"""Tahmin Katmani: Random Forest Regressor ile iş yükü (trafik) tahmini.

Tez Bolum 2.6'da secilen Random Forest algoritmasi kullanilarak, gecmis trafik ve
zaman ozniteliklerinden (saat, haftanin gunu, hafta sonu, lag/rolling degerler)
bir sonraki saatin trafigi tahmin edilir. Basari metrikleri (R^2, MAE, RMSE)
Tablo 3.1'de belirtilen Scikit-learn kutuphanesi ile hesaplanir.
"""

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

FEATURE_COLUMNS = [
    "hour",
    "day_of_week",
    "is_weekend",
    "traffic_lag_1h",
    "traffic_lag_24h",
    "traffic_rolling_6h",
]
TARGET_COLUMN = "traffic_rps"


@dataclass
class ForecastResult:
    model: RandomForestRegressor
    test_df: pd.DataFrame
    r2: float
    mae: float
    rmse: float


def train_forecaster(df: pd.DataFrame, test_ratio: float = 0.15) -> ForecastResult:
    split_idx = int(len(df) * (1 - test_ratio))
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:].copy()

    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train_df[FEATURE_COLUMNS], train_df[TARGET_COLUMN])

    predictions = model.predict(test_df[FEATURE_COLUMNS])
    test_df["predicted_traffic"] = predictions

    r2 = r2_score(test_df[TARGET_COLUMN], predictions)
    mae = mean_absolute_error(test_df[TARGET_COLUMN], predictions)
    rmse = mean_squared_error(test_df[TARGET_COLUMN], predictions) ** 0.5

    return ForecastResult(model=model, test_df=test_df, r2=r2, mae=mae, rmse=rmse)
