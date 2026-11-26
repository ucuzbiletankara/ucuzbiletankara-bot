"""Sabit postları (sabit/<ad>/1..4.jpg + caption.txt) sırayla Instagram'a carousel olarak paylaşır.

Sıra: Nasıl kullanılır → Neden biz → Biz kimiz (en yenisi "Biz kimiz?" olsun diye).
Daha önce paylaşılanlar onay/sabit_sonuc.json'da durur ve tekrar paylaşılmaz.
history.json'a yazılmaz (şehir postu değil).
"""
from __future__ import annotations

import json
import time

from . import config
from .publish import IGError, Instagram, check_disclosure, host_on_github, summary, trim_caption

ORDER = ["3_nasil_kullanilir", "2_neden_biz", "1_biz_kimiz"]
RESULT = config.ROOT / "onay" / "sabit_sonuc.json"
DISCLOSURE = {"word": "Tanıtım", "brands": "Aviasales · Airalo"}


def main() -> None:
    s = config.settings().get("publish") or {}
    done = json.loads(RESULT.read_text(encoding="utf-8")) if RESULT.exists() else {}
    ig = Instagram(config.secret("IG_ACCESS_TOKEN"), str(s["ig_user_id"]))
    ig.detect_host()
    lines = ["## Sabit postlar"]
    for i, name in enumerate(ORDER):
        if done.get(name, {}).get("permalink"):
            lines.append(f"- {name}: zaten paylaşılmış → {done[name]['permalink']}")
            continue
        d = config.ROOT / "sabit" / name
        jpgs = sorted(d.glob("*.jpg"))
        if len(jpgs) != 4:
            raise IGError(f"{name}: 4 görsel bekleniyordu, {len(jpgs)} bulundu")
        caption = trim_caption((d / "caption.txt").read_text(encoding="utf-8"))
        check_disclosure(caption, DISCLOSURE)
        urls = host_on_github(jpgs, f"sabit-{name}")
        res = ig.publish_carousel(urls, caption)
        done[name] = res
        RESULT.parent.mkdir(exist_ok=True)
        RESULT.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        lines.append(f"- {name}: ✅ {res.get('permalink')}")
        if i < len(ORDER) - 1:
            time.sleep(60)  # sıra belli olsun
    summary("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
