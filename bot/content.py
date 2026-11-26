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
2. En fazla 3 web araması yapabilirsin; önceliği etkinlik tarihlerine ver, sonra ulaşım ve açılış saatleri.
   Açılış saatleri, tarihler, ulaşım süreleri gibi değişebilen bilgileri web aramasıyla kontrol et. Emin
   olamadığın sayıyı yazma; genel ifade kullan. Fiyat (TL/€) yazma, değişir.
3. Mekân önerileri köklü ve hâlâ açık yerler olsun (gerekirse doğrula).
4. Domuz eti ve alkol içeren yemeklerde kibarca belirt; food.note bu tür bir hassasiyet ya da pratik bir
   uyarı olsun.
5. {'Türk vatandaşları için vize gerekir; ipuçlarından biri vize randevusunu erken almak olsun.' if visa else 'Vize durumunu doğrula ve ipuçlarında doğru bilgiyi ver (vizesiz/e-vize/kapıda vize).'}
6. Dil: sade, samimi, doğal Türkçe; okura "sen" diye hitap et ("kaçırma", "rezervasyon yap"), "siz" ve
   "-yoruz" (biz) dili KULLANMA. Slaytlarda emoji YOK. Kaynaklardan cümle kopyalama, kendi cümlelerinle yaz.
   desc/text alanlarını sınıra yakın doldur (sınırın en az %70'i) ve somut bilgi ver: ne var, neden gidilir,
   pratik bir detay (saat, kapalı gün, en iyi zaman, yakınındaki yer). "Güzel bir yer" gibi boş ifadeler yazma.
7. Karakter sınırları tasarım için zorunlu; aşma. Öğe sayıları: why_now.rows 3-5, sights 4+4, food 4,
   eat 4, stay 4, transport.cards 3 (havalimanından şehre seçenekler), transport.city_items 2, tips 6.
8. photo_query'ler İngilizce, kısa (2-4 kelime) ve somut olsun; İLK KELİME öznenin kendi adı olsun
   (ör. "stephansdom vienna", "maultaschen", "markthalle stuttgart"). Yemeklerde sadece yemeğin adı yeterli.
   Aynı sorguyu iki kez kullanma. Kapak sorgusu şehri ve sezonu anlatan dikey bir fotoğraf için
   (ör. "stuttgart christmas market").
11. Slayt başlıkları (title) üstteki etiketi tekrar etmesin ("Ne yenir?", "Ulaşım" gibi değil);
   şehre özgü, merak uyandıran kısa başlıklar yaz (ör. "Viyana'nın tadı", "Havalimanından şehre").
9. closing.subtitle'da "Bilet linki profilde" geçsin.
10. CAPTION: 900-1500 karakter. Yapı: güçlü ilk satır (rota + fiyat){'' if mode == 'firsat' else ' ("fırsat" kelimesini KULLANMA, "Ankara’dan direkt" dilini kullan)'};
    uçuş özeti (tarih, havayolu, aktarmasız, fiyat, {'gidiş-dönüş' if rt else 'tek yön'}); neden şimdi (1-2 cümle);
    3-4 maddelik "kaçırma" listesi (emoji madde imi olabilir); kaydet/gönder çağrısı; "Bilet linki profilde";
    son satırda: "Fiyatlar paylaşım anında bulunan en düşük fiyattır, değişebilir." Hashtag'leri caption'a
    yazma, ayrı listede ver (Türkçe ve İngilizce karışık, şehir + ankara + seyahat temalı).

ÇIKTI: Araştırmanı bitirdikten sonra SADECE aşağıdaki şemaya uyan geçerli JSON'u <json> ve </json> etiketleri
arasında ver. JSON'u girintisiz, tek satır (minified) yaz; araştırma sırasında uzun açıklama yazma. Şema (değerler açıklamadır, gerçek içerikle doldur):
{json.dumps(SCHEMA_EXAMPLE, ensure_ascii=False, indent=1)}
"""


LAST_RAW: list[dict] = []  # hata ayıklama için son ham cevaplar


def _post(api_key: str, body: dict) -> dict:
    r = requests.post(API, json=body, timeout=600, headers={
        "x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    if r.status_code >= 400:
        raise RuntimeError(f"Claude API {r.status_code}: {r.text[:500]}")
    return r.json()


EFFORT = "medium"
THINKING = "disabled"

PRICES = {  # $ / milyon token: (giriş, çıkış); Haiku 100k üstü istekte pahalı kademe
    "claude-haiku-5-5": [(100_000, 0.10, 0.50), (10**12, 0.50, 2.50)],
    "claude-sonnet-5-5": [(10**12, 2.0, 10.0)],
    "claude-opus-5-5": [(10**12, 4.0, 20.0)],
}


def request_cost(model: str, usage: dict) -> float:
    inp = usage.get("input_tokens", 0) + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)
    out = usage.get("output_tokens", 0)
    for limit, pi, po in PRICES.get(model, [(10**12, 2.0, 10.0)]):
        if inp <= limit:
            break
    searches = (usage.get("server_tool_use") or {}).get("web_search_requests", 0)
    return inp / 1e6 * pi + out / 1e6 * po + searches * 0.01


def _call(api_key: str, model: str, prompt: str, use_search: bool, max_searches: int) -> dict:
    """Mesaj gönder; web araması uzun sürüp cevap 'pause_turn' ile yarıda kalırsa devam ettir.
    Dönen sözlükte tüm turların içerik blokları birleştirilmiş olarak 'content' alanındadır."""
    messages = [{"role": "user", "content": prompt}]
    body = {"model": model, "max_tokens": 20000, "messages": messages,
            "output_config": {"effort": EFFORT}}
    if THINKING:
        body["thinking"] = {"type": THINKING}
    if use_search:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": max_searches}]
    all_blocks, usage, cost = [], {}, 0.0
    for _ in range(6):
        resp = _post(api_key, body)
        LAST_RAW.append(resp)
        blocks = resp.get("content", [])
        all_blocks += blocks
        u = resp.get("usage") or {}
        cost += request_cost(model, u)  # her istek kendi kademesinden faturalanır
        for k, v in u.items():
            if isinstance(v, (int, float)):
                usage[k] = usage.get(k, 0) + v
        searches = (u.get("server_tool_use") or {}).get("web_search_requests", 0)
        usage["web_searches"] = usage.get("web_searches", 0) + searches
        usage["max_prompt_tokens"] = max(usage.get("max_prompt_tokens", 0), u.get("input_tokens", 0))
        stop = resp.get("stop_reason")
        if stop == "pause_turn":
            messages.append({"role": "assistant", "content": blocks})
            continue
        if stop == "max_tokens":
            raise RuntimeError("Claude cevabı uzunluk sınırına takıldı (max_tokens).")
        break
    usage["estimated_cost_usd"] = round(cost, 4)
    return {"content": all_blocks, "usage": usage, "stop_reason": resp.get("stop_reason")}


def _extract_json(resp: dict) -> dict:
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    m = re.search(r"<json>\s*(\{.*\})\s*</json>", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    if not raw.strip():
        raise ValueError(f"Cevapta JSON bulunamadı (stop_reason={resp.get('stop_reason')}). "
                         f"Metin başı: {text[:300]!r}")
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


KICKER_TITLES = {
    "why_now": ("neden şimdi", "{city} şimdi güzel"),
    "sights_1": ("gezilecek yerler", "{city} turu"),
    "sights_2": ("gezilecek yerler", "Biraz daha {city}"),
    "food": ("ne yenir", "{city} lezzetleri"),
    "eat": ("nerede yenir", "Masaya otur"),
    "stay": ("nerede kalınır", "Hangi semtte kalmalı?"),
    "transport": ("ulaşım", "Havalimanından şehre"),
    "tips": ("ipuçları", "Gitmeden önce"),
}


def fix_titles(c: dict, city: str) -> dict:
    """Başlık üstteki etiketi tekrar ediyorsa şehre özgü yedek başlık koy."""
    for sec, (kicker, fallback) in KICKER_TITLES.items():
        t = (c.get(sec) or {}).get("title", "")
        if not t or kicker in t.lower().replace("?", "").replace("i̇", "i"):
            c.setdefault(sec, {})["title"] = fallback.format(city=city)
    return c


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


def generate(pick: dict, api_key: str, today: date, model: str = "claude-haiku-5-5",
             use_search: bool = True, max_searches: int = 4, effort: str = "medium",
             thinking: str | None = "disabled") -> tuple[dict, dict]:
    """(içerik, kullanım bilgisi) döndürür."""
    global EFFORT, THINKING
    EFFORT, THINKING = effort, thinking
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
    content = fix_titles(content, pick["city_name"])
    usage = resp.get("usage", {})
    usage["estimated_cost_usd"] = round(sum(
        request_cost(model, r.get("usage") or {}) for r in LAST_RAW), 4)
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
