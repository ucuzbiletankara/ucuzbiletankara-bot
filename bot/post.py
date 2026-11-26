"""Günün postunu üret: tarama sonucu → içerik → fotoğraf → 10 PNG + caption.

Çalıştırma:  python -m bot.post            (önce python -m bot.scan çalışmış olmalı)
Çıktı:       output/post/01_cover.png ... 10_closing.png, caption.txt, post.json, rapor.md
Yayınlama bu aşamada YOK (Aşama 5).
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config
from .content import generate, shorten_request
from .photos import PhotoFinder, collect
from .render import render_post, overflow_report

OUT = config.ROOT / "output" / "post"
TR_TZ = timezone(timedelta(hours=3))


def build_caption(content: dict, photos: dict) -> str:
    tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in content.get("hashtags", [])[:15])
    credits = sorted({p["credit"] for p in photos.values() if p and p.get("credit")})
    parts = [content["caption"].strip()]
    if credits:
        parts.append("Fotoğraflar: Pixabay · " + " · ".join(credits))
    parts.append(tags)
    return "\n\n".join(p for p in parts if p)


def main() -> None:
    s = config.settings()
    scan = json.loads((config.DATA_DIR / "scan_latest.json").read_text(encoding="utf-8"))
    pick = scan.get("pick")
    if not pick:
        raise SystemExit("Tarama sonucunda paylaşılacak uçuş yok.")
    today = datetime.now(TR_TZ).date()
    model = (s.get("content") or {}).get("model", "claude-sonnet-5-5")
    api_key = config.secret("ANTHROPIC_API_KEY")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1) İçerik
    from . import content as content_mod
    try:
        content, usage = generate(pick, api_key, today, model=model)
    finally:
        (OUT / "claude_raw.json").write_text(
            json.dumps(content_mod.LAST_RAW, ensure_ascii=False, indent=1), encoding="utf-8")

    # 2) Fotoğraflar
    finder = PhotoFinder(config.secret("PIXABAY_API_KEY"), OUT)
    photos = collect(content, content.get("city_en") or pick["city_name"], finder)

    # 3) Render + taşma kontrolü (taşarsa bir kez kısaltma iste)
    render_post(content, pick, photos, OUT)
    over = overflow_report(OUT)
    if over:
        content = shorten_request(content, over, pick, api_key, model)
        render_post(content, pick, photos, OUT)
        over = overflow_report(OUT)

    caption = build_caption(content, photos)
    (OUT / "caption.txt").write_text(caption, encoding="utf-8")
    (OUT / "post.json").write_text(json.dumps(
        {"pick": pick, "content": content, "photos": photos, "usage": usage,
         "generated_at": datetime.now(TR_TZ).isoformat(timespec="minutes")},
        ensure_ascii=False, indent=2), encoding="utf-8")
    for f in OUT.glob("*.html"):
        f.unlink()

    found = sum(1 for p in photos.values() if p)
    report = [
        f"## Post önizleme – {pick['city_name']} ({today.isoformat()})",
        "",
        f"- Uçuş: ESB → {pick['destination_airport']} · {pick['out_date']}"
        + (f" → {pick['ret_date']}" if pick.get("ret_date") else " (tek yön)")
        + f" · {pick['airline_name']} · {pick['price']} TL · mod: {pick.get('mode')}",
        f"- Fotoğraf: {found}/{len(photos)} bulundu",
        f"- Claude kullanımı: {usage}",
        f"- Taşma: {'; '.join(over) if over else 'yok'}",
        "",
        "### Caption",
        "```",
        caption,
        "```",
        "",
        "### Fotoğraf günlüğü",
        *[f"- {l}" for l in finder.log],
        "",
        "### Doğrulama kaynakları",
        *[f"- {u}" for u in content.get("sources", [])],
    ]
    md = "\n".join(report) + "\n"
    (OUT / "rapor.md").write_text(md, encoding="utf-8")
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(md)


if __name__ == "__main__":
    main()
