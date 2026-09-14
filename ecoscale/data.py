"""Veri Toplama Katmani: sentetik trafik, sebeke karbon yogunlugu ve maliyet verisi uretimi.

Gercek bir bulut ortaminda bu katman; APM/monitoring araclarindan trafik metrikleri,
bulut saglayici API'lerinden fiyatlandirma ve elektricitymaps/WattTime gibi servislerden
anlik karbon yogunlugu verisi ceker. Simulasyon kapsaminda bu kaynaklar, tez Sekil 2.1'de
tanimlanan gunluk davranis oruntulerini (trafikte mesai saati piki, karbonda ogle
saatlerinde gunes uretimiyle dusus) yansitacak sekilde sentetik olarak uretilir.
"""

import numpy as np
import pandas as pd


def generate_dataset(days: int = 120, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    periods = days * 24
    timestamps = pd.date_range("2026-01-01", periods=periods, freq="h")

    hour = timestamps.hour.values
    dow = timestamps.dayofweek.values
    is_weekend = (dow >= 5).astype(float)

    # --- Trafik: mesai saatleri piki (10-18), hafta sonu dususu, kademeli buyume trendi ---
    daily_shape = np.exp(-((hour - 14) ** 2) / (2 * 4.5 ** 2))
    weekday_factor = np.where(is_weekend == 1, 0.55, 1.0)
    trend = 1.0 + np.arange(periods) / periods * 0.25
    noise = rng.normal(0, 0.05, periods)
    spikes = (rng.random(periods) < 0.01) * rng.uniform(0.3, 0.8, periods)
    traffic = (200 + 800 * daily_shape) * weekday_factor * trend + noise * 200 + spikes * 400
    traffic = np.clip(traffic, 50, None)

    # --- Karbon yogunlugu: ogle saatlerinde gunes ile dusus, sabah/aksam pikinde fosil yakit ---
    solar_dip = np.exp(-((hour - 13) ** 2) / (2 * 3.0 ** 2))
    evening_peak = np.exp(-((hour - 20) ** 2) / (2 * 2.0 ** 2))
    weather_drift = 40 * np.sin(np.arange(periods) / (24 * 7) * 2 * np.pi + 1.0)
    carbon = 420 - 180 * solar_dip + 90 * evening_peak + weather_drift
    carbon += rng.normal(0, 15, periods)
    carbon = np.clip(carbon, 60, 650)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "hour": hour,
            "day_of_week": dow,
            "is_weekend": is_weekend,
            "traffic_rps": traffic.round(1),
            "carbon_intensity": carbon.round(1),
        }
    )

    # Kisa vadeli tahmin icin lag/rolling ozellikler (Feature Engineering, Tablo 3.1 - Pandas)
    df["traffic_lag_1h"] = df["traffic_rps"].shift(1)
    df["traffic_lag_24h"] = df["traffic_rps"].shift(24)
    df["traffic_rolling_6h"] = df["traffic_rps"].rolling(6).mean()
    df = df.dropna().reset_index(drop=True)
    return df


if __name__ == "__main__":
    data = generate_dataset()
    data.to_csv("ecoscale_dataset.csv", index=False)
    print(f"{len(data)} satir uretildi -> ecoscale_dataset.csv")
