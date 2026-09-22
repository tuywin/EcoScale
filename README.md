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

### Deney 1 — Gerçek Karbon Yoğunluğu Verisi (UK Carbon Intensity API)

[`ecoscale/real_data.py`](ecoscale/real_data.py), National Energy System Operator'ın
ücretsiz ve kayıt gerektirmeyen [Carbon Intensity API](https://api.carbonintensity.org.uk/)'sinden
İngiltere şebekesinin gerçek yarım-saatlik gCO₂eq/kWh verisini çeker, saatliğe indirger
ve `data_real/uk_carbon_intensity.csv` içinde önbelleğe alır (ağ erişimi olmadan da
tekrar kullanılabilir). Dashboard'daki **"Karbon Yoğunluğu Verisi"** seçeneğinden
sentetik veri yerine bu gerçek veri kullanılarak tüm optimizasyon/karşılaştırma
sonuçları yeniden hesaplanabilir. Veriyi elle yenilemek için:

```bash
python -m ecoscale.real_data
```

### Deney 1b — Türkiye ve AB Ülkeleri Karşılaştırması (Ember)

[`ecoscale/country_carbon.py`](ecoscale/country_carbon.py), [Ember Yearly Electricity
Data](https://ember-energy.org/data/yearly-electricity-data/)'dan Türkiye ve 27 AB
üyesi ülkenin **yıllık ortalama** şebeke karbon yoğunluğunu (gCO₂e/kWh) çekip
`data_real/ember_country_carbon_intensity.csv` içinde önbelleğe alır (kayıt
gerektirmez). Dashboard bölüm 6'da tüm ülkeler karşılaştırmalı olarak gösterilir.
Türkiye'nin şebekesi AB ortalamasının ~2.1 katı karbon yoğunluğunda (476 vs ~224
gCO₂e/kWh, 2025) — 29 ülke arasında 4. en kirli şebeke. Bu veri yıllık ortalama
olduğu için saatlik simülasyonlarda kullanılmıyor; saatlik Türkiye/AB verisi için
`DEVAM_PLANI.md`'deki ENTSO-E adımlarına bakın.

### Deney 2 — Gerçek Bulut Fiyatlandırma Verisi (Azure Retail Prices API)

[`ecoscale/cloud_pricing.py`](ecoscale/cloud_pricing.py), tamamen açık ve kimlik
doğrulama gerektirmeyen [Azure Retail Prices API](https://prices.azure.com/api/retail/prices)'sinden
11 gerçek Azure bölgesinin (Standard_D2s_v5, Linux, pay-as-you-go) saatlik $ fiyatını
çeker ve `data_real/azure_regional_prices.csv` içinde önbelekler (AWS Price List Bulk
API kasıtlı olarak kullanılmadı — bölge başına 400MB-9GB olduğu ve sunucu tarafında
filtrelenemediği için). Dashboard'daki **"Sunucu Maliyeti (C_birim)"** seçeneğinden
bir bölge seçilerek gerçek fiyat, amaç fonksiyonuna doğrudan aktarılabilir. Bölüm 7'de
bu fiyatlar Ember'ın karbon verisiyle birleştirilip **fiyat–karbon korelasyonu**
hesaplanıyor (gerçek veride Pearson r ≈ 0.60 — Polonya ve İsveç neredeyse aynı fiyata
sahipken karbon yoğunlukları 17 kat farklı, tez Bölüm 1.3 madde 3'ü somutlaştırıyor).
Not: Ne Azure'un ne AWS'in Türkiye'de fiziksel bölgesi var; Türkiye için en yakın
pratik seçenek olarak Qatar Central kullanıldı (karbon değeri değil, sadece fiyat
için temsili). Veriyi elle yenilemek için:

```bash
python -m ecoscale.cloud_pricing
```

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
- **Deney 1 — gerçek karbon yoğunluğu verisi**: UK Carbon Intensity API'den çekilen
  gerçek İngiltere şebeke verisiyle tüm sonuçlar yeniden üretilebiliyor (`ecoscale/real_data.py`);
  gerçek veride de proaktif yaklaşım ~%18 karbon tasarrufu sağlıyor (sentetik veride ~%20)
- **Deney 1b — Türkiye + AB ülkeleri karşılaştırması**: Ember verisiyle 29 ülkenin
  yıllık ortalama karbon yoğunluğu karşılaştırılıyor (`ecoscale/country_carbon.py`);
  Türkiye AB ortalamasının 2.1 katı ile en kirli 4. şebeke
- **Deney 2 — gerçek bulut fiyatlandırma verisi**: Azure Retail Prices API'den 11
  bölgenin gerçek $/saat fiyatı çekiliyor (`ecoscale/cloud_pricing.py`); fiyat–karbon
  korelasyonu (r≈0.60) ve "aynı fiyata çok farklı karbon" örnekleri dashboard'da

## Sırada ne var (bkz. `DEVAM_PLANI.md`)

- Gerçek **saatlik** Türkiye/AB verisi (ENTSO-E Transparency Platform — kullanıcının
  kendi hesabıyla kayıt + token gerektiriyor, adımlar `DEVAM_PLANI.md`'de)
- Deney 3: Gerçek trafik verisi (Azure Public Dataset / Wikipedia Pageviews) ile model yeniden eğitimi
- LSTM / hibrit model karşılaştırması (Tablo 2.1)
- Kapsam 3 (embodied carbon) hesaplamalarının modele eklenmesi
- Kullanıcı testleri ve performans/yük testleri
