"""Günün fırsatlarını tara ve listele.

Çalıştırma:  python -m bot.scan
Çıktı:       data/scan_latest.json  +  GitHub Actions özet tablosu
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

from . import config
from .deals import (
    best_round_trip,
    build_deal,
    city_allowed,
    group_one_way,
    parse_day,
    rank,
    score_deal,
)
from .travelpayouts import Client, load_cities

TR_TZ = timezone(timedelta(hours=3))
RT_CANDIDATES = 12  # gidiş-dönüş araması yapılacak en iyi şehir sayısı


def month_list(today: date, n: int) -> list[str]:
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def next_month(ym: str) -> str:
    y, m = map(int, ym.split("-"))
    return f"{y + (m == 12):04d}-{(m % 12) + 1:02d}"


def load_history() -> list[dict]:
    p = config.DATA_DIR / "history.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return []


def run(client, cities: dict, today: date | None = None) -> dict:
    s = config.settings()
    dest_cfg = config.destinations()
    seasons = config.seasons()
    history = load_history()
    today = today or datetime.now(TR_TZ).date()
    origin = dest_cfg.get("origin", "ESB")
    months = month_list(today, s["scan"]["months_ahead"])

    # 1) Keşif: "Ankara'dan her yere" toplu sorgu (yeni açılan rotaları yakalamak için)
    rows = []
    for market in s["markets"]:
        for ym in months:
            rows += client.prices_for_dates(origin, ym, one_way=True, direct=True, market=market)

    # 2) Ülke kuralı: keşfedilenler + bilinen direkt rotalar
    known = list(dest_cfg.get("known_direct") or [])
    seen = sorted({r["destination"] for r in rows} | set(known))
    allowed, excluded = [], []
    for code in seen:
        country = cities.get(code, {}).get("country", "")
        (allowed if city_allowed(code, country, dest_cfg) else excluded).append(code)

    # 3) Her izinli şehir için ayrı sorgu (toplu sorgu sadece popüler rotaları döndürüyor).
    #    Önce ilk pazar; veri azsa diğer pazarlar da denenir.
    for code in allowed:
        got = [r for r in rows if r["destination"] == code]
        for market in s["markets"]:
            if len(got) >= 6 and market != s["markets"][0]:
                break
            for ym in months:
                new = client.prices_for_dates(
                    origin, ym, destination=code, one_way=True, direct=True, market=market
                )
                got += new
                rows += new

    found = {r["destination"] for r in rows}
    no_data = sorted(c for c in allowed if c not in found)
    allowed_rows = [r for r in rows if r["destination"] in allowed]
    grouped = group_one_way(allowed_rows, today, s)

    # 4) Ön sıralama: tek yön indirimine göre en iyi şehirler için gidiş-dönüş ara
    def pre_score(code: str) -> float:
        ps = [r["price"] for r in grouped[code]]
        if len(ps) < 3:
            return -1
        ps.sort()
        return 1 - ps[0] / ps[len(ps) // 2]

    candidates = sorted(grouped, key=pre_score, reverse=True)[:RT_CANDIDATES]
    rt_best: dict[str, dict | None] = {}
    for code in candidates:
        cheap = sorted(grouped[code], key=lambda r: r["price"])[:3]
        rt_months = sorted({parse_day(r["departure_at"]).strftime("%Y-%m") for r in cheap})
        rt_rows = []
        for market in s["markets"]:
            for ym in rt_months:
                for ret_ym in (ym, next_month(ym)):
                    rt_rows += client.prices_for_dates(
                        origin, ym, destination=code, return_at=ret_ym,
                        one_way=False, direct=True, market=market,
                    )
        rt_best[code] = best_round_trip(rt_rows, today, s)

    # 5) Fırsatları kur ve puanla
    deals, thin = [], []
    for code, ow_rows in grouped.items():
        deal = build_deal(code, ow_rows, rt_best.get(code), cities, dest_cfg, seasons, s)
        if deal is None:
            thin.append(code)
            continue
        deal = score_deal(deal, today, history, s)
        if deal:
            deals.append(deal)
    deals = rank(deals)

    # Günün seçimi: eşiği geçen en iyi fırsat; yoksa (yedek kural) en iyi aday,
    # "fırsat" denmeden "Ankara'dan direkt" diliyle paylaşılır.
    good = [d for d in deals if d.discount >= s["scoring"]["min_discount"]]
    pick = None
    if deals:
        best = good[0] if good else deals[0]
        pick = {**best.to_dict(), "mode": "firsat" if good else "direkt"}

    return {
        "generated_at": datetime.now(TR_TZ).isoformat(timespec="minutes"),
        "today": today.isoformat(),
        "origin": origin,
        "api_calls": getattr(client, "calls", None),
        "direct_destinations_seen": sorted(found),
        "excluded_by_rules": [c for c in excluded if c in found],
        "no_data": no_data,
        "too_little_data": sorted(thin),
        "deals": [d.to_dict() for d in deals],
        "pick": pick,
    }


# ---------------------------------------------------------------- çıktı

def tl(x: float) -> str:
    return f"{x:,.0f} TL".replace(",", ".")


def tr_date(iso: str) -> str:
    aylar = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
    d = date.fromisoformat(iso)
    return f"{d.day} {aylar[d.month - 1]}"


def to_markdown(res: dict, cities: dict, top: int = 15) -> str:
    def name(code):
        return cities.get(code, {}).get("name", code)

    lines = [
        f"## Günün fırsatları – {res['today']}",
        "",
        f"Fiyat verisi gelen direkt nokta: {len(res['direct_destinations_seen'])}; "
        f"kurala uymadığı için elenen: {len(res['excluded_by_rules'])}; "
        f"değerlendirilen fırsat: {len(res['deals'])}. API çağrısı: {res['api_calls']}.",
        "",
    ]
    if not res["deals"]:
        lines.append("Bugün kurala uyan fırsat bulunamadı.")
    else:
        lines += [
            "| # | Rota | Format | Tarih | Fiyat | Normal tek yön | İndirim | Veri | Sezon / tatil | Havayolu | Puan |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for i, d in enumerate(res["deals"][:top], 1):
            fmt = f"Gidiş-dönüş ({d['nights']} gece)" if d["format"] == "rt" else "Tek yön"
            when = tr_date(d["out_date"]) + (f" → {tr_date(d['ret_date'])}" if d["ret_date"] else "")
            tags = ", ".join(filter(None, [d["season"]] + d["holidays"])) or "–"
            lines.append(
                f"| {i} | ESB → {d['destination_airport'] or d['city']} {d['city_name']} | {fmt} | {when} | "
                f"**{tl(d['price'])}** | {tl(d['median_one_way'])} | %{d['discount']*100:.0f} | {d['samples']} | {tags} | "
                f"{d['airline_name']} | {d['score']} |"
            )
        min_disc = config.settings()["scoring"]["min_discount"]
        good = [d for d in res["deals"] if d["discount"] >= min_disc]
        best = good[0] if good else res["deals"][0]
        if good:
            lines += ["", f"**Bugün paylaşılacak post:** {best['city_name']} – {tl(best['price'])}"]
        else:
            lines += ["", f"**Bugün %{min_disc*100:.0f} eşiğini geçen fırsat yok.** "
                          f"En iyi aday: {best['city_name']} – {tl(best['price'])}"]
        if best["notes"]:
            lines.append("Not: " + "; ".join(best["notes"]))
    if res["excluded_by_rules"]:
        lines += ["", "**Kurala uymadığı için elenen direkt noktalar:** "
                  + ", ".join(f"{c} {name(c)}" for c in res["excluded_by_rules"])]
    if res.get("no_data"):
        lines += ["", "**Önbellekte hiç direkt fiyat bulunamayanlar:** "
                  + ", ".join(f"{c} {name(c)}" for c in res["no_data"])]
    if res["too_little_data"]:
        lines += ["", "**Fiyat verisi az olduğu için değerlendirilemeyenler:** "
                  + ", ".join(f"{c} {name(c)}" for c in res["too_little_data"])]
    return "\n".join(lines) + "\n"


def main() -> None:
    token = config.secret("TRAVELPAYOUTS_TOKEN")
    s = config.settings()
    client = Client(token, currency=s.get("currency", "try"))
    cities = load_cities()
    res = run(client, cities)

    config.DATA_DIR.mkdir(exist_ok=True)
    (config.DATA_DIR / "scan_latest.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md = to_markdown(res, cities)
    (config.DATA_DIR / "scan_summary.md").write_text(md, encoding="utf-8")
    print(md)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(md)


if __name__ == "__main__":
    sys.exit(main())
