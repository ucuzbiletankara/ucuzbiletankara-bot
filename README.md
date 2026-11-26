# @ucuzbiletankara bot

Ankara Esenboğa (ESB) çıkışlı, **aktarmasız** ve **ucuz** yurt dışı uçuşları bulup
Instagram'da her gün otomatik carousel olarak paylaşan sistem.

## Durum
| Aşama | İçerik | Durum |
|---|---|---|
| 3 | Fırsat tarama motoru | ✅ hazır, test ediliyor |
| 4 | İçerik + görsel üretimi | sırada |
| 5 | Instagram'a otomatik paylaşım | sırada |

## Kurallar
- Sadece yurt dışı, sadece direkt uçuş
- İzinli ülkeler: `config/destinations.yaml`
- Gidiş-dönüş mü tek yön mü, fırsat eşiği, puanlama: `config/settings.yaml`
- Sezon/gündem takvimi (Noel pazarları, kayak, lale, Oktoberfest…): `config/seasons.yaml`

## Gizli anahtarlar (GitHub → Settings → Secrets and variables → Actions)
| Ad | Ne için |
|---|---|
| `TRAVELPAYOUTS_TOKEN` | Uçuş fiyatları |
| `TRAVELPAYOUTS_MARKER` | Uçuş affiliate linkleri |
| `PIXABAY_API_KEY` | Fotoğraflar |
| `ANTHROPIC_API_KEY` | İçerik metinleri |

## Elle tarama
Actions → **Fırsat taraması (test)** → **Run workflow**. Sonuç tablosu çalışmanın
özet sayfasında, ham veri `tarama-sonucu` dosyasında.

## Yerel test (ağsız)
```bash
pip install -r requirements.txt
python -m tests.test_scan
```
