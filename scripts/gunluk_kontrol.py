"""Günlük post başlamadan önce: bu çalıştırma paylaşım yapmalı mı?

Kurallar (28 Kasım'da, 7 saat gecikip 02:59'da çalışan zamanlanmış iş yüzünden eklendi):
1. Zamanlanmış (schedule) çalıştırma sadece 18:00–23:00 (Türkiye) arasında paylaşır. GitHub işi geciktirip
   gece ya da ertesi gün başlatırsa atlanır. Elle başlatılan çalıştırmaya bu kural uygulanmaz.
2. Aynı gün (Türkiye) paylaşım varsa ya da son paylaşımın üstünden 18 saat geçmediyse atlanır.
3. Elle başlatırken "kontrolu_atla" işaretlenirse bu kontrol yapılmaz.
Kullanım: python3 scripts/gunluk_kontrol.py <history.json> <event_name>  → "skip" ya da "ok" yazar.
"""
import json
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TR = ZoneInfo("Europe/Istanbul")
WINDOW = (18, 23)
MIN_GAP = timedelta(hours=18)


def decide(history: list, event: str, now: datetime) -> tuple[bool, str]:
    if event == "schedule" and not (WINDOW[0] <= now.hour < WINDOW[1]):
        return False, f"zamanlanmış iş saat {now:%H:%M}'te başladı (izin: {WINDOW[0]}:00–{WINDOW[1]}:00); atlanıyor"
    today = now.date().isoformat()
    for e in reversed(history):
        if e.get("date") == today:
            return False, f"bugün ({today}) zaten paylaşım var; atlanıyor"
        t = e.get("time")
        if t:
            when = datetime.fromisoformat(t)
            if when.tzinfo is None:
                when = when.replace(tzinfo=TR)
            if now - when < MIN_GAP:
                return False, f"son paylaşım {when:%d.%m %H:%M}, 18 saat geçmedi; atlanıyor"
    return True, "paylaşıma uygun"


if __name__ == "__main__":
    try:
        hist = json.load(open(sys.argv[1], encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        hist = []
    ok, why = decide(hist, sys.argv[2], datetime.now(TR))
    print(why, file=sys.stderr)
    print("ok" if ok else "skip")
