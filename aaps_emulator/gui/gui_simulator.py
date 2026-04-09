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


def load_real_profile_from_cache() -> Dict[str, Any]:
    """
    Ищем реальный профиль в raw_block (тип OapsProfileAutoIsf),
    а не пустую заглушку в profile.
    """
    for p in sorted(CACHE_DIR.glob("inputs_before_algo_block_*.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            continue

        # 1) Ищем в raw_block объект OapsProfileAutoIsf
        raw_block = d.get("raw_block")
        if isinstance(raw_block, list):
            for item in raw_block:
                if isinstance(item, dict) and item.get("__type__") == "OapsProfileAutoIsf":
                    st.write(f"Found REAL profile in raw_block: {p.name}")
                    return item

        # 2) fallback: inputs.profile
        prof2 = d.get("inputs", {}).get("profile")
        if isinstance(prof2, dict):
            if any(v not in (None, {}, []) for v in prof2.values()):
                st.write(f"Found usable inputs.profile in: {p.name}")
                return prof2

        # 3) fallback: корневой profile
        prof = d.get("profile")
        if isinstance(prof, dict):
            if any(v not in (None, {}, []) for v in prof.values()):
                st.write(f"Found usable profile in: {p.name}")
                return prof

    return {}


# ============================================================
# MAIN GUI
# ============================================================
def main():
    st.title("AAPS Emulator — Profile Optimizer")

    # -----------------------------
    # LOAD BLOCKS
    # -----------------------------
    blocks = load_and_group_blocks(LOGS_DIR)
    if not blocks:
        st.error("No blocks found in data/logs. Check that logs exist.")
        return

    # -----------------------------
    # EXTRACT INITIAL PROFILE (REAL)
    # -----------------------------
    initial_profile: Dict[str, Any] = load_real_profile_from_cache()
    if not initial_profile:
        st.error("No initial profile found in cache inputs. Check data/cache files.")
        return

    st.markdown("### Initial profile (keys sample)")
    st.write(list(initial_profile.keys())[:40])

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

    # -----------------------------
    # OPTIMIZATION TAB
    # -----------------------------
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

        population_size = st.slider("Размер популяции", 20, 400, 80, 10)
        generations = st.slider("Количество поколений", 10, 1000, 60, 10)
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

        with st.expander("Advanced GA settings", expanded=False):
            st.write("Тонкая настройка Auto‑GA (опционально)")

            base_mutation_rate = st.slider("Base mutation rate", 0.01, 1.0, 0.30, 0.01)
            min_mutation_rate = st.slider("Min mutation rate", 0.0, 0.5, 0.05, 0.01)
            max_mutation_rate = st.slider("Max mutation rate", 0.1, 1.0, 0.6, 0.01)

            patience = st.number_input(
                "Early stop patience (поколений)",
                min_value=1,
                max_value=500,
                value=50,
                step=1,
            )
            min_improvement = st.number_input(
                "Min improvement (fraction)",
                min_value=0.0,
                max_value=1.0,
                value=0.01,
                step=0.001,
                format="%.3f",
            )

            min_elitism = st.number_input("Min elitism", min_value=1, max_value=10, value=1, step=1)
            max_elitism = st.number_input("Max elitism", min_value=1, max_value=20, value=5, step=1)

            min_pop = st.number_input(
                "Min population",
                min_value=10,
                max_value=1000,
                value=max(30, population_size // 2),
                step=1,
            )
            max_pop = st.number_input(
                "Max population",
                min_value=10,
                max_value=5000,
                value=max(population_size, population_size * 3),
                step=1,
            )

        st.write(
            f"Параметры: популяция = {population_size}, поколения = {generations}, "
            f"элитизм = {elitism}, Auto‑GA = {auto_ga}"
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
                    population_size=int(population_size),
                    generations=int(generations),
                    elitism=int(elitism),
                    auto_mode=bool(auto_ga),
                    base_mutation_rate=float(base_mutation_rate),
                    min_mutation_rate=float(min_mutation_rate),
                    max_mutation_rate=float(max_mutation_rate),
                    min_elitism=int(min_elitism),
                    max_elitism=int(max_elitism),
                    min_pop=int(min_pop),
                    max_pop=int(max_pop),
                    patience=int(patience),
                    min_improvement=float(min_improvement),
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
