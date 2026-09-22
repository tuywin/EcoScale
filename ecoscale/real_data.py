"""Deney 1: Gercek Sebeke Karbon Yogunlugu Verisi (UK Carbon Intensity API).

Tez Bolum 2.4.2'deki karbon yogunlugu formulasyonunun gercek dunya verisiyle
sinanmasi icin, National Energy System Operator'in ucretsiz ve kayit
gerektirmeyen "Carbon Intensity API"sinden (api.carbonintensity.org.uk)
Buyuk Britanya sebekesinin gercek yarim-saatlik gCO2eq/kWh degerleri cekilir.

API tek istekte en fazla 31 gunluk araligi destekledigi icin (400 Bad Request
ile sinirlandiriliyor), istekler <=28 gunluk parcalara bolunur. Sonuc, ag
erisimi olmadan tekrar kullanilabilmesi icin data_real/ altina CSV olarak
onbelleklenir.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

API_BASE = "https://api.carbonintensity.org.uk/intensity"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data_real"
CACHE_FILE = CACHE_DIR / "uk_carbon_intensity.csv"
CHUNK_DAYS = 28


def _fetch_chunk(start: datetime, end: datetime) -> list[dict]:
    url = f"{API_BASE}/{start.strftime('%Y-%m-%dT%H:%MZ')}/{end.strftime('%Y-%m-%dT%H:%MZ')}"
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()["data"]


def fetch_uk_carbon_intensity(days: int = 180, end_date: datetime | None = None) -> pd.DataFrame:
    """UK Carbon Intensity API'den son `days` gunun yarim-saatlik verisini ceker.

    `actual` degeri henuz yayinlanmamis (yakin gecmis/gelecek) yarim-saatler
    icin `forecast` ile doldurulur.
    """
    end_date = end_date or datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    rows = []
    cursor = start_date
    while cursor < end_date:
        chunk_end = min(cursor + timedelta(days=CHUNK_DAYS), end_date)
        rows.extend(_fetch_chunk(cursor, chunk_end))
        cursor = chunk_end

    df = pd.DataFrame(
        {
            "timestamp": [pd.to_datetime(r["from"]) for r in rows],
            "carbon_intensity_actual": [r["intensity"]["actual"] for r in rows],
            "carbon_intensity_forecast": [r["intensity"]["forecast"] for r in rows],
        }
    )
    df["carbon_intensity"] = df["carbon_intensity_actual"].fillna(df["carbon_intensity_forecast"])
    df = df.dropna(subset=["carbon_intensity"]).drop_duplicates(subset="timestamp").sort_values("timestamp")
    return df.reset_index(drop=True)


def resample_hourly(df: pd.DataFrame) -> pd.Series:
    """Yarim-saatlik veriyi projenin geri kalaniyla uyumlu olacak sekilde saatlige indirger."""
    hourly = df.set_index("timestamp")["carbon_intensity"].resample("h").mean()
    return hourly.dropna()


def load_or_fetch(days: int = 180, force_refresh: bool = False) -> pd.Series:
    """Onbellekten okur; yoksa veya `force_refresh=True` ise API'den ceker ve onbelleğe yazar."""
    if not force_refresh and CACHE_FILE.exists():
        cached = pd.read_csv(CACHE_FILE, parse_dates=["timestamp"])
        hourly = resample_hourly(cached)
        if len(hourly) >= days * 24 * 0.9:  # onbellek yeterince genisse tekrar cekme
            return hourly

    CACHE_DIR.mkdir(exist_ok=True)
    raw = fetch_uk_carbon_intensity(days=days)
    raw.to_csv(CACHE_FILE, index=False)
    return resample_hourly(raw)


def get_carbon_series(n_hours: int, force_refresh: bool = False) -> "list[float]":
    """Simulasyonun ihtiyac duydugu uzunlukta gercek karbon yogunlugu serisi dondurur.

    Gercek veri istenenden kisaysa dongusel olarak tekrarlanir (tiling); tarih
    hizalamasi degil, sadece gercek degerlerin dagilimi/deseni onemlidir.
    """
    hourly = load_or_fetch(days=max(180, n_hours // 24 + 7), force_refresh=force_refresh)
    values = hourly.to_numpy()
    if len(values) == 0:
        raise RuntimeError("UK Carbon Intensity API'den veri alinamadi.")
    tiled = (values.tolist() * (n_hours // len(values) + 1))[:n_hours]
    return tiled


if __name__ == "__main__":
    series = load_or_fetch(days=180, force_refresh=True)
    print(f"{len(series)} saatlik gercek karbon yogunlugu verisi cekildi -> {CACHE_FILE}")
    print(series.describe())
