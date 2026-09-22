"""EcoScale - Karbon Ayak Izi ve Maliyet Odakli Akilli Bulut Kaynak Yonetimi Simulasyonu.

Kullanici Arayuzu Katmani (Streamlit). Calistirmak icin:
    streamlit run app.py
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ecoscale import live_state
from ecoscale.simulation import SimulationConfig, run_simulation

PROJECT_ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="EcoScale", page_icon="🌿", layout="wide")


@st.cache_data(show_spinner="Simulasyon calistiriliyor (veri uretimi + model egitimi)...")
def cached_simulation(days, capacity, power_kw, cost_hour, alpha, carbon_source):
    config = SimulationConfig(
        days=days,
        capacity_per_server=capacity,
        power_per_server_kw=power_kw,
        cost_per_server_hour=cost_hour,
        alpha=alpha,
        beta=1 - alpha,
        carbon_source=carbon_source,
    )
    return run_simulation(config)


st.title("🌿 EcoScale")
st.caption("Karbon Ayak İzi ve Maliyet Odaklı Akıllı Bulut Kaynak Yönetimi Simülasyonu")

with st.sidebar:
    st.header("Sistem Parametreleri")
    days = st.slider("Simüle edilen gün sayısı", 30, 180, 120, step=10)
    carbon_source_label = st.radio(
        "Karbon Yoğunluğu Verisi",
        ["Sentetik", "Gerçek (UK Carbon Intensity API)"],
        help="Gerçek seçeneği, National Energy System Operator'ın ücretsiz API'sinden çekilip önbelleklenen gerçek İngiltere şebeke verisini kullanır (Deney 1).",
    )
    carbon_source = "uk_real" if "Gerçek" in carbon_source_label else "synthetic"
    capacity = st.slider("Sunucu kapasitesi (req/sn)", 20, 150, 60, step=5)
    power_kw = st.slider("Sunucu güç tüketimi (kWh/saat)", 0.1, 1.0, 0.35, step=0.05)
    cost_hour = st.slider("Sunucu maliyeti ($/saat) — C_birim", 0.02, 0.50, 0.12, step=0.01)
    st.divider()
    alpha = st.slider("α — Maliyet ağırlığı", 0.0, 1.0, 0.5, step=0.05)
    st.metric("β — Karbon ağırlığı", f"{1 - alpha:.2f}")
    st.caption("α + β = 1. α'yı artırmak bütçe odaklı, β'yı artırmak çevre odaklı optimizasyona karşılık gelir.")

    st.divider()
    st.header("Canlı Motor (APScheduler)")
    engine_running = live_state.is_running()
    tick_seconds = st.slider("Tick süresi (sn) — 1 simülasyon saati", 0.5, 5.0, 2.0, step=0.5, disabled=engine_running)

    if engine_running:
        st.success(f"Çalışıyor (PID {live_state.read_pid()})")
        if st.button("■ Motoru Durdur", use_container_width=True):
            pid = live_state.read_pid()
            if pid:
                try:
                    os.kill(pid, signal.SIGTERM)
                except OSError:
                    pass
            live_state.clear_pid()
            st.rerun()
    else:
        st.warning("Çalışmıyor")
        if st.button("▶ Motoru Başlat", use_container_width=True):
            log_path = PROJECT_ROOT / ".state" / "live_engine.log"
            log_file = open(log_path, "a")
            subprocess.Popen(
                [
                    sys.executable, "-m", "ecoscale.live_engine",
                    "--tick-seconds", str(tick_seconds),
                    "--capacity", str(capacity),
                    "--power-kw", str(power_kw),
                    "--cost-hour", str(cost_hour),
                    "--alpha", str(alpha),
                ],
                cwd=str(PROJECT_ROOT),
                stdout=log_file,
                stderr=log_file,
                start_new_session=True,
            )
            time.sleep(1.5)
            st.rerun()

    live_autorefresh = st.checkbox("🔄 Canlı görünümü otomatik yenile", value=engine_running)

result = cached_simulation(days, capacity, power_kw, cost_hour, alpha, carbon_source)

if carbon_source == "uk_real":
    st.info(
        "🇬🇧 Karbon yoğunluğu verisi **UK Carbon Intensity API**'den (api.carbonintensity.org.uk) çekilen "
        "gerçek İngiltere şebeke verisidir. Trafik verisi henüz sentetiktir (Deney 3'te gerçek veriyle değiştirilecek).",
        icon="🔬",
    )

# --- KPI satırı ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Model Doğruluğu (R²)", f"{result.forecast.r2 * 100:.1f}%")
col2.metric("MAE", f"{result.forecast.mae:.1f} req/sn")

cost_saved = result.reactive_obj.total_cost - result.proactive_obj.total_cost
cost_saved_pct = (cost_saved / result.reactive_obj.total_cost * 100) if result.reactive_obj.total_cost else 0
carbon_saved_kg = (result.reactive_obj.total_carbon_g - result.proactive_obj.total_carbon_g) / 1000
carbon_saved_pct = (
    (result.reactive_obj.total_carbon_g - result.proactive_obj.total_carbon_g) / result.reactive_obj.total_carbon_g * 100
    if result.reactive_obj.total_carbon_g
    else 0
)

col3.metric("Tasarruf Edilen Maliyet", f"${cost_saved:,.2f}", f"{cost_saved_pct:.1f}%")
col4.metric("Engellenen Karbon", f"{carbon_saved_kg:,.1f} kg CO₂eq", f"{carbon_saved_pct:.1f}%")

col5, col6 = st.columns(2)
col5.metric("SLA İhlali — Reaktif (Geleneksel)", f"{result.reactive_sla_violations} saat")
col6.metric("SLA İhlali — Proaktif (EcoScale)", f"{result.proactive_sla_violations} saat")

st.divider()

# --- Trafik tahmini ---
st.subheader("1. Trafik Tahmini (Random Forest Regressor)")
test_df = result.test_df
fig_forecast = go.Figure()
fig_forecast.add_trace(go.Scatter(x=test_df["timestamp"], y=test_df["traffic_rps"], name="Gerçek Trafik", line=dict(color="#4C78A8")))
fig_forecast.add_trace(go.Scatter(x=test_df["timestamp"], y=test_df["predicted_traffic"], name="Tahmin Edilen Trafik", line=dict(color="#F58518", dash="dot")))
fig_forecast.update_layout(height=350, margin=dict(t=10, b=10), yaxis_title="req/sn", legend=dict(orientation="h", y=1.1))
st.plotly_chart(fig_forecast, use_container_width=True)
st.caption(f"Test kümesi (son {len(test_df)} saat) üzerinde R²={result.forecast.r2:.3f}, MAE={result.forecast.mae:.1f}, RMSE={result.forecast.rmse:.1f}")

# --- Reaktif vs Proaktif olceklendirme ---
st.subheader("2. Reaktif vs. Proaktif Ölçeklendirme ve Karbon Yoğunluğu")
fig_scale = go.Figure()
fig_scale.add_trace(go.Scatter(x=test_df["timestamp"], y=result.reactive_servers, name="Aktif Sunucu (Reaktif)", line=dict(color="#B0B0B0")))
fig_scale.add_trace(go.Scatter(x=test_df["timestamp"], y=result.proactive_servers, name="Aktif Sunucu (EcoScale/Proaktif)", line=dict(color="#54A24B")))
fig_scale.add_trace(go.Scatter(x=test_df["timestamp"], y=test_df["carbon_intensity"], name="Karbon Yoğunluğu (gCO₂eq/kWh)", yaxis="y2", line=dict(color="#E45756", width=1)))
fig_scale.update_layout(
    height=380,
    margin=dict(t=10, b=10),
    yaxis=dict(title="Aktif Sunucu Sayısı"),
    yaxis2=dict(title="Karbon Yoğunluğu", overlaying="y", side="right"),
    legend=dict(orientation="h", y=1.15),
)
st.plotly_chart(fig_scale, use_container_width=True)

st.divider()

# --- Gorev kaydirma ---
st.subheader("3. Karbon Bilinçli Görev Kaydırma (Carbon-Aware Task Shifting)")
st.dataframe(result.task_shift_df, use_container_width=True, hide_index=True)
fig_tasks = go.Figure(
    go.Bar(x=result.task_shift_df["task"], y=result.task_shift_df["carbon_saved_pct"], marker_color="#54A24B")
)
fig_tasks.update_layout(height=300, margin=dict(t=10, b=10), yaxis_title="Karbon Tasarrufu (%)")
st.plotly_chart(fig_tasks, use_container_width=True)

st.divider()

# --- Senaryo tablosu ---
st.subheader("4. Karar Senaryoları (Son 7 Gün)")
scenario_colors = {"S1": "#B7E1CD", "S2": "#FCE8B2", "S3": "#F4C7C3", "S4": "#D9D2E9", "S5": "#E8EAED"}


def highlight_scenario(row):
    color = scenario_colors.get(row["scenario"], "#FFFFFF")
    return [f"background-color: {color}"] * len(row)


st.dataframe(
    result.scenario_df.style.apply(highlight_scenario, axis=1),
    use_container_width=True,
    hide_index=True,
    height=300,
)

st.divider()

# --- Canli motor (APScheduler) ---
st.subheader("5. Canlı İzleme — APScheduler Karbon-Bilinçli Zamanlama Motoru")

live = live_state.read_state()
engine_alive = live_state.is_running()

if not engine_alive or live is None:
    st.info("Canlı motor şu anda çalışmıyor. Sol menüden **▶ Motoru Başlat**'a tıklayın; motor bağımsız bir arka plan sürecinde (APScheduler) çalışmaya başlar ve her tick'te bir simülasyon saati ilerler.")
else:
    cur = live["current"]
    cum = live["cumulative"]

    lc1, lc2, lc3, lc4, lc5 = st.columns(5)
    lc1.metric("Simülasyon Saati", f"#{cur['sim_hour']}", cur["timestamp"])
    lc2.metric("Aktif Sunucu", cur["active_servers"])
    lc3.metric("Karbon Yoğunluğu", f"{cur['carbon_intensity']:.0f} gCO₂eq/kWh")
    lc4.metric("Toplam Maliyet (motor başından beri)", f"${cum['total_cost']:.2f}")
    lc5.metric("Toplam Karbon (motor başından beri)", f"{cum['total_carbon_kg']:.2f} kg")

    st.caption(
        f"Senaryo **{cur['scenario']}** — {cur['decision']} → *{cur['expected_outcome']}* · "
        f"Bekleyen görev: {cur['pending_task_count']} · Anlık çalıştırılan görev: {cum['tasks_run_immediately']} · "
        f"Karbon için ertelenen görev: {cum['tasks_shifted']}"
    )

    hist_df = pd.DataFrame(live["history"])
    if not hist_df.empty:
        fig_live_traffic = go.Figure()
        fig_live_traffic.add_trace(go.Scatter(x=hist_df["sim_hour"], y=hist_df["traffic_rps"], name="Trafik (req/sn)", line=dict(color="#4C78A8")))
        fig_live_traffic.add_trace(go.Scatter(x=hist_df["sim_hour"], y=hist_df["active_servers"], name="Aktif Sunucu", yaxis="y2", line=dict(color="#54A24B")))
        fig_live_traffic.add_trace(go.Scatter(x=hist_df["sim_hour"], y=hist_df["carbon_intensity"], name="Karbon Yoğunluğu", yaxis="y3", line=dict(color="#E45756", width=1, dash="dot")))
        fig_live_traffic.update_layout(
            height=380,
            margin=dict(t=10, b=10),
            xaxis_title="Simülasyon Saati",
            yaxis=dict(title="req/sn"),
            yaxis2=dict(title="Sunucu", overlaying="y", side="right"),
            yaxis3=dict(overlaying="y", side="right", anchor="free", position=1.0, showticklabels=False),
            legend=dict(orientation="h", y=1.15),
        )
        st.plotly_chart(fig_live_traffic, use_container_width=True)

    lcol1, lcol2 = st.columns(2)
    with lcol1:
        st.markdown("**Bekleyen Görevler**")
        pending_df = pd.DataFrame(live["pending_tasks"])
        if pending_df.empty:
            st.caption("Bekleyen görev yok.")
        else:
            st.dataframe(pending_df, use_container_width=True, hide_index=True)

    with lcol2:
        st.markdown("**Son Görev Kararları**")
        events = []
        for h in reversed(live["history"]):
            for ev in h["task_events"]:
                events.append({"sim_hour": h["sim_hour"], **ev})
        if not events:
            st.caption("Henüz bir görev kararı alınmadı.")
        else:
            st.dataframe(pd.DataFrame(events[:10]), use_container_width=True, hide_index=True)

if engine_alive and live_autorefresh:
    time.sleep(2)
    st.rerun()
