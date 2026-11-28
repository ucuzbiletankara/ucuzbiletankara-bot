"""Carousel postundan otomatik Reels (1080×1920, 30 fps, ~17 sn, telifsiz kendi müziği).

Kullanım: python3 reel.py <post_klasörü> <çıktı.mp4>
post_klasörü: post.json + cover.jpg, sights_*.jpg, food_0.jpg (bot'un output/post klasörü).
"""
import json
import math
import subprocess
import sys
import wave
from datetime import date
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

W, H, FPS = 1080, 1920, 30
SG = Path("/home/claude/sabit/gf/ofl/spacegrotesk/SpaceGrotesk[wght].ttf").as_uri()
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
AY3 = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def tl(x):
    return f"{int(x):,}".replace(",", ".") + " TL"


def dates_txt(p):
    o = date.fromisoformat(p["out_date"])
    if p.get("ret_date"):
        r = date.fromisoformat(p["ret_date"])
        if o.month == r.month:
            return f"{o.day}–{r.day} {AYLAR[o.month - 1]}"
        return f"{o.day} {AY3[o.month - 1]} – {r.day} {AY3[r.month - 1]}"
    return f"{o.day} {AYLAR[o.month - 1]}"


def short(d):
    d = date.fromisoformat(d)
    return f"{d.day} {AY3[d.month - 1]}"


def photo_score(path: Path) -> float:
    """Reels için 'göz alıcılık' puanı: renk canlılığı (Hasler–Süsstrunk) × parlaklık; karanlık/soluk fotoğraf geride kalır."""
    from PIL import Image
    im = np.asarray(Image.open(path).convert("RGB").resize((160, 100)), dtype=float)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    rg, yb = r - g, 0.5 * (r + g) - b
    colorful = np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)
    bright = im.mean() / 255
    return colorful * min(1.0, bright / 0.45)


def build_scenes(post_dir: Path, exclude=()):
    d = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    c, p = d["content"], d["pick"]
    items = c["sights_1"]["items"] + c["sights_2"]["items"]
    photos = {f"sights_{1 + i // 4}_{i % 4}": it for i, it in enumerate(items)}
    # En bilinen yerler genelde 2. sayfada değil 1.'de olur; Claude'un sırasını koru, ilk 4 fotoğraflıyı al
    cand = [(k, it) for k, it in photos.items() if (post_dir / f"{k}.jpg").exists() and k not in exclude]
    cand.sort(key=lambda x: -photo_score(post_dir / f"{x[0]}.jpg"))
    hero, sights = (cand[0] if cand else None), cand[1:4]
    food = c["food"]["items"][0]
    rt = p["format"] == "rt"
    scenes = [dict(kind="cover", dur=3.4, img=f"{hero[0]}.jpg" if hero else "cover.jpg", city=p["city_name"],
                   price=tl(p["price"]), fmt="gidiş-dönüş" if rt else "tek yön", dates=dates_txt(p))]
    for n, (k, it) in enumerate(sights, 1):
        scenes.append(dict(kind="card", dur=2.0, img=f"{k}.jpg", kicker=f"GEZ · {n}/{len(sights)}", title=it["name"]))
    if (post_dir / "food_0.jpg").exists():
        scenes.append(dict(kind="card", dur=2.0, img="food_0.jpg", kicker="YE", title=food["name"]))
    legs = [("Gidiş", short(p["out_date"]), p.get("out_dep_time"), p.get("out_arr_time"))]
    if rt:
        legs.append(("Dönüş", short(p["ret_date"]), p.get("ret_dep_time"), p.get("ret_arr_time")))
    scenes.append(dict(kind="end", dur=3.8, city=p["city_name"], code=p.get("destination_airport", ""),
                       price=tl(p["price"]), fmt="gidiş-dönüş" if rt else "tek yön", legs=legs,
                       airline=f"{p.get('airline_name', '')} {p.get('flight_number', '')}".strip()))
    return scenes


PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:'SG';src:url('%(sg)s') format('truetype');font-weight:300 700}
*{box-sizing:border-box;margin:0}
body{width:1080px;height:1920px;overflow:hidden;background:#0F1E33;font-family:Inter,sans-serif;color:#F5F3EE}
.scene{position:absolute;inset:0;opacity:0;overflow:hidden}
.bg{position:absolute;inset:-60px;background-size:cover;background-position:center;filter:blur(38px) brightness(.45) saturate(1.2)}
.full{position:absolute;inset:0;background-size:cover;background-position:center}
.shade{position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,30,51,.55) 0%%,rgba(15,30,51,.05) 30%%,rgba(15,30,51,.25) 55%%,rgba(15,30,51,.92) 100%%)}
.brand{position:absolute;top:150px;left:70px;font-family:SG;font-weight:700;font-size:38px;letter-spacing:-.5px}
.brand span{color:#FFC533}
.kick{display:inline-block;background:#FFC533;color:#0F1E33;font-weight:800;font-size:32px;letter-spacing:2px;padding:10px 18px;border-radius:10px}
.city{font-family:SG;font-weight:700;font-size:170px;line-height:.92;letter-spacing:-6px}
.price{font-family:SG;font-weight:700;font-size:150px;line-height:1;color:#FFC533;letter-spacing:-4px}
.sub{font-size:42px;font-weight:600;color:#F5F3EE}
.card{position:absolute;left:60px;right:60px;top:430px;height:720px;border-radius:36px;overflow:hidden;box-shadow:0 30px 80px rgba(0,0,0,.45)}
.card .img{position:absolute;inset:0;background-size:cover;background-position:center}
.ttl{font-family:SG;font-weight:700;font-size:92px;line-height:1;letter-spacing:-3px}
.ticket{background:#F5F3EE;color:#0F1E33;border-radius:36px;padding:44px 50px}
.leg{display:flex;justify-content:space-between;align-items:baseline;padding:22px 0;border-top:3px dashed #C9D3E1}
.leg:first-child{border-top:none}
.cta{background:#FFC533;color:#0F1E33;border-radius:28px;padding:34px 40px;font-weight:800;font-size:46px;line-height:1.2}
</style></head><body>%(body)s
<script>
const S=%(scenes)s;
function ease(x){return 1-Math.pow(1-Math.min(Math.max(x,0),1),3)}
window.renderAt=function(t){
  let start=0;
  S.forEach((s,i)=>{
    const el=document.getElementById('s'+i), lt=t-start, fade=.35;
    let op=0;
    if(lt>=-fade && lt<s.dur){op= i==0?1:ease((lt+fade)/fade);}
    if(lt>=s.dur-0.0 && i<S.length-1){op=0}
    el.style.opacity=op;
    const k=lt/s.dur;
    el.querySelectorAll('[data-zoom]').forEach(z=>{z.style.transform='scale('+(1.0+0.08*Math.max(0,Math.min(k,1)))+')'});
    el.querySelectorAll('[data-in]').forEach(z=>{
      const d=parseFloat(z.dataset.in), e=ease((lt-d)/.35);
      z.style.opacity=e; z.style.transform='translateY('+((1-e)*40)+'px)';
    });
    el.querySelectorAll('[data-pop]').forEach(z=>{
      const d=parseFloat(z.dataset.pop), x=Math.min(Math.max((lt-d)/.3,0),1);
      const sc= x<1 ? 0.6+0.55*Math.sin(x*Math.PI/2)-0.15*x : 1; z.style.opacity=x>0?1:0; z.style.transform='scale('+sc+')';
    });
    start+=s.dur;
  });
};
</script></body></html>"""


def scene_html(i, s, base):
    img = lambda f: (base / f).as_uri()
    if s["kind"] == "cover":
        return f"""<div class="scene" id="s{i}">
  <div class="bg" style="background-image:url('{img(s['img'])}')"></div>
  <div class="brand">ucuzbilet<span>ankara</span></div>
  <div class="card" style="top:300px;height:660px"><div class="img" data-zoom style="background-image:url('{img(s['img'])}')"></div></div>
  <div style="position:absolute;left:70px;right:150px;top:1010px;display:flex;flex-direction:column;gap:22px">
    <div data-in="0.0"><span class="kick">ANKARA'DAN DİREKT ✈</span></div>
    <div class="city" data-in="0.1" style="font-size:150px">{s['city']}</div>
    <div class="price" data-pop="0.45" style="transform-origin:left center;font-size:140px">{s['price']}</div>
    <div class="sub" data-in="0.8">{s['fmt']} · {s['dates']}</div>
  </div></div>"""
    if s["kind"] == "card":
        return f"""<div class="scene" id="s{i}">
  <div class="bg" style="background-image:url('{img(s['img'])}')"></div>
  <div class="brand">ucuzbilet<span>ankara</span></div>
  <div class="card"><div class="img" data-zoom style="background-image:url('{img(s['img'])}')"></div></div>
  <div style="position:absolute;left:70px;right:150px;top:1200px;display:flex;flex-direction:column;gap:22px">
    <div data-in="0.1"><span class="kick">{s['kicker']}</span></div>
    <div class="ttl" data-in="0.2">{s['title']}</div>
  </div></div>"""
    legs = "".join(f"""<div class="leg"><div><div style="font-size:26px;font-weight:700;letter-spacing:2px;color:#4A5A72">{a.upper()} · {b}</div>
      <div style="font-family:SG;font-weight:700;font-size:64px;letter-spacing:-1px">{c or ''} → {d or ''}</div></div></div>""" for a, b, c, d in s["legs"])
    return f"""<div class="scene" id="s{i}" style="background:#0F1E33">
  <div class="brand">ucuzbilet<span>ankara</span></div>
  <div style="position:absolute;left:70px;right:150px;top:270px;display:flex;flex-direction:column;gap:30px">
    <div data-in="0.05" style="font-family:SG;font-weight:700;font-size:84px;line-height:1;letter-spacing:-3px">ESB → {s['code']}<br><span style="color:#FFC533">{s['price']}</span></div>
    <div data-in="0.15" style="font-size:36px;font-weight:600;color:#C9D3E1">{s['fmt']} · aktarmasız · yerel saat</div>
    <div class="ticket" data-in="0.3">{legs}
      <div style="font-size:28px;font-weight:700;color:#4A5A72;padding-top:14px">{s['airline']}</div></div>
    <div class="cta" data-pop="0.9" style="transform-origin:left center">Bunu kiminle gidersin?<br>Ona gönder ✈️</div>
    <div data-in="1.3" style="font-size:38px;font-weight:700">Bilet linki profilde 🔗</div>
  </div></div>"""


def music(path: Path, dur: float, bpm=100, sr=44100):
    """Basit, telifsiz lo-fi döngü: yumuşak akorlar + kick + hi-hat (kendi üretimimiz)."""
    n = int(dur * sr)
    t = np.arange(n) / sr
    out = np.zeros(n)
    beat = 60 / bpm
    bar = beat * 4
    notes = {"C": 261.63, "D": 293.66, "E": 329.63, "F": 349.23, "G": 392.0, "A": 440.0, "B": 493.88}
    prog = [("F", ["F", "A", "C5", "E5"]), ("G", ["G", "B", "D5", "F5"]), ("E", ["E", "G", "B", "D5"]), ("A", ["A", "C5", "E5", "G5"])]

    def f(nm):
        return notes[nm[0]] * (2 if nm.endswith("5") else 1)
    for b in range(int(dur / bar) + 1):
        root, chord = prog[b % 4]
        for hit in (0, 2.5):  # akor vuruşları
            s0 = b * bar + hit * beat
            i0 = int(s0 * sr)
            if i0 >= n:
                continue
            L = min(n - i0, int(bar * sr))
            tt = np.arange(L) / sr
            env = np.exp(-tt * 1.6) * (1 - np.exp(-tt * 60))
            for nm in chord:
                fr = f(nm)
                out[i0:i0 + L] += 0.07 * env * (np.sin(2 * np.pi * fr * tt) + 0.3 * np.sin(4 * np.pi * fr * tt) + 0.1 * np.sin(6 * np.pi * fr * tt))
            fr = notes[root] / 2
            out[i0:i0 + L] += 0.12 * env * np.sin(2 * np.pi * fr * tt)  # bas
    for k in range(int(dur / beat) + 1):
        i0 = int(k * beat * sr)
        if i0 >= n:
            continue
        if k % 2 == 0:  # kick
            L = min(n - i0, int(0.35 * sr)); tt = np.arange(L) / sr
            fr = 50 + 70 * np.exp(-tt * 25)
            out[i0:i0 + L] += 0.5 * np.exp(-tt * 9) * np.sin(2 * np.pi * np.cumsum(fr) / sr)
        else:  # snare benzeri
            L = min(n - i0, int(0.2 * sr)); tt = np.arange(L) / sr
            out[i0:i0 + L] += 0.12 * np.exp(-tt * 18) * np.random.default_rng(k).standard_normal(L)
        for half in (0, 0.5):  # hi-hat
            j0 = int((k + half) * beat * sr)
            if j0 >= n:
                continue
            L = min(n - j0, int(0.05 * sr)); tt = np.arange(L) / sr
            noise = np.random.default_rng(1000 + k * 2 + int(half * 2)).standard_normal(L)
            out[j0:j0 + L] += 0.04 * np.exp(-tt * 80) * np.diff(np.concatenate([[0], noise]))
    out += 0.004 * np.random.default_rng(7).standard_normal(n)  # plak hışırtısı
    fade = int(0.8 * sr)
    out[:int(0.15 * sr)] *= np.linspace(0, 1, int(0.15 * sr))
    out[-fade:] *= np.linspace(1, 0, fade)
    out = out / max(1e-9, np.abs(out).max()) * 0.8
    pcm = (np.stack([out, out], 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def main(post_dir: Path, out: Path, exclude=()):
    work = out.parent / "frames"
    work.mkdir(parents=True, exist_ok=True)
    for f in work.glob("*.jpg"):
        f.unlink()
    scenes = build_scenes(post_dir, exclude)
    total = sum(s["dur"] for s in scenes)
    html = PAGE % dict(sg=SG, body="".join(scene_html(i, s, post_dir.resolve()) for i, s in enumerate(scenes)),
                       scenes=json.dumps([{"dur": s["dur"]} for s in scenes]))
    page_file = out.parent / "reel.html"
    page_file.write_text(html, encoding="utf-8")
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium-1243/chrome-linux64/chrome")
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto(page_file.as_uri(), wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(500)
        nf = int(math.ceil(total * FPS))
        for k in range(nf):
            pg.evaluate(f"renderAt({k / FPS})")
            pg.screenshot(path=str(work / f"{k:05d}.jpg"), type="jpeg", quality=92)
        b.close()
    wav = out.parent / "music.wav"
    music(wav, total)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(work / "%05d.jpg"), "-i", str(wav),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-profile:v", "high",
                    "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(out)], check=True)
    print(f"{out} · {total:.1f} sn · {len(scenes)} sahne")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), tuple(sys.argv[3].split(',')) if len(sys.argv) > 3 else ())
