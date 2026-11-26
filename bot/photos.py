"""Fotoğraf bulucu: önce Pixabay, bulunamazsa Wikimedia Commons.

Pixabay: içerikler kaynak göstermeden ticari kullanılabilir; API istekleri 24 saat
önbelleğe alınmalı ve görseller sunucuya indirilmeli (hotlink yok). → .cache/pixabay
Wikimedia: sadece serbest lisanslar (CC0, kamu malı, CC BY, CC BY-SA); kaynak gösterimi
slaytın köşesine ve caption'a eklenir.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import requests

from .config import ROOT

CACHE = ROOT / ".cache" / "pixabay"
UA = "ucuzbiletankara-bot/1.0 (https://github.com/ucuzbiletankara/ucuzbiletankara-bot)"
OK_LICENSES = re.compile(r"^(cc0|public domain|pd|cc by(-sa)? [\d.]+|cc by(-sa)?)", re.I)


class PhotoFinder:
    def __init__(self, pixabay_key: str | None, out_dir: Path):
        self.key = pixabay_key
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.used: set[str] = set()
        self.s = requests.Session()
        self.s.headers["User-Agent"] = UA
        self.log: list[str] = []

    # ------------------------------------------------------------ Pixabay
    def _pixabay(self, query: str, orientation: str) -> list[dict]:
        if not self.key:
            return []
        CACHE.mkdir(parents=True, exist_ok=True)
        h = hashlib.sha1(f"{query}|{orientation}".encode()).hexdigest()[:16]
        cf = CACHE / f"{h}.json"
        if cf.exists() and time.time() - cf.stat().st_mtime < 24 * 3600:
            return json.loads(cf.read_text())
        r = self.s.get("https://pixabay.com/api/", params={
            "key": self.key, "q": query[:100], "image_type": "photo", "orientation": orientation,
            "safesearch": "true", "per_page": 20, "order": "popular",
            "min_width": 1200 if orientation == "horizontal" else 800,
        }, timeout=30)
        if r.status_code == 429:
            time.sleep(10)
            return []
        r.raise_for_status()
        hits = r.json().get("hits", [])
        cf.write_text(json.dumps(hits))
        return hits

    # ------------------------------------------------------------ Wikimedia
    def _wikimedia(self, query: str) -> list[dict]:
        r = self.s.get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 10,
            "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1600,
        }, timeout=30)
        r.raise_for_status()
        pages = (r.json().get("query") or {}).get("pages") or {}
        out = []
        for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            lic = (meta.get("LicenseShortName") or {}).get("value", "")
            if not OK_LICENSES.match(lic.strip()):
                continue
            if (info.get("width") or 0) < 1000:
                continue
            artist = re.sub("<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
            needs_credit = not re.match(r"^(cc0|public domain|pd)", lic, re.I)
            out.append({"id": f"wm{p['pageid']}", "url": info.get("thumburl") or info.get("url"),
                        "credit": f"Foto: {artist[:40] or 'Wikimedia Commons'} / Wikimedia, {lic}" if needs_credit else None})
        return out

    # ------------------------------------------------------------ ortak
    def _download(self, url: str, name: str) -> str:
        ext = ".jpg" if ".png" not in url.lower() else ".png"
        fname = f"{name}{ext}"
        r = self.s.get(url, timeout=60)
        r.raise_for_status()
        (self.out / fname).write_bytes(r.content)
        return fname

    def find(self, name: str, queries: list[str], orientation: str = "horizontal") -> dict | None:
        """queries sırayla denenir. Daha önce kullanılan fotoğraf tekrar seçilmez."""
        for q in [q for q in queries if q]:
            try:
                for hit in self._pixabay(q, orientation):
                    pid = f"px{hit['id']}"
                    if pid in self.used:
                        continue
                    self.used.add(pid)
                    url = hit.get("largeImageURL") or hit.get("webformatURL")
                    self.log.append(f"{name}: Pixabay '{q}' → {hit.get('pageURL')}")
                    return {"file": self._download(url, name), "credit": None, "source": hit.get("pageURL")}
            except Exception as e:  # noqa: BLE001
                self.log.append(f"{name}: Pixabay hata '{q}': {e}")
            try:
                for hit in self._wikimedia(q):
                    if hit["id"] in self.used:
                        continue
                    self.used.add(hit["id"])
                    self.log.append(f"{name}: Wikimedia '{q}' → {hit['url']}")
                    return {"file": self._download(hit["url"], name), "credit": hit["credit"], "source": hit["url"]}
            except Exception as e:  # noqa: BLE001
                self.log.append(f"{name}: Wikimedia hata '{q}': {e}")
        self.log.append(f"{name}: fotoğraf bulunamadı {queries}")
        return None


def collect(content: dict, city_en: str, finder: PhotoFinder) -> dict:
    """İçerikteki her fotoğraf alanı için fotoğraf bul. Sorgu bulunamazsa şehir adına düşer."""
    c = content
    jobs = [("cover", [c["cover"].get("photo_query"), f"{city_en} city"], "vertical"),
            ("why_now", [c["why_now"].get("photo_query"), f"{city_en}"], "horizontal")]
    for sec in ("sights_1", "sights_2"):
        for i, it in enumerate(c[sec]["items"]):
            jobs.append((f"{sec}_{i}", [it.get("photo_query"), f"{it['name']} {city_en}"], "horizontal"))
    for i, it in enumerate(c["food"]["items"]):
        jobs.append((f"food_{i}", [it.get("photo_query"), it["name"]], "horizontal"))
    jobs += [("eat", [c["eat"].get("photo_query"), f"{city_en} restaurant"], "horizontal"),
             ("stay", [c["stay"].get("photo_query"), f"{city_en} street"], "horizontal"),
             ("transport", [c["transport"].get("photo_query"), f"{city_en} tram"], "horizontal")]
    return {name: finder.find(name, qs, ori) for name, qs, ori in jobs}
