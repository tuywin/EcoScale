"""EcoScale Canli Karbon-Bilincli Zamanlama Motoru.

Tez Tablo 3.1'de tanimlanan APScheduler rolunun ("karbon yogunlugu sinyallerini
arka planda dinleyerek, dusuk oncelikli gorevleri tetikleyen veya erteleyen
proaktif zamanlama motoru") calisan karsiligidir. Streamlit surecinden bagimsiz,
kendi basina calisan bir servistir: her "tick" te simulasyon saatini bir ileri
alir, ML tahmin motorundan gelen trafik ongorusune gore proaktif sunucu sayisina
karar verir ve bekleyen arka plan gorevlerini ya hemen calistirir ya da sebeke
karbon yogunlugu dusene kadar erteler. Durumunu .state/live_state.json dosyasina
yazar; Streamlit arayuzu bu dosyayi okuyarak sonuclari canli gosterir.

Calistirma:
    python -m ecoscale.live_engine --tick-seconds 3
"""

import argparse
import os
import signal
import sys
from collections import deque
from datetime import datetime, timezone

import numpy as np
from apscheduler.schedulers.blocking import BlockingScheduler

from ecoscale import live_state, optimizer
from ecoscale.data import generate_dataset
from ecoscale.forecasting import FEATURE_COLUMNS, train_forecaster

HISTORY_MAXLEN = 300

TASK_TEMPLATES = [
    {"name": "Veritabani Yedekleme", "every_hours": 18, "deadline_window_hours": 10, "duration_hours": 2, "power_kw": 4.0},
    {"name": "Buyuk Veri Isleme (ETL)", "every_hours": 14, "deadline_window_hours": 12, "duration_hours": 3, "power_kw": 6.0},
    {"name": "Batch Raporlama", "every_hours": 10, "deadline_window_hours": 8, "duration_hours": 1, "power_kw": 2.5},
]


class LiveEngine:
    def __init__(self, capacity, power_kw, cost_hour, alpha, train_days=120, pool_days=200):
        self.capacity = capacity
        self.power_kw = power_kw
        self.cost_hour = cost_hour
        self.alpha = alpha
        self.beta = 1 - alpha

        full = generate_dataset(days=pool_days)
        split_idx = int(len(full) * (train_days / pool_days))
        forecast = train_forecaster(full.iloc[: split_idx + int(len(full) * 0.15)].reset_index(drop=True))
        self.model = forecast.model

        self.pool = full.iloc[split_idx:].reset_index(drop=True).copy()
        self.pool["traffic_pct"] = self.pool["traffic_rps"].rank(pct=True)
        self.pool["carbon_pct"] = self.pool["carbon_intensity"].rank(pct=True)
        self.cursor = 0

        self.history = deque(maxlen=HISTORY_MAXLEN)
        self.pending_tasks = []
        self.task_hour_counters = {t["name"]: 0 for t in TASK_TEMPLATES}
        self.next_task_id = 1
        self.sim_hour = 0

        self.cumulative_cost = 0.0
        self.cumulative_carbon_g = 0.0
        self.tasks_run_immediately = 0
        self.tasks_shifted = 0

    def _row(self, offset=0):
        idx = (self.cursor + offset) % len(self.pool)
        return self.pool.iloc[idx]

    def _spawn_tasks(self):
        for tpl in TASK_TEMPLATES:
            self.task_hour_counters[tpl["name"]] += 1
            if self.task_hour_counters[tpl["name"]] >= tpl["every_hours"]:
                self.task_hour_counters[tpl["name"]] = 0
                self.pending_tasks.append(
                    {
                        "id": self.next_task_id,
                        "name": tpl["name"],
                        "remaining_deadline": tpl["deadline_window_hours"],
                        "duration_hours": tpl["duration_hours"],
                        "power_kw": tpl["power_kw"],
                        "spawned_at_hour": self.sim_hour,
                    }
                )
                self.next_task_id += 1

    def _green_threshold(self):
        if len(self.history) < 6:
            return float("inf")
        recent_carbon = [h["carbon_intensity"] for h in self.history]
        return float(np.percentile(recent_carbon, 35))

    def _process_tasks(self, current_carbon):
        decisions = []
        threshold = self._green_threshold()
        still_pending = []
        for task in self.pending_tasks:
            task["remaining_deadline"] -= 1
            must_run_now = task["remaining_deadline"] <= task["duration_hours"]
            is_green_now = current_carbon <= threshold

            if must_run_now or is_green_now:
                energy = task["power_kw"] * task["duration_hours"]
                carbon_g = current_carbon * energy
                reason = "SON TESLIM TARIHI" if must_run_now and not is_green_now else "TEMIZ ENERJI PENCERESI"
                decisions.append(
                    {"task": task["name"], "reason": reason, "carbon_intensity": round(float(current_carbon), 1)}
                )
                self.cumulative_carbon_g += carbon_g
                if reason == "TEMIZ ENERJI PENCERESI":
                    self.tasks_shifted += 1
                else:
                    self.tasks_run_immediately += 1
            else:
                still_pending.append(task)

        self.pending_tasks = still_pending
        return decisions

    def tick(self):
        current = self._row(0)
        next_row = self._row(1)

        predicted_next_traffic = float(self.model.predict(next_row[FEATURE_COLUMNS].to_frame().T)[0])
        active_servers = int(optimizer.proactive_schedule(np.array([predicted_next_traffic]), self.capacity)[0])
        consumption = optimizer.energy_consumption(np.array([active_servers]), self.power_kw)[0]

        cost_tick = self.cost_hour * active_servers
        carbon_tick = float(current["carbon_intensity"]) * consumption
        self.cumulative_cost += cost_tick
        self.cumulative_carbon_g += carbon_tick

        self._spawn_tasks()
        task_events = self._process_tasks(float(current["carbon_intensity"]))
        scenario, decision, outcome = optimizer.classify_scenario(current["traffic_pct"], current["carbon_pct"])

        entry = {
            "sim_hour": self.sim_hour,
            "timestamp": str(current["timestamp"]),
            "traffic_rps": round(float(current["traffic_rps"]), 1),
            "predicted_next_traffic": round(predicted_next_traffic, 1),
            "carbon_intensity": round(float(current["carbon_intensity"]), 1),
            "active_servers": active_servers,
            "cost_tick": round(cost_tick, 4),
            "carbon_tick_g": round(carbon_tick, 2),
            "scenario": scenario,
            "decision": decision,
            "expected_outcome": outcome,
            "task_events": task_events,
            "pending_task_count": len(self.pending_tasks),
        }
        self.history.append(entry)
        self.cursor = (self.cursor + 1) % len(self.pool)
        self.sim_hour += 1

        state = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "config": {
                "capacity": self.capacity,
                "power_kw": self.power_kw,
                "cost_hour": self.cost_hour,
                "alpha": self.alpha,
                "beta": self.beta,
            },
            "current": entry,
            "cumulative": {
                "total_cost": round(self.cumulative_cost, 2),
                "total_carbon_kg": round(self.cumulative_carbon_g / 1000, 2),
                "tasks_run_immediately": self.tasks_run_immediately,
                "tasks_shifted": self.tasks_shifted,
            },
            "pending_tasks": self.pending_tasks,
            "history": list(self.history),
        }
        live_state.write_state(state)


def main():
    parser = argparse.ArgumentParser(description="EcoScale canli karbon-bilincli zamanlama motoru")
    parser.add_argument("--tick-seconds", type=float, default=3.0, help="Her tick'in gercek sure karsiligi (1 simulasyon saati)")
    parser.add_argument("--capacity", type=float, default=60.0)
    parser.add_argument("--power-kw", type=float, default=0.35)
    parser.add_argument("--cost-hour", type=float, default=0.12)
    parser.add_argument("--alpha", type=float, default=0.5)
    args = parser.parse_args()

    engine = LiveEngine(args.capacity, args.power_kw, args.cost_hour, args.alpha)
    live_state.write_pid(os.getpid())

    scheduler = BlockingScheduler()
    scheduler.add_job(engine.tick, "interval", seconds=args.tick_seconds, id="ecoscale_tick", max_instances=1, coalesce=True)

    def handle_exit(signum, frame):
        scheduler.shutdown(wait=False)
        live_state.clear_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    print(f"EcoScale canli motor baslatildi (PID={os.getpid()}, tick={args.tick_seconds}s)", flush=True)
    scheduler.start()


if __name__ == "__main__":
    main()
