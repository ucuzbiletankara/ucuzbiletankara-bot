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
GENERIC = {"city", "photo", "plate", "dish", "food", "building", "interior", "exterior", "evening", "night",
           "street", "streets", "old", "town", "lights", "light", "view", "christmas", "market", "train",
           "platform", "station", "museum", "church", "palace", "square", "park", "river", "bridge", "tower",
           "with", "and", "the", "from", "courtyard", "atrium", "winter", "summer", "traditional", "local",
           "cafe", "coffee", "house", "restaurant", "hotel", "beach", "sunset", "panorama", "skyline", "aerial",
           "bahn", "sbahn", "ubahn", "tram", "metro", "subway", "airport", "terminal", "hauptbahnhof", "central",
           "railway", "rail", "taxi", "public", "transport", "transit", "express", "line"}
OTHER_CITIES = {"berlin", "london", "paris", "vienna", "wien", "munich", "munchen", "frankfurt", "hamburg",
                "cologne", "koln", "rome", "roma", "prague", "praha", "budapest", "amsterdam", "barcelona",
                "madrid", "lisbon", "lisboa", "istanbul", "dubai", "new york", "moscow", "warsaw", "krakow",
                "zurich", "geneva", "brussels", "copenhagen", "stockholm", "oslo", "venice", "milan", "florence",
                "dresden", "nuremberg", "salzburg", "stuttgart", "dusseldorf", "leipzig", "bremen", "hannover",
                "edinburgh", "dublin", "athens", "baku", "tbilisi", "cairo", "belgrade", "sarajevo", "tirana",
                "bucharest", "sofia", "riga", "tallinn", "vilnius", "helsinki", "seville", "valencia", "porto",
                "nice", "lyon", "marseille", "strasbourg", "basel", "bern", "innsbruck", "graz", "bratislava"}


ALIASES = [{"vienna", "wien"}, {"munich", "munchen"}, {"cologne", "koln"}, {"prague", "praha"},
           {"lisbon", "lisboa"}, {"rome", "roma"}, {"nuremberg", "nurnberg"}, {"warsaw", "warszawa"},
           {"krakow", "cracow"}, {"copenhagen", "kobenhavn"}, {"brussels", "bruxelles", "brussel"},
           {"geneva", "geneve", "genf"}, {"zurich", "zuerich"}, {"belgrade", "beograd"}, {"bucharest", "bucuresti"}]


def city_names(city: str) -> set[str]:
    c = norm(city)
    for group in ALIASES:
        if c in group:
            return set(group)
    return {c}


def norm(t: str) -> str:
    t = t.lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "ss"), ("é", "e"), ("è", "e"), ("á", "a"),
                 ("ç", "c"), ("ş", "s"), ("ğ", "g"), ("ı", "i"), ("ø", "o"), ("å", "a"), ("ñ", "n")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def relevant(query: str, text: str, city: str, strict: bool, place: bool = True) -> bool:
    """Fotoğraf metni (etiketler/başlık/adres) sorguyla uyumlu mu?
    strict: sorgunun şehir dışındaki ilk özgün kelimesi geçmeli. Her durumda başka şehir adı geçmemeli."""
    q, t, own = norm(query).split(), f" {norm(text)} ", city_names(city)
    for oc in OTHER_CITIES:
        if oc not in own and oc not in norm(query) and f" {oc} " in t:
            return False
    key = [w for w in q if len(w) >= 4 and w not in GENERIC and w not in own]
    city_hit = any(f" {c} " in t for c in own)
    if strict:
        if not key:
            # sorgu "şehir + genel kelimeler" ise (ör. "stuttgart christmas market"):
            # şehir VE en az bir diğer kelime geçmeli
            others = [w for w in q if len(w) >= 4 and w not in own]
            return city_hit and (not others or any(f" {w}" in t for w in others))
        w = key[0]
        hit = f" {w} " in t or f" {w[:6]}" in t
        return hit and (city_hit or not place)
    if place:  # gevşek modda bile yer fotoğrafında şehir adı geçmeli
        return city_hit
    return any(f" {w}" in t for w in key)


OK_LICENSES = re.compile(r"^(cc0|public domain|pd|cc by(-sa)? [\d.]+|cc by(-sa)?)", re.I)


class PhotoFinder:
    def __init__(self, pixabay_key: str | None, out_dir: Path, city: str = ""):
        self.key = pixabay_key
        self.city = city
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
            artist = re.sub(r"^(photo|foto|fotograf|author)\s*:\s*", "", artist, flags=re.I)
            artist = re.split(r"[\n,;(]| -{2,}| if you", artist, flags=re.I)[0].strip()[:28]
            needs_credit = not re.match(r"^(cc0|public domain|pd)", lic, re.I)
            out.append({"id": f"wm{p['pageid']}", "url": info.get("thumburl") or info.get("url"),
                        "title": p.get("title", ""),
                        "credit": f"{artist or 'Wikimedia Commons'} / Wikimedia, {lic}" if needs_credit else None})
        return out

    # ------------------------------------------------------------ ortak
    def _download(self, url: str, name: str) -> str:
        ext = ".jpg" if ".png" not in url.lower() else ".png"
        fname = f"{name}{ext}"
        r = self.s.get(url, timeout=60)
        r.raise_for_status()
        (self.out / fname).write_bytes(r.content)
        return fname

    def _try_pixabay(self, name, q, orientation, strict):
        for hit in self._pixabay(q, orientation):
            pid = f"px{hit['id']}"
            if pid in self.used:
                continue
            text = f"{hit.get('tags', '')} {hit.get('pageURL', '')}"
            if not relevant(q, text, self.city, strict, place=not name.startswith("food")):
                continue
            self.used.add(pid)
            url = hit.get("largeImageURL") or hit.get("webformatURL")
            self.log.append(f"{name}: Pixabay{'' if strict else ' (gevşek)'} '{q}' → {hit.get('pageURL')}")
            return {"file": self._download(url, name), "credit": None, "source": hit.get("pageURL")}
        return None

    def _try_wikimedia(self, name, q, strict):
        for hit in self._wikimedia(q):
            if hit["id"] in self.used or not relevant(q, hit["title"], self.city, strict,
                                                      place=not name.startswith("food")):
                continue
            self.used.add(hit["id"])
            self.log.append(f"{name}: Wikimedia '{q}' → {hit['title']}")
            return {"file": self._download(hit["url"], name), "credit": hit["credit"], "source": hit["url"]}
        return None

    def find(self, name: str, queries: list[str], orientation: str = "horizontal") -> dict | None:
        """Önce sıkı eşleşme (Pixabay → Wikimedia), sonra gevşek eşleşme (Pixabay).
        Daha önce kullanılan fotoğraf tekrar seçilmez."""
        queries = [q for q in queries if q]
        for strict in (True, False):
            for q in queries:
                try:
                    got = self._try_pixabay(name, q, orientation, strict)
                    if got:
                        return got
                except Exception as e:  # noqa: BLE001
                    self.log.append(f"{name}: Pixabay hata '{q}': {e}")
                if not strict:
                    continue
                try:
                    got = self._try_wikimedia(name, q, strict)
                    if got:
                        return got
                except Exception as e:  # noqa: BLE001
                    self.log.append(f"{name}: Wikimedia hata '{q}': {e}")
        self.log.append(f"{name}: uygun fotoğraf bulunamadı {queries}")
        return None


def collect(content: dict, city_en: str, finder: PhotoFinder) -> dict:
    """İçerikteki her fotoğraf alanı için fotoğraf bul. Sorgu bulunamazsa şehir adına düşer."""
    c = content
    jobs = [("cover", [c["cover"].get("photo_query"), f"{city_en} city"], "vertical"),
            ("why_now", [c["why_now"].get("photo_query"), c["cover"].get("photo_query"), f"{city_en} old town"], "horizontal")]
    for sec in ("sights_1", "sights_2"):
        for i, it in enumerate(c[sec]["items"]):
            jobs.append((f"{sec}_{i}", [it.get("photo_query"), f"{it['name']} {city_en}"], "horizontal"))
    for i, it in enumerate(c["food"]["items"]):
        jobs.append((f"food_{i}", [it.get("photo_query"), it["name"]], "horizontal"))
    jobs += [("eat", [c["eat"].get("photo_query"), f"{city_en} old town", f"{city_en} square"], "horizontal"),
             ("stay", [c["stay"].get("photo_query"), f"{city_en} old town", f"{city_en} architecture"], "horizontal"),
             ("transport", [c["transport"].get("photo_query"), f"{city_en} tram"], "horizontal")]
    return {name: finder.find(name, qs, ori) for name, qs, ori in jobs}
