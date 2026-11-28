"""Meme formatında Reels: "Aktarma acısı" (kullanıcı seçimi, 28 Kasım).

Akış (~10 sn, 1080×1920, sert kesmeler):
  A) 3,5 sn  – havalimanında bekleme/yorgunluk videosu + "İstanbul aktarmalı <şehir>: ... 😩"
  B) 3,0 sn  – kalkış/keyif videosu + "Esenboğa'dan direkt: <süre> 😎"
  C) 3,0 sn  – fiyat kartı: rota, fiyat, tarih, "Bilet linki profilde", "Kiminle gidersin? Gönder"
Videolar Pixabay'den (ücretsiz, ticari kullanım serbest, atıf gerekmez); yazılar bizim.

Kullanım: PIXABAY_API_KEY=... python3 tools/meme_reel.py <post.json> <çıktı_klasörü>
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
from reel import AY3, music, tl  # noqa: E402

W, H, FPS = 1080, 1920, 30
SEG = {"A": 3.5, "B": 3.0, "C": 3.2}
QUERIES = {
    "A": ["yawning tired", "bored waiting", "sleeping chair", "tired man", "waiting clock", "airport waiting"],
    "B": ["happy dance celebration", "woman celebrating", "happy travel woman", "airplane window view", "airplane sunset sky"],
}
BLOCK_TAGS = {"cartoon", "animation", "3d", "render", "military", "fighter", "jet fighter", "crash", "fire", "war"}

FONTS = '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@600;800;900&family=Space+Grotesk:wght@700&display=swap" rel="stylesheet">'
CSS = """*{box-sizing:border-box;margin:0}body{width:1080px;height:1920px;background:transparent;font-family:Inter,sans-serif}
.box{position:absolute;left:70px;right:150px;display:flex;flex-direction:column;align-items:flex-start;gap:14px}
.t{background:#fff;color:#111;font-weight:800;font-size:54px;line-height:1.18;padding:14px 24px;border-radius:18px;box-shadow:0 8px 30px rgba(0,0,0,.25)}
.t.big{font-size:76px;font-weight:900}
.y{background:#FFC533;color:#0F1E33}
.brand{position:absolute;top:150px;left:70px;font-family:'Space Grotesk';font-weight:700;font-size:36px;color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.6)}
.brand span{color:#FFC533}"""


def hm(minutes: int) -> str:
    h, m = divmod(int(minutes), 60)
    return f"{h} saat {m} dakika" if m else f"{h} saat"


def texts(p: dict) -> dict:
    city = p["city_name"]
    return {
        "A": [f"İstanbul aktarmalı {city}:", "Gece kalk, İstanbul'a uç,", "kapıda bekle, bekle, bekle… 😩"],
        "B": ["Esenboğa'dan direkt:", f"{hm(p['duration_min'])},", f"iner inmez {city} 😎"] if p.get("duration_min")
             else ["Esenboğa'dan direkt:", f"iner inmez {city} 😎"],
    }


def pixabay(q: str, key: str) -> list[dict]:
    r = requests.get("https://pixabay.com/api/videos/", params={"key": key, "q": q, "per_page": 20, "safesearch": "true"}, timeout=30)
    r.raise_for_status()
    return r.json().get("hits", [])


def clip_info(h: dict, q: str) -> dict | None:
    v = h["videos"]
    best = next((v[s] for s in ("large", "medium") if v.get(s, {}).get("url") and v[s].get("height", 0) >= 1080), None)
    if not best:
        return None
    return {"query": q, "id": h["id"], "tags": h.get("tags"), "url": best["url"], "w": best["width"], "h": best["height"],
            "page": h.get("pageURL"), "duration": h.get("duration"), "tiny": v.get("tiny", {}).get("url")}


def by_id(vid: int, key: str) -> dict:
    r = requests.get("https://pixabay.com/api/videos/", params={"key": key, "id": vid}, timeout=30)
    r.raise_for_status()
    return clip_info(r.json()["hits"][0], f"id:{vid}")


def candidates(key: str, out: Path, per_query: int = 6):
    """Aday kareleri: her sorgudan ilk N video, ortadan bir kare; numaralı bir pano."""
    from PIL import Image, ImageDraw
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for seg, qs in QUERIES.items():
        for q in qs:
            n = 0
            for h in pixabay(q, key):
                tags = {t.strip().lower() for t in h.get("tags", "").split(",")}
                c = clip_info(h, q)
                if not c or tags & BLOCK_TAGS or not c["tiny"] or h.get("duration", 0) < 5:
                    continue
                f = out / f"t_{h['id']}.mp4"
                f.write_bytes(requests.get(c["tiny"], timeout=60).content)
                jpg = out / f"t_{h['id']}.jpg"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(min(2, h["duration"] / 2)), "-i", str(f),
                                "-frames:v", "1", "-vf", "scale=320:-2", str(jpg)], check=False)
                f.unlink(missing_ok=True)
                if jpg.exists():
                    rows.append((seg, q, h["id"], jpg, h.get("tags", "")))
                    n += 1
                if n >= per_query:
                    break
    cols, tw, th = 6, 320, 210
    sheet = Image.new("RGB", (cols * tw, ((len(rows) + cols - 1) // cols) * (th + 34)), "white")
    d = ImageDraw.Draw(sheet)
    for i, (seg, q, vid, jpg, tags) in enumerate(rows):
        x, y = (i % cols) * tw, (i // cols) * (th + 34)
        im = Image.open(jpg).convert("RGB"); im.thumbnail((tw, th)); sheet.paste(im, (x, y))
        d.text((x + 4, y + th + 2), f"{seg} {vid} | {q}"[:48], fill="black")
        d.text((x + 4, y + th + 16), tags[:48], fill="gray")
        jpg.unlink()
    sheet.save(out / "adaylar.jpg", quality=85)
    (out / "adaylar.json").write_text(json.dumps([{"seg": r[0], "q": r[1], "id": r[2], "tags": r[4]} for r in rows], ensure_ascii=False, indent=1))


def pick_clip(seg: str, key: str, need: float, used: set) -> dict:
    forced = dict(x.split(":") for x in os.environ.get("MEME_IDS", "").split(",") if ":" in x)
    if seg in forced:
        return by_id(int(forced[seg]), key)
    for q in QUERIES[seg]:
        for h in pixabay(q, key):
            tags = {t.strip().lower() for t in h.get("tags", "").split(",")}
            if h["id"] in used or tags & BLOCK_TAGS or h.get("duration", 0) < need + 1:
                continue
            c = clip_info(h, q)
            if not c:
                continue
            used.add(h["id"])
            return c
    raise SystemExit(f"{seg} için uygun video bulunamadı")


def overlay_html(lines: list[str]) -> str:
    rows = "".join(f'<div class="t{" y big" if i == 0 else ""}">{l}</div>' for i, l in enumerate(lines))
    return f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{CSS}</style></head><body>' \
           f'<div class="brand">ucuzbilet<span>ankara</span></div><div class="box" style="top:300px">{rows}</div></body></html>'


def card_html(p: dict) -> str:
    rt = p["format"] == "rt"
    o = date.fromisoformat(p["out_date"])
    d = f"{o.day} {AY3[o.month - 1]}"
    if rt:
        r = date.fromisoformat(p["ret_date"])
        d += f" – {r.day} {AY3[r.month - 1]}"
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{CSS}
body{{background:#0F1E33;color:#F5F3EE}}</style></head><body>
<div class="brand">ucuzbilet<span>ankara</span></div>
<div style="position:absolute;left:70px;right:150px;top:330px;display:flex;flex-direction:column;gap:30px">
 <div style="display:inline-block;align-self:flex-start;background:#FFC533;color:#0F1E33;font-weight:800;font-size:32px;letter-spacing:2px;padding:10px 18px;border-radius:10px">ANKARA'DAN DİREKT ✈</div>
 <div style="font-family:'Space Grotesk';font-weight:700;font-size:130px;line-height:.95;letter-spacing:-4px">{p['city_name']}</div>
 <div style="font-family:'Space Grotesk';font-weight:700;font-size:140px;line-height:1;color:#FFC533;letter-spacing:-4px">{tl(p['price'])}</div>
 <div style="font-size:42px;font-weight:600">{'gidiş-dönüş' if rt else 'tek yön'} · {d} · aktarmasız</div>
 <div style="font-size:34px;color:#C9D3E1">{p.get('airline_name', '')} · kalkış {p.get('out_dep_time', '')}</div>
 <div style="margin-top:30px;background:#F5F3EE;color:#0F1E33;border-radius:26px;padding:30px 36px;font-weight:800;font-size:46px;line-height:1.2">Kiminle gidersin?<br>Ona gönder ✈️</div>
 <div style="font-size:38px;font-weight:800">Bilet linki profilde 🔗</div>
</div></body></html>"""


def render_png(pg, html: str, path: Path, transparent: bool):
    tmp = path.with_suffix(".html")
    tmp.write_text(html, encoding="utf-8")
    pg.goto(tmp.as_uri(), wait_until="networkidle")
    pg.evaluate("document.fonts.ready")
    pg.screenshot(path=str(path), omit_background=transparent)


def run(post_json: Path, out: Path):
    key = os.environ["PIXABAY_API_KEY"]
    p = json.loads(post_json.read_text(encoding="utf-8"))["pick"]
    out.mkdir(parents=True, exist_ok=True)
    tx = texts(p)
    used: set = set()
    clips = {s: pick_clip(s, key, SEG[s], used) for s in ("A", "B")}
    for s, c in clips.items():
        f = out / f"clip_{s}.mp4"
        with requests.get(c["url"], stream=True, timeout=120) as r:
            r.raise_for_status()
            f.write_bytes(r.content)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        for s in ("A", "B"):
            render_png(pg, overlay_html(tx[s]), out / f"ov_{s}.png", True)
        render_png(pg, card_html(p), out / "card.png", False)
        b.close()
    total = sum(SEG.values())
    music(out / "music.wav", total, bpm=112)
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1,"
          "eq=brightness=-0.04:saturation=1.1")
    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-ss", "0.5", "-t", str(SEG["A"]), "-i", str(out / "clip_A.mp4"),
           "-ss", "0.5", "-t", str(SEG["B"]), "-i", str(out / "clip_B.mp4"),
           "-loop", "1", "-t", str(SEG["C"]), "-i", str(out / "card.png"),
           "-i", str(out / "ov_A.png"), "-i", str(out / "ov_B.png"), "-i", str(out / "music.wav"),
           "-filter_complex",
           f"[0:v]{vf}[a0];[a0][3:v]overlay=0:0[a];"
           f"[1:v]{vf}[b0];[b0][4:v]overlay=0:0[b];"
           f"[2:v]fps={FPS},scale={W}:{H},setsar=1,zoompan=z='min(zoom+0.0006,1.04)':d=1:s={W}x{H}:fps={FPS}[c];"
           "[a][b][c]concat=n=3:v=1:a=0,format=yuv420p[v]",
           "-map", "[v]", "-map", "5:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out / "meme_reel.mp4")]
    subprocess.run(cmd, check=True)
    # önizleme karesi ve bilgi
    for t, name in ((1.5, "kare_A"), (5.0, "kare_B"), (8.5, "kare_C")):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(out / "meme_reel.mp4"),
                        "-frames:v", "1", "-q:v", "3", str(out / f"{name}.jpg")], check=True)
    (out / "bilgi.json").write_text(json.dumps({"pick": {k: p.get(k) for k in ("city_name", "price", "format", "out_date", "ret_date", "duration_min")},
                                                 "metin": tx, "klipler": clips, "sure_sn": total}, ensure_ascii=False, indent=1), encoding="utf-8")
    for f in ("clip_A.mp4", "clip_B.mp4", "music.wav"):
        (out / f).unlink(missing_ok=True)
    print(f"Tamam: {out / 'meme_reel.mp4'} ({total:.1f} sn)")


if __name__ == "__main__":
    if sys.argv[1] == "aday":
        candidates(os.environ["PIXABAY_API_KEY"], Path(sys.argv[2]))
    else:
        run(Path(sys.argv[1]), Path(sys.argv[2]))
