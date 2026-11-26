"""Travelpayouts / Aviasales Data API istemcisi.

Kullanılan uç nokta: /aviasales/v3/prices_for_dates
Veriler önbellekten gelir (gerçek zamanlı değil); bu yüzden postlarda
"fiyatlar anlık değişebilir" uyarısı bulunur.
"""
from __future__ import annotations

import time

import requests

BASE = "https://api.travelpayouts.com"
DATA_URL = BASE + "/data/en/cities.json"


class TravelpayoutsError(RuntimeError):
    pass


class Client:
    def __init__(self, token: str, currency: str = "try", pause: float = 0.4):
        self.token = token
        self.currency = currency
        self.pause = pause
        self.session = requests.Session()
        self.session.headers.update(
            {"X-Access-Token": token, "Accept-Encoding": "gzip, deflate"}
        )
        self.calls = 0

    def _get(self, path: str, params: dict) -> dict:
        for attempt in range(3):
            self.calls += 1
            r = self.session.get(BASE + path, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 401:
                raise TravelpayoutsError(
                    "Travelpayouts token'ı reddedildi (401). TRAVELPAYOUTS_TOKEN doğru mu, "
                    "Aviasales programına katıldın mı?"
                )
            r.raise_for_status()
            time.sleep(self.pause)
            body = r.json()
            if body.get("success") is False:
                raise TravelpayoutsError(f"API hatası: {body.get('error')}")
            return body
        raise TravelpayoutsError("Çok fazla istek (429); daha sonra tekrar dene.")

    def prices_for_dates(
        self,
        origin: str,
        departure_at: str,
        destination: str | None = None,
        return_at: str | None = None,
        one_way: bool = True,
        direct: bool = True,
        market: str = "tr",
        limit: int = 1000,
    ) -> list[dict]:
        params = {
            "origin": origin,
            "departure_at": departure_at,
            "one_way": str(one_way).lower(),
            "direct": str(direct).lower(),
            "market": market,
            "currency": self.currency,
            "sorting": "price",
            "limit": limit,
            "page": 1,
        }
        if destination:
            params["destination"] = destination
        if return_at:
            params["return_at"] = return_at
        body = self._get("/aviasales/v3/prices_for_dates", params)
        rows = body.get("data") or []
        for row in rows:
            row["_market"] = market
        return rows


def load_cities() -> dict[str, dict]:
    """Şehir kodu -> {name, country_code} sözlüğü. Token gerektirmez."""
    r = requests.get(DATA_URL, timeout=60, headers={"Accept-Encoding": "gzip, deflate"})
    r.raise_for_status()
    out = {}
    for c in r.json():
        code = c.get("code")
        if code:
            out[code] = {"name": c.get("name") or code, "country": c.get("country_code") or ""}
    return out


def load_airport_timezones() -> dict[str, str]:
    """Havalimanı ve şehir kodu -> IANA saat dilimi (varış saatini yerel saate çevirmek için)."""
    r = requests.get(BASE + "/data/en/airports.json", timeout=60, headers={"Accept-Encoding": "gzip, deflate"})
    r.raise_for_status()
    out = {}
    for a in r.json():
        tz = a.get("time_zone")
        if not tz:
            continue
        if a.get("code"):
            out[a["code"]] = tz
        if a.get("city_code"):
            out.setdefault(a["city_code"], tz)
    return out
