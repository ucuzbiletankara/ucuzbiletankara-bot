"""Claude API ile 10 slaytlık carousel metnini ve caption'ı üretir.

- Model: claude-sonnet-5-5 (config/settings.yaml → content.model ile değiştirilebilir)
- Web arama aracı: etkinlik tarihleri, açılış saatleri gibi değişebilen bilgileri
  seyahat tarihine göre doğrulamak için.
"""
from __future__ import annotations

import json
import re
from datetime import date

import requests

API = "https://api.anthropic.com/v1/messages"

SCHEMA_EXAMPLE = {
    "airport_name": "Varış havalimanının Türkçe kısa adı, en fazla 22 karakter (ör. 'Viyana Schwechat')",
    "city_en": "Şehrin İngilizce adı (fotoğraf aramaları için, ör. 'Vienna')",
    "cover": {"subtitle": "≤ 42 karakter", "photo_query": "İngilizce, dikey kapak fotoğrafı araması"},
    "why_now": {
        "title": "≤ 24 karakter", "subtitle": "≤ 70 karakter",
        "photo_query": "İngilizce", "photo_label": "Türkçe, ≤ 40 karakter",
        "rows": [{"name": "≤ 22 karakter", "detail": "≤ 32 karakter"}],
        "tip": "≤ 95 karakter",
    },
    "sights_1": {"title": "≤ 24 karakter", "items": [{"name": "≤ 20 karakter", "desc": "≤ 110 karakter", "photo_query": "İngilizce"}]},
    "sights_2": {"title": "≤ 24 karakter", "items": "sights_1 ile aynı yapı, 4 öğe"},
    "food": {"title": "≤ 24 karakter",
             "items": [{"name": "≤ 22 karakter", "desc": "≤ 110 karakter", "photo_query": "İngilizce"}],
             "note_title": "≤ 22 karakter", "note": "≤ 120 karakter"},
    "eat": {"title": "≤ 24 karakter", "photo_query": "İngilizce",
            "items": [{"tag": "≤ 10 karakter", "name": "≤ 24 karakter", "desc": "≤ 70 karakter"}],
            "tip": "≤ 100 karakter"},
    "stay": {"title": "≤ 24 karakter", "photo_query": "İngilizce",
             "items": [{"badge": "≤ 4 karakter (semt no veya kısa etiket)", "name": "≤ 22 karakter", "desc": "≤ 75 karakter"}],
             "footnote": "≤ 70 karakter veya boş"},
    "transport": {"title": "≤ 24 karakter", "photo_query": "İngilizce",
                  "cards": [{"label": "≤ 10 karakter", "name": "≤ 7 karakter", "desc": "≤ 50 karakter"}],
                  "city_items": [{"bold": "≤ 32 karakter", "text": "≤ 85 karakter"}]},
    "tips": {"title": "≤ 24 karakter", "items": [{"title": "≤ 16 karakter", "text": "≤ 85 karakter"}]},
    "closing": {"title": "≤ 18 karakter", "subtitle": "≤ 60 karakter"},
    "caption": "Instagram açıklaması (kurallara bak)",
    "hashtags": ["10-15 adet, # işareti olmadan"],
    "sources": ["Doğrulama için kullandığın sayfa adresleri"],
}

COUNTS = {"why_now.rows": (3, 5), "sights_1.items": (4, 4), "sights_2.items": (4, 4),
          "food.items": (4, 4), "eat.items": (4, 4), "stay.items": (4, 4),
          "transport.cards": (3, 3), "transport.city_items": (2, 2), "tips.items": (6, 6)}

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
         "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def _fmt(d: str | None) -> str:
    if not d:
        return "-"
    x = date.fromisoformat(d)
    return f"{x.day} {AYLAR[x.month - 1]} {x.year}"


def build_prompt(pick: dict, today: date) -> str:
    rt = pick["format"] == "rt"
    mode = pick.get("mode", "firsat")
    visa = pick.get("country") in {"AT", "BE", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IS", "IT", "LV",
                                   "LI", "LT", "LU", "MT", "NL", "NO", "PL", "PT", "SK", "SI", "ES", "SE", "CH",
                                   "HR", "BG", "RO", "GB", "IE", "CY"}
    price = f"{pick['price']:,.0f}".replace(",", ".")
    flight = f"""- Rota: Ankara Esenboğa (ESB) → {pick['city_name']} ({pick['destination_airport']}), aktarmasız
- Format: {'gidiş-dönüş, iki yön de direkt' if rt else 'tek yön (dönüş ayrıca alınır)'}
- Gidiş: {_fmt(pick['out_date'])}{f" · Dönüş: {_fmt(pick['ret_date'])} ({pick['nights']} gece)" if rt else ''}
- Havayolu: {pick['airline_name']}
- Fiyat: {price} TL{' (gidiş-dönüş toplam)' if rt else ' (tek yön)'}, kişi başı, 'den başlayan
- Ülke kodu: {pick.get('country')} · Sezon/etkinlik etiketi: {pick.get('season') or 'yok'} · Resmi tatil: {', '.join(pick.get('holidays') or []) or 'yok'}"""

    return f"""Bugün {_fmt(today.isoformat())}. Sen @ucuzbiletankara Instagram sayfasının içerik editörüsün.
Sayfa Ankara'dan aktarmasız, uygun fiyatlı yurt dışı uçuşları ve o şehrin kısa seyahat rehberini paylaşıyor.
Hedef kitle: Ankara'da yaşayan, Türkçe konuşan gezginler.

UÇUŞ (bu bilgiler kesin, DEĞİŞTİRME, uydurma fiyat yazma):
{flight}

GÖREV: Bu uçuş için 10 slaytlık carousel metnini ve Instagram açıklamasını hazırla.
Slaytlar: kapak, neden şimdi, gezilecek yerler I, gezilecek yerler II, ne yenir, nerede yenir, nerede kalınır, ulaşım, ipuçları, kapanış.

KURALLAR
1. "Neden şimdi?" slaytı SEYAHAT TARİHİNE ({_fmt(pick['out_date'])}) göre yazılır. O tarihte gerçekten olan bir
   etkinlik/sezon varsa (festival, Noel pazarı, sergi, mevsim) onu anlat. Etkinliğin o tarihte açık olduğunu
   web aramasıyla doğrula; seyahat tarihinde kapanmış ya da başlamamış etkinliği ÖNERME. Etkinlik yoksa
   mevsimin avantajını anlat (ör. sakin sezon, hava, fiyatlar). rows: etkinlik adları + tarih/saat ya da
   o döneme özel 3-5 kısa madde.
2. Açılış saatleri, tarihler, ulaşım süreleri gibi değişebilen bilgileri web aramasıyla kontrol et. Emin
   olamadığın sayıyı yazma; genel ifade kullan. Fiyat (TL/€) yazma, değişir.
3. Mekân önerileri köklü ve hâlâ açık yerler olsun (gerekirse doğrula).
4. Domuz eti ve alkol içeren yemeklerde kibarca belirt; food.note bu tür bir hassasiyet ya da pratik bir
   uyarı olsun.
5. {'Türk vatandaşları için vize gerekir; ipuçlarından biri vize randevusunu erken almak olsun.' if visa else 'Vize durumunu doğrula ve ipuçlarında doğru bilgiyi ver (vizesiz/e-vize/kapıda vize).'}
6. Dil: sade, samimi, doğal Türkçe. Slaytlarda emoji YOK. Kaynaklardan cümle kopyalama, kendi cümlelerinle yaz.
7. Karakter sınırları tasarım için zorunlu; aşma. Öğe sayıları: why_now.rows 3-5, sights 4+4, food 4,
   eat 4, stay 4, transport.cards 3 (havalimanından şehre seçenekler), transport.city_items 2, tips 6.
8. photo_query'ler İngilizce ve somut olsun (ör. "stephansdom vienna", "wiener schnitzel plate"); aynı
   sorguyu iki kez kullanma. Kapak sorgusu şehri ve sezonu en iyi anlatan dikey bir fotoğraf için.
9. closing.subtitle'da "Bilet linki profilde" geçsin.
10. CAPTION: 900-1500 karakter. Yapı: güçlü ilk satır (rota + fiyat){'' if mode == 'firsat' else ' ("fırsat" kelimesini KULLANMA, "Ankara’dan direkt" dilini kullan)'};
    uçuş özeti (tarih, havayolu, aktarmasız, fiyat, {'gidiş-dönüş' if rt else 'tek yön'}); neden şimdi (1-2 cümle);
    3-4 maddelik "kaçırma" listesi (emoji madde imi olabilir); kaydet/gönder çağrısı; "Bilet linki profilde";
    son satırda: "Fiyatlar paylaşım anında bulunan en düşük fiyattır, değişebilir." Hashtag'leri caption'a
    yazma, ayrı listede ver (Türkçe ve İngilizce karışık, şehir + ankara + seyahat temalı).

ÇIKTI: Araştırmanı bitirdikten sonra SADECE aşağıdaki şemaya uyan geçerli JSON'u <json> ve </json> etiketleri
arasında ver. Şema (değerler açıklamadır, gerçek içerikle doldur):
{json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False, indent=1)}
"""


def _call(api_key: str, model: str, prompt: str, use_search: bool, max_searches: int) -> dict:
    body = {"model": model, "max_tokens": 8000,
            "messages": [{"role": "user", "content": prompt}]}
    if use_search:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}]
    r = requests.post(API, json=body, timeout=600, headers={
        "x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    if r.status_code >= 400:
        raise RuntimeError(f"Claude API {r.status_code}: {r.text[:500]}")
    return r.json()


def _extract_json(resp: dict) -> dict:
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    m = re.search(r"<json>\s*(\{.*\})\s*</json>", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def _get(d: dict, path: str):
    for k in path.split("."):
        d = d[k]
    return d


def validate(c: dict) -> list[str]:
    """Şema ve öğe sayısı kontrolü. Uzunlukları burada kırpmıyoruz; şablon taşmayı ayrıca kontrol ediliyor."""
    problems = []
    for path, (lo, hi) in COUNTS.items():
        try:
            n = len(_get(c, path))
        except (KeyError, TypeError):
            problems.append(f"{path} eksik")
            continue
        if not lo <= n <= hi:
            problems.append(f"{path}: {n} öğe (beklenen {lo}-{hi})")
    for key in ("airport_name", "cover", "why_now", "closing", "caption", "hashtags"):
        if key not in c:
            problems.append(f"{key} eksik")
    return problems


def fit_counts(c: dict) -> dict:
    """Fazla öğeleri kırp (eksikler validate'te yakalanır)."""
    for path, (_, hi) in COUNTS.items():
        try:
            parent_path, key = path.rsplit(".", 1)
            parent = _get(c, parent_path)
            parent[key] = parent[key][:hi]
        except (KeyError, TypeError):
            pass
    return c


def generate(pick: dict, api_key: str, today: date, model: str = "claude-sonnet-5-5",
             use_search: bool = True, max_searches: int = 6) -> tuple[dict, dict]:
    """(içerik, kullanım bilgisi) döndürür."""
    prompt = build_prompt(pick, today)
    try:
        resp = _call(api_key, model, prompt, use_search, max_searches)
    except RuntimeError as e:
        if use_search and "web search" in str(e).lower():
            resp = _call(api_key, model, prompt, False, 0)  # arama kapalıysa aramasız dene
        else:
            raise
    content = fit_counts(_extract_json(resp))
    problems = validate(content)
    if problems:
        fix = prompt + "\n\nÖNCEKİ ÇIKTINDA ŞU SORUNLAR VARDI, DÜZELTEREK TEKRAR VER: " + "; ".join(problems)
        resp = _call(api_key, model, fix, False, 0)
        content = fit_counts(_extract_json(resp))
        problems = validate(content)
        if problems:
            raise RuntimeError("İçerik şemaya uymuyor: " + "; ".join(problems))
    usage = resp.get("usage", {})
    return content, usage


def shorten_request(content: dict, overflow: list[str], pick: dict, api_key: str, model: str) -> dict:
    """Şablonda taşan slaytlar için metni kısaltmasını iste."""
    prompt = (
        "Aşağıdaki carousel JSON'unda bazı slaytların metni tasarıma sığmadı: " + "; ".join(overflow) +
        ". İlgili slaytlardaki metinleri yaklaşık %20 kısalt, anlamı koru, yapıyı ve diğer alanları aynen bırak. "
        "Sadece JSON'u <json></json> arasında ver.\n\n" + json.dumps(content, ensure_ascii=False)
    )
    resp = _call(api_key, model, prompt, False, 0)
    return fit_counts(_extract_json(resp))
