"""Slaytları HTML şablonundan 1080×1350 PNG'ye çevirir (Playwright / Chromium)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import ROOT

SLIDES = ["cover", "why_now", "sights_1", "sights_2", "food", "eat", "stay", "transport", "tips", "closing"]

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
AYLAR_KISA = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def tl(x: float) -> str:
    return f"{x:,.0f} TL".replace(",", ".")


def flight_view(pick: dict) -> dict:
    """Şablonun ihtiyaç duyduğu hazır metinler."""
    out = date.fromisoformat(pick["out_date"])
    ret = date.fromisoformat(pick["ret_date"]) if pick.get("ret_date") else None
    if ret:
        if out.month == ret.month:
            dates = f"{out.day} → {ret.day} {AYLAR[out.month - 1]}"
            short = f"{out.day}–{ret.day} {AYLAR[out.month - 1]}"
        else:
            dates = f"{out.day} {AYLAR_KISA[out.month - 1]} → {ret.day} {AYLAR_KISA[ret.month - 1]}"
            short = dates.replace(" → ", "–")
    else:
        dates = short = f"{out.day} {AYLAR[out.month - 1]}"
    dur = pick.get("duration_min")
    dur_txt = f"{dur // 60} sa {dur % 60:02d} dk" if dur else ""

    def leg(dep, arr):
        if not dep:
            return ""
        return f"{dep} → {arr}" if arr else f"Kalkış {dep}"

    out_leg = leg(pick.get("out_dep_time"), pick.get("out_arr_time"))
    ret_leg = leg(pick.get("ret_dep_time"), pick.get("ret_arr_time"))
    return {**pick, "dates_txt": dates, "dates_short": short, "duration_txt": dur_txt,
            "price_txt": tl(pick["price"]), "out_leg": out_leg, "ret_leg": ret_leg,
            "dep_short": pick.get("out_dep_time") or ""}


def city_size(name: str) -> int:
    n = len(name)
    if n <= 7:
        return 200
    if n <= 9:
        return 170
    if n <= 12:
        return 130
    return 104


def render_post(content: dict, pick: dict, photos: dict, out_dir: Path, partner: str | None = None) -> list[Path]:
    """photos: anahtar → {"file": out_dir içindeki dosya adı, "credit": str|None}"""
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(ROOT / "templates"),
                      autoescape=select_autoescape(["html", "j2"]))
    tpl = env.get_template("slide.html.j2")
    flight = flight_view(pick)

    # Fotoğraf kaynak gösterimi gerekenler: hangi slaytta kullanıldıysa o slayta küçük not
    credits: dict[str, list[str]] = {}
    for key, p in photos.items():
        if p and p.get("credit"):
            slide = next((s for s in SLIDES if key == s or key.startswith(s + "_")), None)
            if slide:
                credits.setdefault(slide, []).append(p["credit"])

    html_files = []
    for i, slide in enumerate(SLIDES, 1):
        html = tpl.render(slide=slide, c=content, flight=flight, photos=photos,
                          city_size=city_size(flight["city_name"]), partner=partner,
                          credit=" · ".join(dict.fromkeys(credits.get(slide, []))) or None)
        f = out_dir / f"{i:02d}_{slide}.html"
        f.write_text(html, encoding="utf-8")
        html_files.append(f)

    from playwright.sync_api import sync_playwright

    pngs = []
    with sync_playwright() as pw:
        kw = {}
        if os.environ.get("CHROME_PATH"):  # yerel test için
            kw["executable_path"] = os.environ["CHROME_PATH"]
        browser = pw.chromium.launch(**kw)
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        for f in html_files:
            page.goto(f.as_uri(), wait_until="load")
            try:
                page.evaluate("document.fonts.ready")
            except Exception:
                pass
            page.wait_for_timeout(300)
            png = f.with_suffix(".png")
            page.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": 1080, "height": 1350})
            pngs.append(png)
        browser.close()
    return pngs


def overflow_report(out_dir: Path) -> list[str]:
    """Taşma kontrolü: içerik 1350 px'i aşıyorsa uyarı listesi döndürür."""
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir).resolve()
    issues = []
    with sync_playwright() as pw:
        kw = {"executable_path": os.environ["CHROME_PATH"]} if os.environ.get("CHROME_PATH") else {}
        browser = pw.chromium.launch(**kw)
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        for f in sorted(out_dir.glob("*.html")):
            page.goto(f.as_uri(), wait_until="load")
            h = page.evaluate(
                "() => { const s = document.querySelector('.slide') || document.body.firstElementChild;"
                " return s ? s.scrollHeight : 0 }"
            )
            if h > 1350:
                issues.append(f"{f.name}: içerik {h}px (sınır 1350)")
        browser.close()
    return issues
