# EcoScale — Devam Planı (Kalan %60-70)

Mevcut MVP tamamen sentetik veriyle çalışıyor. Bu plan, tezin geri kalanını
**gerçek veri ve deneylerle** doldurmak için hangi işin hangi kaynaktan
besleneceğini gösterir. Her deney maddesinde: neyi değiştireceğiz, veriyi
nereden çekeceğiz, ve bunun hangi tez iddiasını doğrulayacağı belirtilmiştir.

## Veri Kaynakları — Özet Tablo

| # | Kaynak | Ne sağlıyor | Erişim | Maliyet |
|---|---|---|---|---|
| 1 | [EPİAŞ Şeffaflık Platformu](https://seffaflik.epias.com.tr/) | Türkiye saatlik elektrik üretim kaynak dağılımı (kömür/doğalgaz/hidro/rüzgar/güneş, MW) | Ücretsiz kayıt + API anahtarı, `eptr2` Python paketi | Ücretsiz |
| 2 | [UK Carbon Intensity API](https://api.carbonintensity.org.uk/) | Hazır saatlik gCO₂eq/kWh şebeke karbon yoğunluğu (geçmiş+tahmin) | Kayıt gerektirmez, doğrudan REST | Ücretsiz |
| 3 | [AWS Price List Bulk API](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/index.json) | Instance tipi/bölge bazlı saatlik $ fiyat | Kimlik doğrulama yok | Ücretsiz |
| 4 | [Azure Retail Prices API](https://prices.azure.com/api/retail/prices) | Instance tipi/bölge bazlı saatlik $ fiyat | Kimlik doğrulama yok | Ücretsiz |
| 5 | [Azure Public Dataset (AzurePublicDatasetV2)](https://github.com/Azure/AzurePublicDataset) | ~2.6M gerçek VM'in 5 dakikalık CPU kullanım zaman serisi | Genel erişim, dosya indirme | Ücretsiz |
| 6 | [Wikipedia Pageviews](https://dumps.wikimedia.org/other/pageviews/) | Saatlik gerçek web trafiği (günlük/haftalık periyodiklik güçlü) | Genel erişim, dosya indirme | Ücretsiz |

---

## Faz 1 — Gerçek Veri Entegrasyonu

### Deney 1: Gerçek Karbon Yoğunluğu ile Yeniden Değerlendirme
- **Birincil kaynak:** EPİAŞ Şeffaflık Platformu'ndan Türkiye'nin saatlik üretim
  kaynak dağılımını çekip, her kaynağa literatürdeki emisyon faktörünü
  (kömür ≈820, doğalgaz ≈490, hidro/rüzgar/güneş ≈0-45 gCO₂eq/kWh) uygulayarak
  saatlik **ortalama karbon yoğunluğu** hesaplamak (tez Bölüm 2.4.2'deki
  formülasyonun birebir uygulaması).
- **Karşılaştırma kaynağı:** UK Carbon Intensity API — hazır seri, kayıt
  gerektirmiyor; Türkiye verisi hazırlanana kadar hızlı prototipleme ve
  ayrıca "fosil ağırlıklı vs. rüzgar ağırlıklı şebeke" karşılaştırması için.
- **Ne değişecek:** `ecoscale/data.py`'deki sentetik `carbon_intensity` serisi,
  gerçek veriden okunan bir seriyle değiştirilecek (yeni `ecoscale/data_real.py`
  modülü).
- **Doğrulanacak iddia:** Task-shifting algoritmasının gerçek şebeke
  verisinde de anlamlı karbon tasarrufu sağladığı.

### Deney 2: Gerçek Bulut Fiyatlandırmasıyla Maliyet Modeli
- **Kaynak:** AWS Price List API + Azure Retail Prices API (ikisi de açık).
- **Ne değişecek:** Sabit `C_birim` parametresi, gerçek bir instance tipinin
  (ör. AWS t3.medium / Azure Standard_B2s) bölgeye göre saatlik fiyatıyla
  değiştirilecek.
- **Doğrulanacak iddia:** Tez Bölüm 1.3, madde 3 — "bölgelere göre saatlik
  enerji maliyeti ile karbon yoğunluğu her zaman paralel gitmiyor" savı;
  2-3 bölgeyi (fiyat, karbon) çiftleriyle karşılaştırarak somutlaştırılacak.

### Deney 3: Gerçek Trafik Verisiyle Model Doğrulama
- **Kaynak A:** Azure Public Dataset — gerçek VM CPU kullanım serisi.
- **Kaynak B:** Wikipedia Pageviews — gerçek saatlik web trafiği.
- **Ne değişecek:** Random Forest modeli sentetik `traffic_rps` yerine bu
  gerçek serilerden biriyle yeniden eğitilecek.
- **Doğrulanacak iddia:** Özet'te geçen "%90 doğruluk" rakamının gerçek,
  gürültülü veride de korunup korunmadığı (R²/MAE/RMSE yeniden raporlanacak).

## Faz 2 — Model Karşılaştırma ve Duyarlılık Analizi

### Deney 4: RF vs LSTM vs XGBoost (Tablo 2.1)
- Ek veri kaynağı gerekmez — Deney 3'teki gerçek veri seti kullanılır.
- Üç modelin aynı veri üzerinde başarı metrikleri karşılaştırılır; hangisinin
  gerçek veri gürültüsüne karşı daha dayanıklı olduğu tartışılır.

### Deney 5: α/β Duyarlılık Analizi (Pareto Eğrisi)
- Ek veri gerekmez — mevcut sistemle yapılabilir.
- α, 0'dan 1'e adım adım taranarak maliyet–karbon Pareto eğrisi çizilir;
  hibrit amaç fonksiyonunun esnekliğinin (Bölüm 3.2.1) görsel kanıtı olur.

## Faz 3 — Kapsam Genişletme

### Deney 6: Kapsam 3 (Embodied Carbon)
- **Kaynak:** Donanım üreticilerinin sürdürülebilirlik raporları (literatür
  taraması — API değil): AWS/Dell/HPE'nin sunucu başına "üretim karbonu"
  tahminleri.
- Sunucu-saat başına sabit bir üretim-karbonu payı amaç fonksiyonuna eklenir,
  Kapsam 2 sonuçlarıyla karşılaştırılır.

### (Opsiyonel) Çoklu Bölge Desteği
- Deney 1+2'nin kesişimi: 3-4 bölgenin (fiyat, karbon) verisiyle, görevlerin
  en uygun bölgeye yönlendirilmesi simüle edilir.

## Faz 4 — Yazım ve Teslim
- Deneysel sonuçların tez Bölüm 4 (Bulgular) olarak yazılması.
- Grafik/tabloların tez formatına uyarlanması, sunum hazırlığı.

---

## Önerilen Sıra

1. Deney 1 (karbon) ve Deney 2 (fiyat) paralel yürütülebilir — ikisi de
  bağımsız, API entegrasyonu benzer şekilde yapılır.
2. Deney 3 (gerçek trafik) bunlardan sonra — model yeniden eğitimi gerektirir.
3. Deney 4-5 hızlı, veri hazır olduğunda aynı gün tamamlanabilir.
4. Deney 6 ve çoklu bölge, süre kalırsa eklenecek "bonus" kapsam.

Hangi deneyden başlamak istersin? EPİAŞ kaydı biraz zaman alabileceği için,
önce UK Carbon Intensity API ile hızlı bir prototip yapıp mantığı doğrulayıp
sonra Türkiye verisine geçmek pratik bir sıra olur.
