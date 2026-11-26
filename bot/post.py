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
from .content import apply_esim, tidy_caption, clean_ad_tags, disclosure_for, esim_for, generate, shorten_request
from .photos import PhotoFinder, collect
from .render import render_post, overflow_report

OUT = config.ROOT / "output" / "post"
TR_TZ = timezone(timedelta(hours=3))


def build_caption(content: dict, photos: dict, disclosure: dict | None) -> str:
    tags = clean_ad_tags(content.get("hashtags", []))[:15]
    if disclosure:
        tags = ["reklam"] + tags
    tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in tags)
    credits = sorted({p["credit"] for p in photos.values() if p and p.get("credit")})
    body = "\n".join(l for l in tidy_caption(content["caption"]).splitlines()
                     if l.strip().lower() not in {"#reklam", "#işbirliği", "#tanıtım"})
    parts = [body]
    if credits:
        parts.append("Fotoğraflar: Pixabay, Wikimedia Commons (" + "; ".join(credits) + ")")
    if disclosure:  # kullanıcı kararı (27 Kasım): tanıtım satırı en altta, hashtag'lerin hemen üstünde
        parts.append(disclosure["line"])
    parts.append(tags)
    return "\n\n".join(p for p in parts if p)


def main() -> None:
    s = config.settings()
    scan = json.loads((config.DATA_DIR / "scan_latest.json").read_text(encoding="utf-8"))
    pick = scan.get("pick")
    if not pick:
        raise SystemExit("Tarama sonucunda paylaşılacak uçuş yok.")
    today = datetime.now(TR_TZ).date()
    cc = s.get("content") or {}
    model = cc.get("model", "claude-haiku-5-5")
    api_key = config.secret("ANTHROPIC_API_KEY")

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    # 1) İçerik
    esim = esim_for(s, pick)
    from . import content as content_mod
    try:
        content, usage = generate(pick, api_key, today, model=model,
                                  max_searches=cc.get("max_searches", 4), effort=cc.get("effort", "medium"),
                                  thinking=cc.get("thinking", "disabled"),
                                  esim=("link" if esim.get("link_in_bio") else "plain") if esim else False)
    finally:
        (OUT / "claude_raw.json").write_text(
            json.dumps(content_mod.LAST_RAW, ensure_ascii=False, indent=1), encoding="utf-8")

    content = apply_esim(content, esim)
    partner = (esim.get("closing_text") or None) if esim else None

    # 2) Fotoğraflar
    city_en = content.get("city_en") or pick["city_name"]
    finder = PhotoFinder(config.secret("PIXABAY_API_KEY"), OUT, city=city_en)
    photos = collect(content, city_en, finder)

    # 3) Render + taşma kontrolü (taşarsa bir kez kısaltma iste)
    disclosure = disclosure_for(s)
    content["disclosure_badge"] = disclosure["badge"] if disclosure else None
    render_post(content, pick, photos, OUT, partner=partner)
    over = overflow_report(OUT)
    if over:
        content = apply_esim(shorten_request(content, over, pick, api_key, model), esim)
        from .content import request_cost, LAST_RAW
        usage["estimated_cost_usd"] = round(sum(request_cost(model, r.get("usage") or {}) for r in LAST_RAW), 4)
        render_post(content, pick, photos, OUT, partner=partner)
        over = overflow_report(OUT)

    caption = build_caption(content, photos, disclosure)
    (OUT / "caption.txt").write_text(caption, encoding="utf-8")
    (OUT / "post.json").write_text(json.dumps(
        {"pick": pick, "content": content, "photos": photos, "usage": usage, "disclosure": disclosure,
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
        f"- Claude: model {model} · tahmini maliyet {usage.get('estimated_cost_usd')} $ "
        f"(aylık ~{round((usage.get('estimated_cost_usd') or 0) * 30, 2)} $) · web araması {usage.get('web_searches')} · "
        f"en büyük istek {usage.get('max_prompt_tokens')} token",
        f"- Ham kullanım: {usage}",
        f"- Taşma: {'; '.join(over) if over else 'yok'}",
        f"- eSIM notu: {'var' if esim else 'yok'}",
        f"- Reklam/tanıtım bildirimi: {disclosure['line'] if disclosure else 'gerekmiyor (menfaat ilişkisi yok)'}",
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
