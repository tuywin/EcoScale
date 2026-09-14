"""Tum katmanlari (Veri -> Tahmin -> Optimizasyon) tek bir simulasyon akisinda birlestirir."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ecoscale import optimizer
from ecoscale.data import generate_dataset
from ecoscale.forecasting import ForecastResult, train_forecaster

DEFAULT_TASKS = [
    {"name": "Veritabani Yedekleme", "start_hour_idx": 0, "deadline_window_hours": 10, "duration_hours": 2, "power_kw": 4.0},
    {"name": "Buyuk Veri Isleme (ETL)", "start_hour_idx": 24, "deadline_window_hours": 12, "duration_hours": 3, "power_kw": 6.0},
    {"name": "Batch Raporlama", "start_hour_idx": 48, "deadline_window_hours": 8, "duration_hours": 1, "power_kw": 2.5},
]


@dataclass
class SimulationConfig:
    days: int = 120
    capacity_per_server: float = 60.0   # bir sunucunun karsilayabildigi req/sn
    power_per_server_kw: float = 0.35   # sunucu basina saatlik enerji tuketimi (kWh)
    cost_per_server_hour: float = 0.12  # C_birim ($/saat)
    alpha: float = 0.5
    beta: float = 0.5


@dataclass
class SimulationResult:
    dataset: pd.DataFrame
    forecast: ForecastResult
    test_df: pd.DataFrame
    reactive_servers: np.ndarray
    proactive_servers: np.ndarray
    reactive_obj: optimizer.ObjectiveBreakdown
    proactive_obj: optimizer.ObjectiveBreakdown
    reactive_sla_violations: int
    proactive_sla_violations: int
    task_shift_df: pd.DataFrame
    scenario_df: pd.DataFrame


def run_simulation(config: SimulationConfig) -> SimulationResult:
    dataset = generate_dataset(days=config.days)
    forecast = train_forecaster(dataset)
    test_df = forecast.test_df.reset_index(drop=True)

    actual_traffic = test_df["traffic_rps"].to_numpy()
    predicted_traffic = test_df["predicted_traffic"].to_numpy()
    carbon = test_df["carbon_intensity"].to_numpy()

    reactive_servers = optimizer.reactive_schedule(actual_traffic, config.capacity_per_server)
    proactive_servers = optimizer.proactive_schedule(predicted_traffic, config.capacity_per_server)

    reactive_consumption = optimizer.energy_consumption(reactive_servers, config.power_per_server_kw)
    proactive_consumption = optimizer.energy_consumption(proactive_servers, config.power_per_server_kw)

    reactive_obj = optimizer.objective_function(
        config.cost_per_server_hour, reactive_servers, carbon, reactive_consumption, config.alpha, config.beta
    )
    proactive_obj = optimizer.objective_function(
        config.cost_per_server_hour, proactive_servers, carbon, proactive_consumption, config.alpha, config.beta
    )

    reactive_sla = optimizer.sla_violation_hours(actual_traffic, reactive_servers, config.capacity_per_server)
    proactive_sla = optimizer.sla_violation_hours(actual_traffic, proactive_servers, config.capacity_per_server)

    task_shift_df = optimizer.shift_background_tasks(dataset, DEFAULT_TASKS)
    scenario_df = optimizer.classify_all(dataset.tail(24 * 7).reset_index(drop=True))

    return SimulationResult(
        dataset=dataset,
        forecast=forecast,
        test_df=test_df,
        reactive_servers=reactive_servers,
        proactive_servers=proactive_servers,
        reactive_obj=reactive_obj,
        proactive_obj=proactive_obj,
        reactive_sla_violations=reactive_sla,
        proactive_sla_violations=proactive_sla,
        task_shift_df=task_shift_df,
        scenario_df=scenario_df,
    )
