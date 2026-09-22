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
| 7 | [Ember Yearly Electricity Data](https://ember-energy.org/data/yearly-electricity-data/) | Türkiye + tüm AB ülkelerinin **yıllık ortalama** gCO₂e/kWh değeri | Kayıt gerektirmez, doğrudan CSV | Ücretsiz |
| 8 | [ENTSO-E Transparency Platform](https://transparency.entsoe.eu/) | Tüm Avrupa ülkeleri (+ Türkiye/TEİAŞ) için **saatlik** gerçek üretim/emisyon verisi | Ücretsiz kayıt + e-posta ile token talebi (~3 iş günü) | Ücretsiz |

---

## Faz 1 — Gerçek Veri Entegrasyonu

### ✅ Deney 1: Gerçek Karbon Yoğunluğu ile Yeniden Değerlendirme (TAMAMLANDI)
- **Kaynak:** UK Carbon Intensity API — `ecoscale/real_data.py`, dashboard'da
  "Sentetik / Gerçek" seçici. Sonuç: gerçek veride de ~%18 karbon tasarrufu
  (sentetik veride ~%20) — algoritma farklı şebeke profillerinde genelliyor.

### ✅ Deney 1b: Türkiye + AB Ülkeleri Karşılaştırması (TAMAMLANDI)
- **Kaynak:** Ember Yearly Electricity Data — `ecoscale/country_carbon.py`,
  dashboard bölüm 6. **Yıllık ortalama** (saatlik değil) ama tamamen gerçek veri.
- **Bulgu:** Türkiye 476 gCO₂e/kWh (2025) ile AB ortalamasının (~224) 2.1 katı;
  29 ülke arasında 4. en karbon-yoğun şebeke (sadece Polonya, Kıbrıs, Malta daha
  kirli). Bu, EcoScale'in Türkiye bağlamında görece yüksek etki potansiyeli
  taşıdığını gösteren güçlü bir bulgu.
- **Sıradaki adım — gerçek SAATLİK Türkiye/AB verisi:** Bunun için tek/birleşik
  kaynak **ENTSO-E Transparency Platform**. Kayıt tamamen ücretsiz ama hesap
  oluşturma kullanıcının kendi e-postasıyla yapılmalı (bkz. adımlar aşağıda) —
  bu adımı ben senin adına yapamam, hesap açma/kimlik doğrulama kullanıcının
  kendisine ait olmalı. Token'ı aldığında bana verirsen saatlik Türkiye+AB
  entegrasyonunu (Deney 1'in devamı olarak) hemen yaparım.
  1. https://transparency.entsoe.eu/ adresinden ücretsiz hesap oluştur.
  2. `transparency@entsoe.eu` adresine konu satırı "RESTful API access" olan
     bir e-posta gönder, gövdede kayıtlı e-posta adresini belirt.
  3. ~3 iş günü içinde onay gelir; hesap ayarlarından "Web API Security Token"
     oluşturulur.
  4. Token'ı bana ilet, `ecoscale/real_data.py` benzeri bir modülle Türkiye
     (TEİAŞ) ve seçili AB ülkelerinin saatlik verisini entegre edelim.
- **Alternatif (daha hızlı ama kayıt gerektiren):** EPİAŞ Şeffaflık Platformu —
  sadece Türkiye için, üretim kaynak dağılımından (kömür/doğalgaz/hidro/rüzgar/
  güneş MW) emisyon faktörleriyle saatlik karbon yoğunluğu türetilebilir.

### Deney 2: Gerçek Bulut Fiyatlandırmasıyla Maliyet Modeli
### ✅ Deney 2: Gerçek Bulut Fiyatlandırmasıyla Maliyet Modeli (TAMAMLANDI)
- **Kaynak:** Azure Retail Prices API (`ecoscale/cloud_pricing.py`). AWS Price List
  API kullanılmadı — bulk dosyalar bölge başına 400MB-9GB ve sunucu tarafında
  filtrelenemiyor; AWS'in filtrelenebilir "Query API"si ise AWS SDK + IAM
  kimlik bilgisi gerektirdiği için (kullanıcının kendi AWS hesabı olmadan
  yapılamaz) bu deneyde atlandı.
- **Ne değişti:** Sabit `C_birim` parametresi, dashboard'dan seçilen gerçek bir
  Azure bölgesinin (Standard_D2s_v5, Linux) gerçek saatlik fiyatıyla
  değiştirilebiliyor.
- **Doğrulanan iddia:** Tez Bölüm 1.3, madde 3 — "bölgelere göre saatlik
  enerji maliyeti ile karbon yoğunluğu her zaman paralel gitmiyor" savı; 11
  bölge üzerinde Pearson r≈0.60 (zayıf-orta korelasyon), Polonya ve İsveç
  neredeyse aynı fiyata sahipken ($0.115 vs $0.102/saat) karbon yoğunlukları
  17 kat farklı (591 vs 35 gCO₂e/kWh) — somut örnek.
- **Ek gerçek bulgu:** Ne Azure'un ne AWS'in Türkiye'de fiziksel bölgesi var;
  Qatar Central en yakın pratik seçenek olarak kullanıldı (sadece fiyat için,
  karbon verisi Ember'dan geliyor).

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
