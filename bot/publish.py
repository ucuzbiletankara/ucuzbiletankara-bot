"""Instagram'a carousel yayınlar.

Akış:
  1. output/post/*.png → JPEG (Instagram API sadece JPEG kabul eder)
  2. JPEG'ler "yayin" dalına konur → raw.githubusercontent.com üzerinden herkese açık adres
  3. Her görsel için carousel öğesi container → CAROUSEL container (caption ile) → hazır olunca media_publish
  4. data/history.json'a paylaşılan şehir yazılır (aynı şehir 3 hafta tekrar seçilmesin)

Çalıştırma:
  python -m bot.publish --check      # sadece bağlantı testi, yayın YOK
  python -m bot.publish              # yayınla (settings.yaml → publish.enabled true olmalı)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import config

TR_TZ = timezone(timedelta(hours=3))
POST_DIR = config.ROOT / "output" / "post"
API_VERSION = "v25.0"
HOSTS = ["https://graph.facebook.com", "https://graph.instagram.com"]


class IGError(RuntimeError):
    pass


def _err(r: requests.Response) -> str:
    try:
        e = r.json().get("error", {})
        return f"{r.status_code} {e.get('type', '')} {e.get('code', '')}: {e.get('message', r.text[:300])}"
    except Exception:  # noqa: BLE001
        return f"{r.status_code}: {r.text[:300]}"


class Instagram:
    def __init__(self, token: str, ig_user_id: str):
        self.token = token
        self.ig = ig_user_id
        self.host = None
        self.s = requests.Session()
        # Token URL'de değil başlıkta gönderilir (hata mesajlarında/loglarda görünmesin)
        self.s.headers["Authorization"] = f"Bearer {token}"

    def _url(self, path: str) -> str:
        return f"{self.host}/{API_VERSION}/{path.lstrip('/')}"

    def detect_host(self) -> dict:
        """Token'ın hangi API adresinde çalıştığını bul (Unified/Facebook → graph.facebook.com,
        Instagram Login → graph.instagram.com)."""
        errors = []
        for host in HOSTS:
            r = self.s.get(f"{host}/{API_VERSION}/{self.ig}",
                           params={"fields": "id,username,media_count"}, timeout=30)
            if r.ok:
                self.host = host
                return r.json()
            errors.append(f"{host}: {_err(r)}")
        raise IGError("Token hiçbir API adresinde çalışmadı:\n" + "\n".join(errors))

    def get(self, path: str, **params) -> dict:
        r = self.s.get(self._url(path), params=params, timeout=60)
        if not r.ok:
            raise IGError(f"GET {path}: {_err(r)}")
        return r.json()

    def post(self, path: str, **data) -> dict:
        r = self.s.post(self._url(path), data=data, timeout=120)
        if not r.ok:
            raise IGError(f"POST {path}: {_err(r)}")
        return r.json()

    def publishing_limit(self) -> dict:
        try:
            return self.get(f"{self.ig}/content_publishing_limit", fields="quota_usage,config")
        except IGError as e:
            return {"hata": str(e)}

    def wait_ready(self, container_id: str, timeout: int = 300) -> None:
        t0 = time.time()
        while time.time() - t0 < timeout:
            st = self.get(container_id, fields="status_code,status").get("status_code")
            if st == "FINISHED":
                return
            if st in ("ERROR", "EXPIRED"):
                raise IGError(f"Container {container_id} durumu {st}")
            time.sleep(5)
        raise IGError(f"Container {container_id} {timeout} sn içinde hazır olmadı")

    def publish_carousel(self, image_urls: list[str], caption: str) -> dict:
        children = []
        for url in image_urls:
            c = self.post(f"{self.ig}/media", image_url=url, is_carousel_item="true")
            children.append(c["id"])
        for cid in children:
            self.wait_ready(cid)
        parent = self.post(f"{self.ig}/media", media_type="CAROUSEL",
                           children=",".join(children), caption=caption)
        self.wait_ready(parent["id"])
        pub = self.post(f"{self.ig}/media_publish", creation_id=parent["id"])
        media_id = pub["id"]
        try:
            info = self.get(media_id, fields="permalink,timestamp")
        except IGError:
            info = {}
        return {"media_id": media_id, **info}


# ---------------------------------------------------------------- görseller

def to_jpegs(png_dir: Path, out_dir: Path) -> list[Path]:
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    for png in sorted(png_dir.glob("[0-9][0-9]_*.png"))[:10]:  # API carousel sınırı: 10
        jpg = out_dir / (png.stem[:2] + ".jpg")
        Image.open(png).convert("RGB").save(jpg, "JPEG", quality=92, optimize=True, progressive=True)
        files.append(jpg)
    if len(files) < 2:
        raise IGError("Carousel için en az 2 görsel gerekli; output/post boş mu?")
    return files


def host_on_github(jpgs: list[Path], day: str) -> list[str]:
    """Görselleri 'yayin' dalına koy (her seferinde sadece son post tutulur) ve raw adreslerini döndür."""
    repo = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / day
        d.mkdir()
        for f in jpgs:
            (d / f.name).write_bytes(f.read_bytes())

        def git(*a):
            subprocess.run(["git", *a], cwd=tmp, check=True, capture_output=True)

        git("init", "-q", "-b", "yayin")
        git("config", "user.name", "github-actions")
        git("config", "user.email", "github-actions@users.noreply.github.com")
        git("add", "-A")
        git("commit", "-q", "-m", f"Yayın görselleri {day}")
        git("push", "-q", "-f", f"https://x-access-token:{token}@github.com/{repo}", "yayin")
    urls = [f"https://raw.githubusercontent.com/{repo}/yayin/{day}/{f.name}" for f in jpgs]
    # Adresler erişilebilir olana kadar bekle (Instagram görseli bu adresten indirecek)
    for _ in range(24):
        if all(requests.head(u, timeout=20).status_code == 200 for u in urls):
            return urls
        time.sleep(5)
    raise IGError("Görseller herkese açık adreste görünmedi: " + urls[0])


def trim_caption(caption: str) -> str:
    """Instagram sınırları: 2200 karakter, en fazla 30 hashtag."""
    words, tags = [], 0
    for w in caption.split(" "):
        if w.startswith("#"):
            tags += 1
            if tags > 30:
                continue
        words.append(w)
    caption = " ".join(words)
    return caption[:2200]


def record_history(pick: dict, result: dict) -> None:
    p = config.DATA_DIR / "history.json"
    hist = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
    hist.append({"date": datetime.now(TR_TZ).date().isoformat(), "city": pick["city"],
                 "country": pick.get("country"), "price": pick.get("price"),
                 "out_date": pick.get("out_date"), "media_id": result.get("media_id"),
                 "permalink": result.get("permalink")})
    p.write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")


def check_disclosure(caption: str, disclosure: dict | None) -> None:
    """Yönetmelik m.23/A: bildirim gereken postta "Reklam/Tanıtım" + marka caption'da yer almalı.
    Kullanıcı kararı (27 Kasım): satır en altta, hashtag'lerin hemen üstünde."""
    if not disclosure:
        return
    word = disclosure.get("word", "Tanıtım").lower()
    brand = disclosure["brands"].split(" · ")[0].lower()
    if not any(word in l.lower() and brand in l.lower() for l in caption.splitlines()):
        raise IGError("Reklam/tanıtım bildirimi caption'da yok; post paylaşılmadı.")


# ---------------------------------------------------------------- giriş noktası

def summary(md: str) -> None:
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md + "\n")


def check() -> dict:
    s = config.settings().get("publish") or {}
    ig = Instagram(config.secret("IG_ACCESS_TOKEN"), str(s["ig_user_id"]))
    info = ig.detect_host()
    res = {"ok": True, "host": ig.host, "account": info, "publishing_limit": ig.publishing_limit()}
    summary(f"## Instagram bağlantı testi\n\n- Hesap: @{info.get('username')} (ID {info.get('id')}, "
            f"{info.get('media_count')} post)\n- API adresi: {ig.host}\n- Yayın kotası: {res['publishing_limit']}\n")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="sadece bağlantı testi")
    ap.add_argument("--force", action="store_true", help="publish.enabled false olsa da yayınla (elle ilk yayın)")
    args = ap.parse_args()

    out = config.DATA_DIR / "ig_check.json"
    if args.check:
        try:
            res = check()
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "error": str(e)}
            summary(f"## Instagram bağlantı testi BAŞARISIZ\n\n```\n{e}\n```")
        out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        if not res["ok"]:
            raise SystemExit(1)
        return

    s = config.settings().get("publish") or {}
    if not (s.get("enabled") or args.force):
        summary("Yayın kapalı (config/settings.yaml → publish.enabled: false). Post üretildi ama paylaşılmadı.")
        return

    post = json.loads((POST_DIR / "post.json").read_text(encoding="utf-8"))
    caption = trim_caption((POST_DIR / "caption.txt").read_text(encoding="utf-8"))
    check_disclosure(caption, post.get("disclosure"))
    ig = Instagram(config.secret("IG_ACCESS_TOKEN"), str(s["ig_user_id"]))
    ig.detect_host()
    day = datetime.now(TR_TZ).strftime("%Y-%m-%d-%H%M")
    urls = host_on_github(to_jpegs(POST_DIR, config.ROOT / "output" / "jpg"), day)
    result = ig.publish_carousel(urls, caption)
    record_history(post["pick"], result)
    (config.DATA_DIR / "last_publish.json").write_text(
        json.dumps({"pick": post["pick"], **result}, ensure_ascii=False, indent=1), encoding="utf-8")
    summary(f"## Instagram'da yayınlandı ✅\n\n- {post['pick']['city_name']} · {post['pick']['price']} TL\n"
            f"- Bağlantı: {result.get('permalink')}\n")


if __name__ == "__main__":
    main()
