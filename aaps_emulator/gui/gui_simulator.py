# aaps_emulator/gui/gui_simulator.py
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import plotly.graph_objects as go
import streamlit as st

from aaps_emulator.core.block_utils import load_and_group_blocks
from aaps_emulator.optimizer.genetic_optimizer import optimize_profile


# ============================================================
# ROOT PATHS
# ============================================================
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)

DATA_DIR = ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"


st.set_page_config(page_title="AAPS Emulator — Optimizer", layout="wide")


# ============================================================
# LOAD inputs_before_algo_block
# ============================================================
def load_inputs_before(ts: int):
    fname = CACHE_DIR / f"inputs_before_algo_block_{ts}.json"
    if not fname.exists():
        return None
    try:
        with open(fname, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ============================================================
# MAIN GUI
# ============================================================
def main():
    st.title("AAPS Emulator — Profile Optimizer")

    # -----------------------------
    # LOAD BLOCKS
    # -----------------------------
    blocks = load_and_group_blocks(LOGS_DIR)

    # -----------------------------
    # EXTRACT INITIAL PROFILE
    # -----------------------------
    initial_profile: Dict[str, Any] = {}
    for idx, ts, block_objs in blocks:
        inputs_before = load_inputs_before(ts)
        if not inputs_before or not isinstance(inputs_before, dict):
            continue
        inner = inputs_before.get("inputs") or {}
        prof_dict = inner.get("profile")
        if prof_dict:
            initial_profile = prof_dict
            break

    # -----------------------------
    # DATE RANGE SELECTION
    # -----------------------------
    st.sidebar.header("Диапазон дат")
    start_date = st.sidebar.date_input("Дата начала", value=None)
    end_date = st.sidebar.date_input("Дата окончания", value=None)

    start_ts = (
        int(datetime.combine(start_date, datetime.min.time()).timestamp() * 1000)
        if start_date else None
    )
    end_ts = (
        int(datetime.combine(end_date, datetime.min.time()).timestamp() * 1000)
        if end_date else None
    )

    # -----------------------------
    # PROFILE OVERRIDE
    # -----------------------------
    PROFILE_GROUPS = {
        "Основные": ["sens", "target_bg", "carb_ratio", "current_basal"],
        "AutoISF": [
            "autoISF_min", "autoISF_max",
            "bgAccel_ISF_weight", "bgBrake_ISF_weight",
            "pp_ISF_weight", "dura_ISF_weight",
            "lower_ISFrange_weight", "higher_ISFrange_weight",
        ],
        "SMB": ["smb_delivery_ratio"],
        "Прочее": ["autosens_min", "autosens_max"],
    }

    st.sidebar.header("Override профиля")

    override_raw: Dict[str, str] = {}
    changed_params: Dict[str, Any] = {}

    for group_name, keys in PROFILE_GROUPS.items():
        with st.sidebar.expander(group_name, expanded=(group_name == "Основные")):
            for key in keys:
                if key not in initial_profile:
                    continue
                val = initial_profile.get(key, "")
                default_str = json.dumps(val) if isinstance(val, (dict, list)) else str(val)
                override_raw[key] = st.text_input(key, value=default_str)

    for k, v in override_raw.items():
        if k in initial_profile and str(initial_profile[k]) != str(v):
            changed_params[k] = (initial_profile[k], v)

    st.sidebar.header("Изменённые параметры")
    for k, (old, new) in changed_params.items():
        st.sidebar.write(f"🟡 {k}: {old} → {new}")

    if st.sidebar.button("Сбросить override"):
        st.experimental_rerun()

    profile_override: Dict[str, Any] = {}
    for k, v in override_raw.items():
        if v.strip() == "":
            continue
        try:
            profile_override[k] = float(v)
        except Exception:
            try:
                profile_override[k] = json.loads(v)
            except Exception:
                profile_override[k] = v

    # ============================================================
    # OPTIMIZATION TAB
    # ============================================================
    (tab_opt,) = st.tabs(["Optimization"])

    with tab_opt:
        st.subheader("Оптимизация профиля")

        st.markdown("### Настройки оптимизации")

        auto_ga = st.checkbox("Auto‑GA (автоматический режим)", value=True)

        preset = st.selectbox(
            "Preset оптимизации",
            ["Balanced", "Conservative", "Aggressive"],
            index=0,
        )

        population_size = st.slider("Размер популяции", 20, 200, 80, 10)
        generations = st.slider("Количество поколений", 10, 200, 60, 10)
        elitism = st.slider("Элитизм", 1, 10, 2)

        if preset == "Conservative":
            population_size = 60
            generations = 120
        elif preset == "Balanced":
            population_size = 80
            generations = 60
        elif preset == "Aggressive":
            population_size = 120
            generations = 40

        st.write(
            f"Параметры: популяция = {population_size}, поколения = {generations}, элитизм = {elitism}, Auto‑GA = {auto_ga}"
        )

        progress_placeholder = st.empty()

        def update_progress(gen: int, fit: float, note: str | None = None):
            msg = f"Поколение {gen}, лучший fitness = {fit:.4f}"
            if note:
                msg += f" | {note}"
            progress_placeholder.write(msg)

        run_opt = st.button("Запустить оптимизацию")

        if run_opt:
            with st.spinner("Оптимизация..."):
                result = optimize_profile(
                    blocks=blocks,
                    base_profile=initial_profile,
                    override_profile=profile_override,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    population_size=population_size,
                    generations=generations,
                    elitism=elitism,
                    auto_mode=auto_ga,
                    progress_callback=update_progress,
                )

            st.success("Оптимизация завершена")

            st.subheader("Изменения профиля")
            st.json(result.profile_diff())

            st.subheader("История поколений")
            gens = [h.generation for h in result.history]
            fits = [h.best_fitness for h in result.history]

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=gens, y=fits, mode="lines+markers"))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Рекомендации")
            st.write(
                """
            • Если fitness падает медленно — увеличь количество поколений  
            • Если параметры упираются в границы — расширь диапазоны  
            • Если variable_sens нестабилен — усили веса bgAccel/bgBrake  
            • Если eventualBG слишком высок — увеличь sens или уменьшай autoISF_min  
            """
            )


if __name__ == "__main__":
    main()
