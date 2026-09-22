"""Ulke Karsilastirmasi: Turkiye ve AB ulkelerinin karbon yogunlugu (Ember).

Ember (ember-energy.org), 200'den fazla ulke icin ucretsiz, kayit
gerektirmeyen bir "Yearly Electricity Data" CSV'si yayinlar. Bu modul, o
dosyadan yalnizca Turkiye + 27 AB uyesi + Ingiltere'nin en guncel yillik
ortalama sebeke karbon yogunlugunu (gCO2e/kWh) filtreleyip kucuk bir CSV
olarak onbelleklenir.

Onemli metodolojik not: bu YILLIK ORTALAMA degerlerdir (saatlik degil).
UK Carbon Intensity API'den (ecoscale/real_data.py) gelen saatlik veriyle
dogrudan karsilastirilmamalidir; iki kaynagin hesaplama metodolojisi ve
zaman penceresi farklidir. Bu modul, "hangi ulkede/bolgede is yuku
calistirmak ortalamada daha az karbonlu olurdu" sorusuna, cok-bolgeli
gorev yonlendirme (multi-region routing) fikri icin kaba bir kiyas sunar.
"""

from pathlib import Path

import pandas as pd
import requests

EMBER_URL = "https://files.ember-energy.org/public-downloads/generation/outputs/release_generation_yearly_global.csv"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data_real"
CACHE_FILE = CACHE_DIR / "ember_country_carbon_intensity.csv"

EU_MEMBERS = {
    "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark",
    "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland",
    "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands",
    "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden",
}
EXTRA_COUNTRIES = {"Türkiye", "United Kingdom"}


def _download_and_filter() -> pd.DataFrame:
    response = requests.get(EMBER_URL, timeout=60)
    response.raise_for_status()

    from io import StringIO

    full = pd.read_csv(StringIO(response.text))
    mask = (
        (full["Area type"] == "Country or economy")
        & (full["Electricity source"] == "Total generation")
        & (full["Area"].isin(EU_MEMBERS | EXTRA_COUNTRIES))
    )
    filtered = full[mask].copy()
    latest_per_country = filtered.sort_values("Year").groupby("Area", as_index=False).tail(1)

    result = latest_per_country[["Area", "ISO 3 code", "Year", "Emissions intensity (gCO2e/kWh)"]].copy()
    result.columns = ["country", "iso3", "year", "carbon_intensity"]
    result["is_eu_member"] = result["country"].isin(EU_MEMBERS)
    result["is_turkey"] = result["country"] == "Türkiye"
    return result.sort_values("carbon_intensity").reset_index(drop=True)


def load_or_fetch(force_refresh: bool = False) -> pd.DataFrame:
    if not force_refresh and CACHE_FILE.exists():
        return pd.read_csv(CACHE_FILE)

    CACHE_DIR.mkdir(exist_ok=True)
    result = _download_and_filter()
    result.to_csv(CACHE_FILE, index=False)
    return result


if __name__ == "__main__":
    df = load_or_fetch(force_refresh=True)
    print(f"{len(df)} ulke -> {CACHE_FILE}")
    print(df.to_string(index=False))
