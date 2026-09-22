"""Deney 3: Gercek Trafik/Is Yuku Verisi (Wikimedia Pageviews API).

Wikimedia Foundation'in ucretsiz, kayit gerektirmeyen "Pageviews" REST API'si
(wikimedia.org/api/rest_v1/metrics/pageviews), Ingilizce Wikipedia'nin
SAATLIK toplam goruntulenme sayisini dondurur. Bu, gercek bir web servisinin
kullanici trafigini temsil eden, gunluk/haftalik periyodiklik ve organik
gurultu iceren gercek bir zaman serisidir.

Azure Public Dataset (VM CPU trace) alternatifi degerlendirildi ancak
dosyalari (~GB'larca, ozel arac gerektiren format) bu deney icin pratik
degildi; Wikipedia Pageviews API tek istekte hafif bir JSON yaniti ile
aylarca saatlik veri sagladigi icin tercih edildi.

Onemli metodolojik not: Wikipedia'nin mutlak goruntulenme sayisi (~12 milyon/
saat) EcoScale'in "sunucu kapasitesi" (req/sn) olcegiyle kiyaslanamaz. Bu
yuzden seri, ORANTISAL olarak (ortalamasi hedef degere gelecek sekilde)
yeniden olceklendirilir — bu, serinin GORECELI dalgalanma/sekil bilgisini
(gercek gunluk/haftalik desen, gercek gurultu) korurken, mutlak buyuklugu
EcoScale'in sunucu kapasitesi varsayimlarina uyumlu hale getirir.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

API_BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews/aggregate"
HEADERS = {"User-Agent": "EcoScale-Thesis-Research/1.0 (Manisa Celal Bayar Universitesi, academic use)"}
CACHE_DIR = Path(__file__).resolve().parent.parent / "data_real"
CACHE_FILE = CACHE_DIR / "wikipedia_hourly_pageviews.csv"

FEATURE_COLUMNS = [
    "hour",
    "day_of_week",
    "is_weekend",
    "traffic_lag_1h",
    "traffic_lag_24h",
    "traffic_rolling_6h",
]


def fetch_hourly_views(days: int = 200, project: str = "en.wikipedia") -> pd.DataFrame:
    # Pageviews API'si son ~48 saati islemedigi icin bir tampon payi birakiyoruz.
    end_date = datetime.now(timezone.utc) - timedelta(days=2)
    start_date = end_date - timedelta(days=days)

    url = (
        f"{API_BASE}/{project}/all-access/all-agents/hourly/"
        f"{start_date.strftime('%Y%m%d00')}/{end_date.strftime('%Y%m%d00')}"
    )
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    items = response.json()["items"]

    df = pd.DataFrame(
        {
            "timestamp": [pd.to_datetime(i["timestamp"], format="%Y%m%d%H") for i in items],
            "views": [i["views"] for i in items],
        }
    )
    return df.sort_values("timestamp").reset_index(drop=True)


def load_or_fetch(days: int = 200, force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh and CACHE_FILE.exists():
        cached = pd.read_csv(CACHE_FILE, parse_dates=["timestamp"])
        if len(cached) >= days * 24 * 0.9:
            return cached

    CACHE_DIR.mkdir(exist_ok=True)
    df = fetch_hourly_views(days=days)
    df.to_csv(CACHE_FILE, index=False)
    return df


def build_traffic_dataset(n_days: int, target_mean: float = 560.0) -> pd.DataFrame:
    """Gercek Wikipedia trafigini EcoScale olcegine tasir ve ozellik muhendisligi uygular."""
    raw = load_or_fetch(days=max(200, n_days + 10)).tail(n_days * 24).reset_index(drop=True)

    scale = target_mean / raw["views"].mean()
    traffic = (raw["views"].to_numpy() * scale).round(1)

    timestamps = raw["timestamp"]
    hour = timestamps.dt.hour.to_numpy()
    dow = timestamps.dt.dayofweek.to_numpy()
    is_weekend = (dow >= 5).astype(float)

    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "hour": hour,
            "day_of_week": dow,
            "is_weekend": is_weekend,
            "traffic_rps": traffic,
        }
    )
    df["traffic_lag_1h"] = df["traffic_rps"].shift(1)
    df["traffic_lag_24h"] = df["traffic_rps"].shift(24)
    df["traffic_rolling_6h"] = df["traffic_rps"].rolling(6).mean()
    return df.dropna().reset_index(drop=True)


if __name__ == "__main__":
    raw = load_or_fetch(days=200, force_refresh=True)
    print(f"{len(raw)} saatlik gercek trafik verisi -> {CACHE_FILE}")
    print(raw["views"].describe())
