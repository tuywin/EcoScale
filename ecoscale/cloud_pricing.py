"""Deney 2: Gercek Bulut Fiyatlandirma Verisi (Azure Retail Prices API).

Azure Retail Prices API (prices.azure.com) tamamen acik ve kimlik dogrulama
gerektirmeyen bir REST API'dir; sorgu parametreleriyle sunucu tarafinda
filtreleme yapar (AWS Price List Bulk API'nin aksine — o dosyalar bolge
basina yuzlerce MB oldugu ve indirilmeden filtrelenemedigi icin burada
kullanilmamistir).

Onemli gercek bulgu: Ne Azure'un ne de AWS'in Turkiye'de fiziksel bir veri
merkezi bolgesi bulunmaktadir (asagida REGION_MAP icindeki QATAR_CENTRAL,
Turkiye merkezli dagitimlar icin pratikte en cok tercih edilen yakin
bolgelerden biridir, Turkiye'nin kendi karbon yogunlugunu TEMSIL ETMEZ).

Sectigimiz SKU (Standard_D2s_v5) neredeyse tum Azure bolgelerinde mevcut,
genel amacli bir sanal makine tipidir; boylece bolgeler arasi fiyat
kiyaslamasi ayni "urun" uzerinden adil sekilde yapilabilir.
"""

from pathlib import Path

import pandas as pd
import requests

API_BASE = "https://prices.azure.com/api/retail/prices"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data_real"
CACHE_FILE = CACHE_DIR / "azure_regional_prices.csv"
DEFAULT_SKU = "Standard_D2s_v5"
DEFAULT_METER_NAME = "D2s v5"

# Azure bolgesi -> (Ember/AB karsilastirma tablosundaki ulke adi, ISO3, aciklama)
REGION_MAP = {
    "westeurope": ("Netherlands", "NLD", None),
    "northeurope": ("Ireland", "IRL", None),
    "uksouth": ("United Kingdom", "GBR", None),
    "francecentral": ("France", "FRA", None),
    "germanywestcentral": ("Germany", "DEU", None),
    "swedencentral": ("Sweden", "SWE", None),
    "polandcentral": ("Poland", "POL", None),
    "italynorth": ("Italy", "ITA", None),
    "spaincentral": ("Spain", "ESP", None),
    "austriaeast": ("Austria", "AUT", None),
    "qatarcentral": ("Türkiye (en yakın bölge)", "TUR", "Azure'un Türkiye'de bölgesi yok; coğrafi olarak en yakın pratik seçenek"),
}


def _fetch_region_price(region: str, sku: str = DEFAULT_SKU, meter_name: str = DEFAULT_METER_NAME) -> float | None:
    filter_query = (
        f"armRegionName eq '{region}' and armSkuName eq '{sku}' "
        f"and meterName eq '{meter_name}' and priceType eq 'Consumption'"
    )
    response = requests.get(API_BASE, params={"api-version": "2023-01-01-preview", "$filter": filter_query}, timeout=20)
    response.raise_for_status()
    items = [i for i in response.json()["Items"] if "Windows" not in i["productName"]]
    return items[0]["retailPrice"] if items else None


def fetch_all(force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh and CACHE_FILE.exists():
        return pd.read_csv(CACHE_FILE)

    rows = []
    for region, (country, iso3, note) in REGION_MAP.items():
        price = _fetch_region_price(region)
        if price is not None:
            rows.append({"region": region, "country": country, "iso3": iso3, "price_usd_hour": price, "note": note or ""})

    df = pd.DataFrame(rows).sort_values("price_usd_hour").reset_index(drop=True)
    CACHE_DIR.mkdir(exist_ok=True)
    df.to_csv(CACHE_FILE, index=False)
    return df


if __name__ == "__main__":
    df = fetch_all(force_refresh=True)
    print(f"{len(df)} bolge -> {CACHE_FILE}")
    print(df.to_string(index=False))
