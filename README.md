# EcoScale

Karbon Ayak İzi ve Maliyet Odaklı Akıllı Bulut Kaynak Yönetimi Simülasyonu.

Bu depo, Manisa Celal Bayar Üniversitesi Yazılım Mühendisliği Bölümü lisans bitirme
tezinin ("EcoScale: Karbon Ayak İzi ve Maliyet Odaklı Akıllı Bulut Kaynak Yönetimi
Simülasyonu") uçtan uca çalışan bir prototipini içerir. Tezde tanımlanan dört katman
(Veri Toplama, Tahmin, Optimizasyon, Kullanıcı Arayüzü) burada gerçek kodla karşılık
bulur.

## Mimari

| Katman | Modül | İçerik |
|---|---|---|
| Veri Toplama | [`ecoscale/data.py`](ecoscale/data.py) | Trafik ve şebeke karbon yoğunluğu verisinin sentetik üretimi (gerçekçi günlük/haftalık örüntülerle) |
| Tahmin | [`ecoscale/forecasting.py`](ecoscale/forecasting.py) | Random Forest Regressor ile trafik tahmini, R²/MAE/RMSE metrikleri |
| Optimizasyon | [`ecoscale/optimizer.py`](ecoscale/optimizer.py) | Hibrit amaç fonksiyonu (Z = α·maliyet + β·karbon), reaktif/proaktif ölçeklendirme kıyası, karbon-bilinçli görev kaydırma, S1-S5 senaryo sınıflandırması |
| Kullanıcı Arayüzü | [`app.py`](app.py) | Streamlit dashboard — parametreleri (α/β, sunucu maliyeti, kapasite) canlı değiştirip etkisini görme |

`ecoscale/simulation.py` bu dört katmanı tek bir akışta birleştirir (tarihsel/toplu simülasyon).

Ayrıca [`ecoscale/live_engine.py`](ecoscale/live_engine.py), Tablo 3.1'de tanımlanan APScheduler
rolünün **gerçek zamanlı** çalışan karşılığıdır: Streamlit sürecinden bağımsız bir arka plan
servisi olarak çalışır, her "tick"te bir simülasyon saati ilerler, ML tahmin motorundan gelen
trafik öngörüsüne göre proaktif sunucu sayısına karar verir ve bekleyen arka plan görevlerini
ya hemen çalıştırır ya da şebeke karbonu düşene kadar erteler. Durumunu `.state/live_state.json`
dosyasına yazar; dashboard bu dosyayı okuyarak sonuçları canlı gösterir (`ecoscale/live_state.py`
iki süreç arasındaki basit dosya tabanlı IPC katmanıdır).

## Kurulum ve Çalıştırma

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Dashboard açıldıktan sonra sol menüdeki **"Canlı Motor (APScheduler)"** bölümünden
**▶ Motoru Başlat**'a basarak gerçek zamanlı motoru başlatabilirsiniz (veya elle:
`python -m ecoscale.live_engine --tick-seconds 2`). Motor, dashboard kapansa da
arka planda çalışmaya devam eder; durdurmak için dashboard'daki **■ Motoru Durdur**
butonunu kullanın ya da `pkill -f ecoscale.live_engine` çalıştırın.

## Şu ana kadar yapılan (MVP kapsamı)

- Sentetik veri üretimi (trafik + karbon yoğunluğu, günlük/haftalık örüntülerle)
- Random Forest ile trafik tahmini ve başarı metrikleri
- Hibrit amaç fonksiyonu ve reaktif/proaktif ölçeklendirme karşılaştırması (maliyet, karbon, SLA ihlali)
- Karbon-bilinçli görev kaydırma (3 örnek arka plan görevi üzerinde, tarihsel simülasyonda)
- Tez Tablo 3.3'teki S1-S5 karar senaryolarının otomatik sınıflandırılması
- Tüm sonuçları gösteren interaktif Streamlit dashboard
- **APScheduler tabanlı gerçek zamanlı zamanlama motoru**: bağımsız arka plan sürecinde
  saat saat ilerleyen, görevleri anlık karbon sinyaline göre çalıştıran/erteleyen, dashboard'dan
  başlatılıp durdurulabilen canlı bir sistem (`ecoscale/live_engine.py`)

## Sırada ne var

- Gerçek karbon yoğunluğu verisi entegrasyonu (ör. ElectricityMaps API) — şu an sentetik
- LSTM / hibrit model karşılaştırması (Tablo 2.1)
- Gerçek bulut fiyatlandırma API entegrasyonu (bölgeye göre saatlik tarife)
- Kapsam 3 (embodied carbon) hesaplamalarının modele eklenmesi
- Kullanıcı testleri ve performans/yük testleri
