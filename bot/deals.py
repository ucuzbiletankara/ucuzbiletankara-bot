"""Fırsat bulma mantığı: filtre, fiyat formatı (gidiş-dönüş / tek yön), puanlama.

Bu dosyadaki fonksiyonlar ağa çıkmaz; test edilebilir saf mantık içerir.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from statistics import median

try:  # GitHub Actions'ta requirements.txt ile kurulur
    import holidays as _holidays
except ImportError:  # yerel testte yoksa tatil bonusu kapalı
    _holidays = None


# ---------------------------------------------------------------- yardımcılar

def parse_day(iso: str | None) -> date | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()


def is_direct(row: dict) -> bool:
    if row.get("transfers", 0) != 0:
        return False
    if row.get("return_at") and row.get("return_transfers", 0) != 0:
        return False
    return True


def city_allowed(code: str, country: str, dest_cfg: dict) -> bool:
    if code in (dest_cfg.get("always_block") or []):
        return False
    if code in (dest_cfg.get("always_allow") or []):
        return True
    if country == "TR":  # yurt içi
        return False
    return country in set(dest_cfg.get("allowed_countries") or [])


def season_for(code: str, day: date, seasons: list[dict]) -> str | None:
    """Kalkış tarihi bir sezon aralığına düşüyorsa ve şehir listedeyse sezon adını döndür."""
    md = (day.month, day.day)
    for s in seasons:
        if code not in s.get("cities", []):
            continue
        sm, sd = map(int, s["start"].split("-"))
        em, ed = map(int, s["end"].split("-"))
        start, end = (sm, sd), (em, ed)
        inside = start <= md <= end if start <= end else (md >= start or md <= end)
        if inside:
            return s["name"]
    return None


def holiday_names(start: date, end: date) -> list[str]:
    """Seyahat aralığına (bir gün önce dahil) denk gelen Türkiye resmi tatilleri."""
    if _holidays is None:
        return []
    tr = _holidays.Turkey(years=range(start.year, end.year + 1))
    names = []
    d = start - timedelta(days=1)
    while d <= end:
        if d in tr and tr[d] not in names:
            names.append(tr[d])
        d += timedelta(days=1)
    return names


# ---------------------------------------------------------------- veri modeli

@dataclass
class Deal:
    city: str
    city_name: str
    country: str
    format: str                 # "rt" gidiş-dönüş, "ow" tek yön
    out_date: str
    ret_date: str | None
    nights: int | None
    price: float                # rt ise gidiş-dönüş toplamı
    one_way_price: float        # aynı rotanın en ucuz tek yön fiyatı (karşılaştırma için)
    median_one_way: float
    discount: float             # 0.25 = normal fiyattan %25 ucuz (veri azsa temkinli küçültülür)
    samples: int                # normal fiyatın kaç fiyat örneğinden hesaplandığı
    airline: str
    airline_name: str
    origin_airport: str
    destination_airport: str
    duration_min: int | None
    season: str | None = None
    holidays: list[str] = field(default_factory=list)
    score: float = 0.0
    link: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- ana mantık

def group_one_way(rows: list[dict], today: date, s: dict) -> dict[str, list[dict]]:
    """Tek yön, direkt satırları şehir koduna göre grupla; tarih penceresi dışını at.
    Aynı şehir+tarih için en ucuz satırı tut (farklı pazarlardan gelenler birleşir)."""
    lo = today + timedelta(days=s["scan"]["min_days_ahead"])
    hi = today + timedelta(days=s["scan"]["max_days_ahead"])
    best: dict[tuple[str, date], dict] = {}
    for r in rows:
        if not is_direct(r):
            continue
        d = parse_day(r.get("departure_at"))
        if d is None or not (lo <= d <= hi):
            continue
        key = (r["destination"], d)
        if key not in best or r["price"] < best[key]["price"]:
            best[key] = r
    grouped: dict[str, list[dict]] = {}
    for (code, _), r in best.items():
        grouped.setdefault(code, []).append(r)
    return grouped


def best_round_trip(rows: list[dict], today: date, s: dict) -> dict | None:
    """İki bacağı da direkt, gece sayısı aralıkta, en ucuz gidiş-dönüş."""
    lo = today + timedelta(days=s["scan"]["min_days_ahead"])
    mn, mx = s["round_trip"]["min_nights"], s["round_trip"]["max_nights"]
    best = None
    for r in rows:
        if not is_direct(r) or not r.get("return_at"):
            continue
        out, ret = parse_day(r["departure_at"]), parse_day(r["return_at"])
        if out is None or ret is None or out < lo:
            continue
        nights = (ret - out).days
        if not (mn <= nights <= mx):
            continue
        if best is None or r["price"] < best["price"]:
            best = r
    return best


def build_deal(
    code: str,
    one_way_rows: list[dict],
    rt_row: dict | None,
    cities: dict,
    dest_cfg: dict,
    seasons: list[dict],
    s: dict,
) -> Deal | None:
    prices = [r["price"] for r in one_way_rows]
    if len(prices) < 3:
        return None  # normal fiyatı kestirmek için yeterli veri yok
    med = median(prices)
    cheapest = min(one_way_rows, key=lambda r: r["price"])
    info = cities.get(code, {})
    name = (dest_cfg.get("city_names_tr") or {}).get(code) or info.get("name") or code
    airlines = s.get("airlines") or {}

    ratio = s["round_trip"]["max_ratio_to_one_way"]
    use_rt = rt_row is not None and rt_row["price"] <= cheapest["price"] * ratio
    notes = []
    if rt_row is None:
        notes.append("İki yönü direkt uygun gidiş-dönüş bulunamadı → tek yön")
    elif not use_rt:
        notes.append(
            f"Gidiş-dönüş {rt_row['price']:.0f} > tek yön {cheapest['price']:.0f} × {ratio} → tek yön"
        )

    if use_rt:
        row = rt_row
        out, ret = parse_day(row["departure_at"]), parse_day(row["return_at"])
        nights = (ret - out).days
        per_leg = row["price"] / 2
        price = row["price"]
        dur = row.get("duration_to")
    else:
        row = cheapest
        out, ret, nights = parse_day(row["departure_at"]), None, None
        per_leg = row["price"]
        price = row["price"]
        dur = row.get("duration_to") or row.get("duration")

    raw = max(0.0, 1 - per_leg / med) if med else 0.0
    # Az fiyat örneği varsa "normal fiyat" güvenilmez → indirimi orantılı küçült
    full = s["scoring"].get("full_confidence_samples", 10)
    discount = raw * min(1.0, len(prices) / full)
    if discount < raw:
        notes.append(f"Az veri ({len(prices)} fiyat): indirim %{raw*100:.0f} → %{discount*100:.0f}")
    link = row.get("link")
    return Deal(
        city=code,
        city_name=name,
        country=info.get("country", ""),
        format="rt" if use_rt else "ow",
        out_date=out.isoformat(),
        ret_date=ret.isoformat() if ret else None,
        nights=nights,
        price=round(price),
        one_way_price=round(cheapest["price"]),
        median_one_way=round(med),
        discount=round(discount, 3),
        samples=len(prices),
        airline=row.get("airline", ""),
        airline_name=airlines.get(row.get("airline", ""), row.get("airline", "")),
        origin_airport=row.get("origin_airport", ""),
        destination_airport=row.get("destination_airport", ""),
        duration_min=dur,
        season=season_for(code, out, seasons),
        holidays=holiday_names(out, ret or out),
        link=("https://www.aviasales.com" + link) if link else None,
        notes=notes,
    )


def score_deal(deal: Deal, today: date, history: list[dict], s: dict) -> Deal | None:
    """Puan hesapla; kural dışı kalırsa None döndür."""
    sc = s["scoring"]
    out = date.fromisoformat(deal.out_date)

    for h in history:
        days = (today - date.fromisoformat(h["date"])).days
        if h.get("city") == deal.city and days < sc["recent_city_days"]:
            return None

    score = deal.discount * 100
    if deal.discount < sc["min_discount"]:
        deal.notes.append(f"İndirim %{deal.discount*100:.0f}, eşik %{sc['min_discount']*100:.0f}")
        score -= 50  # listede kalsın ama dibe insin
    if deal.season:
        score += sc["season_bonus"]
    if deal.holidays:
        score += sc["holiday_bonus"]
    lead = (out - today).days
    lo, hi = sc["sweet_spot_days"]
    if lo <= lead <= hi:
        score += sc["sweet_spot_bonus"]
    if deal.country in set(sc.get("visa_countries") or []) and lead < sc.get("visa_min_days", 0):
        score -= sc.get("visa_short_notice_penalty", 0)
        deal.notes.append(f"Vize gerekli, kalkışa {lead} gün var")
    for h in history:
        days = (today - date.fromisoformat(h["date"])).days
        if h.get("country") == deal.country and days < sc["recent_country_days"]:
            score -= sc["recent_country_penalty"]
            break
    deal.score = round(score, 1)
    return deal


def rank(deals: list[Deal]) -> list[Deal]:
    return sorted(deals, key=lambda d: d.score, reverse=True)
