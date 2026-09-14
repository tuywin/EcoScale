"""Optimizasyon Katmani: hibrit amac fonksiyonu, proaktif olceklendirme ve
karbon-bilincli gorev kaydirma (Carbon-Aware Task Shifting).

Tez Bolum 3.2'deki formulasyonu birebir uygular:
    Z = alpha * sum(C_birim * S_aktif(t)) + beta * sum(I_karbon(t) * E_tuketim(t))
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


def required_servers(traffic: np.ndarray, capacity_per_server: float) -> np.ndarray:
    return np.maximum(1, np.ceil(traffic / capacity_per_server)).astype(int)


def reactive_schedule(
    actual_traffic: np.ndarray,
    capacity_per_server: float,
    warmup_hours: int = 1,
    utilization_target: float = 0.7,
) -> np.ndarray:
    """Geleneksel esik-tabanli auto-scaling.

    Iki gercekci kisit modellenir: (1) karar, warmup_hours once gozlemlenen trafige
    gore verilir (cold-start gecikmesi) — kademeli gunluk trafik degisimini
    yakalayabilir ama ani sicramalari (Sekil 1.1) kacirir; (2) flapping'i onlemek
    icin sistemler genellikle dusuk bir hedef kullanim orani (ornegin %70) ile
    calisir, bu da surekli bir tampon kapasite (kaynak israfi) anlamina gelir.
    """
    delayed_traffic = np.concatenate([np.full(warmup_hours, actual_traffic[0]), actual_traffic[:-warmup_hours]])
    effective_capacity = capacity_per_server * utilization_target
    return required_servers(delayed_traffic, effective_capacity)


def proactive_schedule(predicted_traffic: np.ndarray, capacity_per_server: float, safety_margin: float = 1.15) -> np.ndarray:
    """EcoScale: ML tahminine gore sunucuyu trafik gelmeden hazirlar, gecikme olmaz."""
    return required_servers(predicted_traffic * safety_margin, capacity_per_server)


def sla_violation_hours(actual_traffic: np.ndarray, servers: np.ndarray, capacity_per_server: float) -> int:
    return int(np.sum(servers * capacity_per_server < actual_traffic))


def energy_consumption(servers: np.ndarray, power_per_server_kw: float) -> np.ndarray:
    return servers * power_per_server_kw


@dataclass
class ObjectiveBreakdown:
    z_score: float
    total_cost: float
    total_carbon_g: float


def objective_function(
    cost_per_server_hour: float,
    servers: np.ndarray,
    carbon_intensity: np.ndarray,
    consumption_kwh: np.ndarray,
    alpha: float,
    beta: float,
) -> ObjectiveBreakdown:
    total_cost = float(np.sum(cost_per_server_hour * servers))
    total_carbon_g = float(np.sum(carbon_intensity * consumption_kwh))
    z_score = alpha * total_cost + beta * total_carbon_g
    return ObjectiveBreakdown(z_score=z_score, total_cost=total_cost, total_carbon_g=total_carbon_g)


def find_greenest_slot(carbon_window: np.ndarray, duration_hours: int) -> tuple[int, float]:
    """duration_hours uzunlugundaki pencerede en dusuk ortalama karbon yogunluguna sahip baslangic saatini bulur."""
    best_idx, best_avg = 0, float("inf")
    last_start = len(carbon_window) - duration_hours
    for start in range(max(last_start, 0) + 1):
        avg = carbon_window[start:start + duration_hours].mean()
        if avg < best_avg:
            best_avg, best_idx = avg, start
    return best_idx, best_avg


def shift_background_tasks(df: pd.DataFrame, tasks: list[dict]) -> pd.DataFrame:
    """Dusuk oncelikli arka plan gorevlerini (tasks), kendi deadline penceresi icinde
    en temiz saatlere kaydirir ve hemen-calistir senaryosuyla karsilastirir.

    Her task: {name, start_hour_idx, deadline_window_hours, duration_hours, power_kw}
    """
    rows = []
    carbon = df["carbon_intensity"].to_numpy()
    for task in tasks:
        start = task["start_hour_idx"]
        window = task["deadline_window_hours"]
        duration = task["duration_hours"]
        power_kw = task["power_kw"]

        window_carbon = carbon[start:start + window]
        immediate_avg = window_carbon[:duration].mean()
        best_offset, best_avg = find_greenest_slot(window_carbon, duration)

        energy = power_kw * duration
        immediate_carbon_g = immediate_avg * energy
        shifted_carbon_g = best_avg * energy

        rows.append(
            {
                "task": task["name"],
                "immediate_start": df["timestamp"].iloc[start],
                "shifted_start": df["timestamp"].iloc[start + best_offset],
                "immediate_carbon_intensity": round(immediate_avg, 1),
                "shifted_carbon_intensity": round(best_avg, 1),
                "carbon_saved_g": round(immediate_carbon_g - shifted_carbon_g, 1),
                "carbon_saved_pct": round((1 - shifted_carbon_g / immediate_carbon_g) * 100, 1) if immediate_carbon_g else 0.0,
            }
        )
    return pd.DataFrame(rows)


def classify_scenario(traffic_pct: float, carbon_pct: float) -> tuple[str, str, str]:
    """Tablo 3.3'teki S1-S5 karar senaryolarina gore siniflandirma (persentil tabanli esikler)."""
    traffic_level = "Dusuk" if traffic_pct < 0.33 else ("Yuksek" if traffic_pct > 0.66 else "Orta")
    carbon_level = "Dusuk" if carbon_pct < 0.33 else ("Yuksek" if carbon_pct > 0.66 else "Orta")

    if traffic_level == "Dusuk" and carbon_level == "Dusuk":
        return "S1", "Minimum sunucu calistir", "Enerji tasarrufu"
    if traffic_level == "Yuksek" and carbon_level == "Dusuk":
        return "S2", "Olceklendirme yap", "Performans korunur"
    if traffic_level == "Dusuk" and carbon_level == "Yuksek":
        return "S3", "Gorevleri ertele", "Karbon azaltilir"
    if traffic_level == "Yuksek" and carbon_level == "Yuksek":
        return "S4", "Kismi olceklendirme ve gorev kaydirma", "Dengeli optimizasyon"
    return "S5", "Standart calisma modu", "Kararli sistem davranisi"


def classify_all(df: pd.DataFrame) -> pd.DataFrame:
    traffic_pct = df["traffic_rps"].rank(pct=True)
    carbon_pct = df["carbon_intensity"].rank(pct=True)
    labels = [classify_scenario(t, c) for t, c in zip(traffic_pct, carbon_pct)]
    out = df[["timestamp", "traffic_rps", "carbon_intensity"]].copy()
    out["scenario"], out["decision"], out["expected_outcome"] = zip(*labels)
    return out
