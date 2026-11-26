"""3 sabit post (Biz kimiz? / Neden biz? / Nasıl kullanılır?) – 1080×1350, günlük postlarla aynı kimlik."""
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)
SG = Path("/home/claude/sabit/gf/ofl/spacegrotesk/SpaceGrotesk[wght].ttf").as_uri()
DISC = "Tanıtım · Aviasales"
DISC_LINE = ("Bilet ve tur satışı yapmıyoruz; fiyatları bulup gösteriyoruz. "
             "Tanıtım · Aviasales: profildeki bilet linki satış ortaklığı (komisyon) linkidir.")

CSS = f"""
@font-face{{font-family:'Space Grotesk';src:url('{SG}') format('truetype');font-weight:300 700}}
:root{{--navy:#0F1E33;--navy2:#17283F;--line:#2A3D5A;--y:#FFC533;--cream:#F5F3EE;--muted:#9FB0C8;--soft:#C9D3E1;--ink2:#4A5A72}}
*{{box-sizing:border-box}}
body{{margin:0;width:1080px;height:1350px;overflow:hidden;font-family:Inter,sans-serif;background:var(--navy);color:var(--cream)}}
.sg{{font-family:'Space Grotesk',Inter,sans-serif}}
.slide{{width:1080px;height:1350px;padding:72px 80px 80px;display:flex;flex-direction:column;gap:36px;position:relative;overflow:hidden}}
.top{{display:flex;justify-content:space-between;align-items:center}}
.brand{{font-family:'Space Grotesk';font-weight:700;font-size:34px;letter-spacing:-.5px}}
.brand span{{color:var(--y)}}
.count{{font-family:'Space Grotesk';font-weight:500;font-size:26px;color:var(--muted)}}
.kicker{{color:var(--y);font-weight:700;font-size:26px;letter-spacing:2.5px}}
.h1{{font-family:'Space Grotesk';font-weight:700;font-size:76px;line-height:1.02;letter-spacing:-2.5px}}
.sub{{font-size:28px;line-height:1.4;color:var(--soft)}}
.badge{{background:var(--cream);color:var(--navy);font-size:21px;font-weight:700;padding:7px 14px;border-radius:8px}}
.card{{background:var(--navy2);border-radius:26px;padding:26px 40px;display:flex;gap:32px;align-items:center;flex:1}}
.num{{font-family:'Space Grotesk';font-weight:700;font-size:66px;line-height:1;color:var(--y);flex:none;width:100px}}
.ct{{font-weight:700;font-size:40px;line-height:1.15;margin-bottom:8px}}
.cd{{font-size:28px;line-height:1.45;color:var(--soft)}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;grid-auto-rows:1fr;gap:22px;flex:1}}
.g{{background:var(--navy2);border-radius:24px;padding:34px 34px;display:flex;flex-direction:column;justify-content:center;gap:14px}}
.g .t{{font-weight:700;font-size:34px;line-height:1.2}}
.g .t b{{color:var(--y);font-family:'Space Grotesk';margin-right:8px}}
.g .d{{font-size:26px;line-height:1.45;color:var(--soft)}}
.tipbox{{background:var(--y);color:var(--navy);border-radius:20px;padding:26px 32px;font-size:27px;line-height:1.4;font-weight:600}}
"""


def page(body, light=False):
    bg = "background:var(--y);color:var(--navy)" if light else ""
    return f"<!doctype html><html lang='tr'><head><meta charset='utf-8'><style>{CSS}</style></head><body style='{bg}'>{body}</body></html>"


def top(n, total=4, light=False):
    c = "style='color:var(--navy)'" if light else ""
    return (f"<div class='top'><div class='brand'>ucuzbilet<span {'style=\"color:var(--navy);background:var(--navy);color:var(--y);padding:0 8px;border-radius:6px\"' if light else ''}>ankara</span></div>"
            f"<div class='count' {c}>{n} / {total}</div></div>")


# ---------- kapak görselleri ----------
def route_map():
    esb = (600, 320)
    dests = [("LON", 70, 120), ("AMS", 220, 50), ("PAR", 110, 250), ("BCN", 80, 420), ("VIE", 390, 150),
             ("TBS", 790, 150), ("BAK", 860, 260), ("DXB", 830, 480), ("CAI", 470, 500)]
    paths, dots = [], []
    for code, x, y in dests:
        dx, dy = x - esb[0], y - esb[1]
        L = (dx * dx + dy * dy) ** .5
        nx, ny = -dy / L, dx / L
        if ny > 0:  # kavis hep yukarı (kuzeye) doğru
            nx, ny = -nx, -ny
        k = .22 * L
        cx, cy = (esb[0] + x) / 2 + nx * k, (esb[1] + y) / 2 + ny * k
        paths.append(f"<path d='M{esb[0]},{esb[1]} Q{cx:.0f},{cy:.0f} {x},{y}' fill='none' stroke='#FFC533' stroke-width='3' stroke-dasharray='2 12' stroke-linecap='round' opacity='.85'/>")
        dots.append(f"<circle cx='{x}' cy='{y}' r='9' fill='#F5F3EE'/>"
                    f"<text x='{x}' y='{y - 22}' text-anchor='middle' font-family='Space Grotesk' font-weight='700' font-size='26' fill='#F5F3EE' stroke='#0F1E33' stroke-width='10' paint-order='stroke' stroke-linejoin='round'>{code}</text>")
    return (f"<svg width='920' height='540' viewBox='0 0 920 540'>{''.join(paths)}{''.join(dots)}"
            f"<circle cx='{esb[0]}' cy='{esb[1]}' r='40' fill='#0F1E33'/>"
            f"<circle cx='{esb[0]}' cy='{esb[1]}' r='34' fill='#FFC533' opacity='.18'/>"
            f"<circle cx='{esb[0]}' cy='{esb[1]}' r='16' fill='#FFC533'/>"
            f"<text x='{esb[0]}' y='{esb[1] + 66}' text-anchor='middle' font-family='Space Grotesk' font-weight='700' font-size='34' fill='#FFC533'>ESB</text></svg>")


def check_ticket():
    rows = [("Aktarmasız", "Sadece direkt uçuş"), ("Esenboğa çıkışlı", "İstanbul yolu yok"), ("Şehir rehberiyle", "Yer, yemek, konaklama")]
    chk = ("<svg width='46' height='46' viewBox='0 0 24 24'><circle cx='12' cy='12' r='11' fill='#0F1E33'/>"
           "<path d='M7 12.5l3.2 3.2L17 9' fill='none' stroke='#FFC533' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'/></svg>")
    r = "".join(f"<div style='display:flex;align-items:center;gap:24px;padding:24px 0;{'border-top:2px dashed #C9D3E1' if i else ''}'>"
                f"{chk}<div><div class='sg' style='font-weight:700;font-size:40px;line-height:1.1'>{a}</div>"
                f"<div style='font-size:24px;color:var(--ink2)'>{b}</div></div></div>" for i, (a, b) in enumerate(rows))
    return (f"<div style='background:var(--cream);color:var(--navy);border-radius:30px;padding:22px 44px;width:100%'>"
            f"<div style='display:flex;justify-content:space-between;font-size:20px;font-weight:700;letter-spacing:1.5px;color:var(--ink2);padding:10px 0 6px'>"
            f"<span>BİNİŞ KARTI</span><span>ESB → DÜNYA</span></div>{r}</div>")


def steps_visual():
    st = [("1", "Postu kaydet"), ("2", "Linke tıkla"), ("3", "Uç")]
    arrow = ("<svg width='54' height='40' viewBox='0 0 54 40'><path d='M4 20h40M32 8l13 12-13 12' fill='none' "
             "stroke='#FFC533' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/></svg>")
    items = []
    for i, (n, t) in enumerate(st):
        items.append(f"<div style='flex:1;background:var(--navy2);border:2px solid var(--line);border-radius:28px;padding:48px 18px;"
                     f"display:flex;flex-direction:column;align-items:center;gap:16px'>"
                     f"<div class='sg' style='width:112px;height:112px;border-radius:50%;background:var(--y);color:var(--navy);"
                     f"display:flex;align-items:center;justify-content:center;font-weight:700;font-size:64px'>{n}</div>"
                     f"<div style='font-weight:700;font-size:34px;text-align:center;line-height:1.2'>{t}</div></div>")
        if i < 2:
            items.append(f"<div style='flex:none'>{arrow}</div>")
    return f"<div style='display:flex;align-items:center;gap:10px;width:100%'>{''.join(items)}</div>"


def cover(n, kicker, title, sub, visual, size=150):
    t = title.replace("?", "<span style='color:var(--y)'>?</span>")
    return page(f"""<div class='slide' style='justify-content:space-between'>
  <div style='display:flex;flex-direction:column;gap:16px'>
    {top(1)}
    <div style='display:flex;justify-content:space-between;align-items:center'>
      <div class='kicker'>{kicker}</div>
    </div>
  </div>
  <div class='sg' style='font-weight:700;font-size:{size}px;line-height:.95;letter-spacing:-6px'>{t}</div>
  <div style='display:flex;justify-content:center'>{visual}</div>
  <div style='font-size:34px;line-height:1.35;font-weight:500'>{sub}</div>
</div>""")


def list_slide(n, kicker, title, items, tip=None):
    cards = "".join(f"<div class='card'><div class='num'>{num}</div><div><div class='ct'>{t}</div><div class='cd'>{d}</div></div></div>"
                    for num, t, d in items)
    tipb = f"<div class='tipbox'>{tip}</div>" if tip else ""
    return page(f"""<div class='slide'>{top(n)}
  <div style='display:flex;flex-direction:column;gap:10px'><div class='kicker'>{kicker}</div><div class='h1'>{title}</div></div>
  <div style='display:flex;flex-direction:column;gap:22px;flex:1'>{cards}</div>{tipb}</div>""")


def grid_slide(n, kicker, title, items, tip):
    g = "".join(f"<div class='g'><div class='t'><b>{i + 1:02d}</b>{t}</div><div class='d'>{d}</div></div>" for i, (t, d) in enumerate(items))
    return page(f"""<div class='slide'>{top(n)}
  <div style='display:flex;flex-direction:column;gap:10px'><div class='kicker'>{kicker}</div><div class='h1'>{title}</div></div>
  <div class='grid2'>{g}</div><div class='tipbox'>{tip}</div></div>""")


ICONS = {
    "follow": "<path d='M9 12a4 4 0 100-8 4 4 0 000 8zM2 21c0-4 3-6 7-6s7 2 7 6M19 8v6M16 11h6'/>",
    "bell": "<path d='M6 16V11a6 6 0 1112 0v5l2 2H4zM10 21h4'/>",
    "save": "<path d='M6 3h12v18l-6-4-6 4z'/>",
    "send": "<path d='M21 3L3 10l7 3 3 7z'/><path d='M10 13l4-4'/>",
}


def closing(title, sub, ctas):
    cards = "".join(
        f"<div style='background:var(--cream);border-radius:26px;padding:34px 30px;display:flex;flex-direction:column;gap:14px'>"
        f"<svg width='44' height='44' viewBox='0 0 24 24' fill='none' stroke='#0F1E33' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>{ICONS[i]}</svg>"
        f"<div style='font-weight:700;font-size:34px'>{t}</div><div style='font-size:25px;line-height:1.4'>{d}</div></div>"
        for i, t, d in ctas)
    return page(f"""<div class='slide'>
  <div class='top'><div class='brand' style='color:var(--navy)'>ucuzbilet<span style='background:var(--navy);color:var(--y);padding:0 8px;border-radius:6px;margin-left:2px'>ankara</span></div>
  <div class='count' style='color:var(--navy)'>4 / 4</div></div>
  <div style='display:flex;flex-direction:column;gap:18px;margin-top:20px'>
    <div class='sg' style='font-weight:700;font-size:132px;line-height:.95;letter-spacing:-5px'>{title}</div>
    <div style='font-size:32px;line-height:1.4;font-weight:500'>{sub}</div></div>
  <svg width='920' height='150' viewBox='0 0 920 150' style='margin:auto 0'>
    <path d='M80,110 Q460,-30 840,110' fill='none' stroke='#0F1E33' stroke-width='4' stroke-dasharray='4 16' stroke-linecap='round'/>
    <circle cx='80' cy='110' r='14' fill='#0F1E33'/><circle cx='840' cy='110' r='14' fill='#0F1E33'/>
    <text x='80' y='148' text-anchor='middle' font-family='Space Grotesk' font-weight='700' font-size='30' fill='#0F1E33'>ESB</text>
    <text x='840' y='148' text-anchor='middle' font-family='Space Grotesk' font-weight='700' font-size='30' fill='#0F1E33'>?</text>
    <g transform='translate(430,8) rotate(8) scale(2.6)'><path d='M2.5 13.5l19-5.5-1-2.5-6.5 1.5-5-4.5-2 .5 3 5.5-4.5 1-2-2-1.5.5 1.5 4z' fill='#0F1E33'/></g>
  </svg>
  <div style='display:grid;grid-template-columns:repeat(3,1fr);gap:20px'>{cards}</div>
  <div style='background:var(--navy);color:var(--cream);border-radius:24px;padding:30px 36px;display:flex;align-items:center;gap:26px'>
    <svg width='60' height='60' viewBox='0 0 24 24' fill='none' stroke='#FFC533' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round' style='flex:none'><path d='M10 14a5 5 0 007 0l3-3a5 5 0 00-7-7l-1 1M14 10a5 5 0 00-7 0l-3 3a5 5 0 007 7l1-1'/></svg>
    <div><div style='font-weight:700;font-size:34px'>Bilet linki profilde</div>
    <div style='font-size:24px;color:var(--soft);margin-top:6px'>@ucuzbiletankara → profildeki link</div></div></div>
  <div style='font-size:22px;line-height:1.45'>{DISC_LINE}</div>
</div>""", light=True)


POSTS = {
    "1_biz_kimiz": [
        cover(1, "TANIŞALIM", "Biz kimiz?", "Ankara'dan aktarmasız yurt dışı uçuşları bulan, şehrini de anlatan sayfa.", route_map()),
        list_slide(2, "NE PAYLAŞIYORUZ", "Her akşam bir rota", [
            ("01", "Sadece Esenboğa'dan", "Kalkış hep Ankara. Fırsat için İstanbul'a gitmene gerek yok."),
            ("02", "Sadece aktarmasız", "Avrupa, Kafkasya, Dubai, Mısır ve fazlasına direkt uçuşlar."),
            ("03", "Normalinden ucuz", "6 ayın fiyatlarını her gün tarıyor, normalinden ucuz olanı seçiyoruz."),
            ("04", "Tarih, saat, fiyat", "Tarihler, kalkış-varış saatleri, havayolu ve fiyat kapakta."),
        ], "Aynı şehri 3 hafta içinde tekrar paylaşmıyoruz."),
        grid_slide(3, "TEK POSTTA KÜÇÜK REHBER", "Bileti bul, şehri de tanı", [
            ("Neden şimdi?", "O tarihteki etkinlik ve sezon: Noel pazarı, kayak, deniz."),
            ("Gezilecek yerler", "8 yer, kısa ve işe yarar notlarla."),
            ("Ne yenir?", "Mutlaka denemen gereken yerel lezzetler."),
            ("Nerede yenir?", "Köklü ve hâlâ açık mekânlar."),
            ("Nerede kalınır?", "Konaklamaya uygun semtler ve neden."),
            ("Ulaşım + ipuçları", "Havalimanından şehre, vize, para ve hava durumu."),
        ], "Postu kaydet: gittiğinde rehberin cebinde olsun."),
        closing("Takipte kal.", "Ankara'dan bir sonraki ucuz direkt uçuş yarın akşam burada.", [
            ("follow", "Takip et", "Her akşam yeni bir rota."),
            ("bell", "Bildirimi aç", "Ucuz fiyatı ilk sen gör."),
            ("send", "Gönder", "Birlikte gideceğin kişiye yolla."),
        ]),
    ],
    "2_neden_biz": [
        cover(1, "FARKIMIZ", "Neden biz?", "Ankara'dan uçanlar için, Ankara'dan bakan bir sayfa.", check_ticket()),
        list_slide(2, "ZAMAN KAZANDIRIR", "Aktarma yok, İstanbul yolu yok", [
            ("01", "Sadece Esenboğa", "Ucuz bilet için önce İstanbul'a gitmek yok. Her rota Ankara'dan kalkıyor."),
            ("02", "Sadece direkt", "Aktarmalı ucuz bilet çoğu zaman yarım gün yolculuk demek. Burada sadece aktarmasız uçuşlar var."),
            ("03", "Erken plan", "6 ay ilerisine bakıyoruz. Vize gereken yerlerde randevuya zamanın kalsın."),
        ]),
        list_slide(3, "İŞİNE YARAR", "Bilet + rehber, tek postta", [
            ("04", "Zamanına göre rota", "Noel pazarları, lale zamanı, kayak, deniz: rotayı mevsimine göre seçiyoruz."),
            ("05", "Kaydedilecek içerik", "Gezilecek yerler, yemek, konaklama ve ulaşım; gidince açıp bakarsın."),
            ("06", "Şeffaf", "Bilet satmıyoruz. Fiyat, paylaşım anındaki en düşük fiyat; değişebileceğini her postta yazıyoruz."),
        ]),
        closing("Bir sonraki rota yarın.", "Kaçırmamak için takip et, beğendiğin rotayı kaydet.", [
            ("follow", "Takip et", "Her akşam yeni bir rota."),
            ("save", "Kaydet", "Plan yaparken elinin altında olsun."),
            ("send", "Gönder", "Yol arkadaşına yolla."),
        ]),
    ],
    "3_nasil_kullanilir": [
        cover(1, "ADIM ADIM", "Nasıl kullanılır?", "Postu gör, bileti 3 adımda bul.", steps_visual(), size=128),
        list_slide(2, "BİLETİ BULMAK", "Postu gördün, şimdi ne?", [
            ("01", "Kapağa bak", "Tarih, kalkış ve varış saati, havayolu ve fiyat ilk slaytta yazıyor."),
            ("02", "Profildeki linke gir", "Bilet linkinde Ankara (ESB) ve şehri seç, postta yazan tarihleri gir."),
            ("03", "Aktarmasızı seç", "Sonuçlarda \"aktarmasız\" filtresini işaretle, postta yazan uçuşu bul."),
        ]),
        list_slide(3, "BİLETTEN SONRA", "Fiyat değiştiyse ve sonrası", [
            ("04", "Fiyat değiştiyse", "Fiyat, paylaşım anındaki en düşük fiyat. Bir gün önceye ya da sonraya da bak."),
            ("05", "Vizeyi unutma", "Vize gereken yerlerde randevuyu erken al; pasaportunun geçerlilik süresine bak."),
            ("06", "Rehberi kaydet", "Gezilecek yerler, yemek ve ulaşım bilgisi gittiğinde cebinde olsun."),
        ]),
        closing("İyi yolculuklar.", "Soru ya da öneri için DM'den yazabilirsin.", [
            ("follow", "Takip et", "Her akşam yeni bir rota."),
            ("bell", "Bildirimi aç", "Ucuz fiyatı ilk sen gör."),
            ("save", "Kaydet", "Bu rehber lazım olacak."),
        ]),
    ],
}

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium-1243/chrome-linux64/chrome")
    pg = b.new_page(viewport={"width": 1080, "height": 1350})
    for name, slides in POSTS.items():
        for i, html in enumerate(slides, 1):
            f = OUT / f"{name}_{i}.html"
            f.write_text(html, encoding="utf-8")
            pg.goto(f.as_uri(), wait_until="load")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(200)
            over = pg.evaluate("document.querySelector('.slide').scrollHeight > 1350")
            pg.screenshot(path=str(OUT / f"{name}_{i}.png"), type="png")
            print(name, i, "TAŞMA" if over else "ok")
    b.close()
