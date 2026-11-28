"""Ağa çıkmadan sahte verilerle tarama mantığını dener.

Çalıştırma: python -m tests.test_scan
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from bot import scan

TODAY = date(2026, 11, 26)
CITIES = {
    "VIE": {"name": "Vienna", "country": "AT"},
    "BER": {"name": "Berlin", "country": "DE"},
    "DXB": {"name": "Dubai", "country": "AE"},
    "JED": {"name": "Jeddah", "country": "SA"},   # kural dışı
    "IST": {"name": "Istanbul", "country": "TR"},  # yurt içi
    "ECN": {"name": "Ercan", "country": "TR"},     # KKTC, özel izin
    "TBS": {"name": "Tbilisi", "country": "GE"},
}
NORMAL = {"VIE": 4500, "BER": 4000, "DXB": 7000, "JED": 6000, "IST": 1500, "ECN": 2500, "TBS": 3500}


def iso(d: date, hh: int = 9) -> str:
    return f"{d.isoformat()}T{hh:02d}:00:00+03:00"


class FakeClient:
    calls = 0

    def prices_for_dates(self, origin, departure_at, destination=None, return_at=None,
                         one_way=True, direct=True, market="tr", limit=1000):
        self.calls += 1
        rnd = random.Random(f"{departure_at}{destination}{return_at}{market}")
        y, m = map(int, departure_at.split("-"))
        days = [date(y, m, d) for d in range(1, 29)]
        out = []
        if destination and destination not in NORMAL:
            return out
        for code in ([destination] if destination else ["VIE", "IST", "JED"]):
            for d in days:
                p = NORMAL[code] * rnd.uniform(0.85, 1.3)
                if code == "VIE" and d == date(2026, 12, 12):
                    p = 1900  # belirgin fırsat
                row = {
                    "origin": "ANK", "destination": code, "origin_airport": "ESB",
                    "destination_airport": code, "price": round(p), "airline": "PC",
                    "departure_at": iso(d), "transfers": 0, "duration_to": 165,
                    "link": f"/search/ESB{d:%d%m}{code}1", "flight_number": "1673",
                }
                if not one_way:
                    ret = d + timedelta(days=rnd.choice([1, 3, 4, 9]))
                    row["return_at"] = iso(ret, 18)
                    row["return_transfers"] = rnd.choice([0, 0, 1])
                    row["duration_back"] = 175
                    row["price"] = round(p * rnd.uniform(1.7, 2.6))
                out.append(row)
        return out


def main():
    tz = {c: "Europe/Vienna" for c in ["VIE", "BER"]} | {"DXB": "Asia/Dubai", "TBS": "Asia/Tbilisi", "ECN": "Asia/Nicosia"}
    scan.load_history = lambda: []  # gerçek paylaşım geçmişi testi etkilemesin
    res = scan.run(FakeClient(), CITIES, today=TODAY, airports_tz=tz)
    codes = [d["city"] for d in res["deals"]]
    assert "JED" in res["excluded_by_rules"], "Cidde elenmeliydi"
    assert "IST" in res["excluded_by_rules"], "Yurt içi elenmeliydi"
    assert "ECN" in codes, "Ercan özel izinle listede olmalıydı"
    assert "TBS" in codes, "Gürcistan izinli olmalıydı"
    assert res["deals"][0]["city"] == "VIE", "En iyi fırsat Viyana olmalıydı"
    assert "BER" in codes and "DXB" in codes, "Toplu sorguda görünmeyen bilinen rotalar ayrıca sorgulanmalıydı"
    for d in res["deals"]:
        assert date.fromisoformat(d["out_date"]) >= TODAY + timedelta(days=5)
        if d["format"] == "rt":
            assert 2 <= d["nights"] <= 7
            assert d["price"] <= d["one_way_price"] * 2.3
    assert res["pick"]["city"] == "VIE" and res["pick"]["mode"] == "firsat"
    p = res["pick"]
    assert p["out_dep_time"] == "09:00" and p["out_arr_time"] == "09:45", (p["out_dep_time"], p["out_arr_time"])
    assert p["flight_number"] == "PC 1673"
    rts = [d for d in res["deals"] if d["format"] == "rt"]
    assert rts and all(d["ret_dep_time"] == "18:00" for d in rts), [d["ret_dep_time"] for d in rts]
    print(scan.to_markdown(res, CITIES))
    print("TÜM KONTROLLER GEÇTİ")


if __name__ == "__main__":
    main()
