# run_opt.py
from pathlib import Path
import json

from aaps_emulator.core.block_utils import load_and_group_blocks
from aaps_emulator.optimizer.genetic_optimizer import optimize_profile
from aaps_emulator.optimizer.utils import extract_profile_params, format_profile

ROOT = Path(__file__).resolve().parents[0]
LOGS_DIR = ROOT / "data" / "logs"
CACHE_DIR = ROOT / "data" / "cache"


def load_profile_from_cache_first():
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
                    print("Found REAL profile in raw_block:", p.name)
                    return item

        # 2) fallback: inputs.profile (если вдруг там есть числа)
        prof2 = d.get("inputs", {}).get("profile")
        if isinstance(prof2, dict):
            if any(v not in (None, {}, []) for v in prof2.values()):
                print("Found usable inputs.profile in:", p.name)
                return prof2

        # 3) fallback: корневой profile (обычно пустой)
        prof = d.get("profile")
        if isinstance(prof, dict):
            if any(v not in (None, {}, []) for v in prof.values()):
                print("Found usable profile in:", p.name)
                return prof

    return {}


def main():
    print("Loading blocks from:", LOGS_DIR)
    blocks = load_and_group_blocks(LOGS_DIR)

    if not blocks:
        print("No blocks found in data/logs. Check that logs exist.")
        return

    initial_profile = load_profile_from_cache_first()
    if not initial_profile:
        print("No initial profile found in cache inputs. Check data/cache files.")
        return

    # DEBUG: показать, какие параметры реально числовые и будут оптимизироваться
    print("=== DEBUG: extract_profile_params ===")
    debug_params = extract_profile_params(initial_profile, [
        "sens",
        "carb_ratio",
        "autoISF_min",
        "autoISF_max",
        "bgAccel_ISF_weight",
        "bgBrake_ISF_weight",
        "pp_ISF_weight",
        "dura_ISF_weight",
        "lower_ISFrange_weight",
        "higher_ISFrange_weight",
        "autosens_min",
        "autosens_max",
        "smb_delivery_ratio",
        "target_bg",
    ])
    print(debug_params)
    print("=====================================")

    # Полный профиль для визуального контроля
    print("=== FULL PROFILE ===")
    print(format_profile(initial_profile))
    print("====================")

    print("Initial profile keys sample:", list(initial_profile.keys())[:40])

    # пустой override — оптимизируем вокруг базового профиля
    profile_override = {}

    # --- ПАРАМЕТРЫ ОПТИМИЗАЦИИ ---
    # баланс качество / скорость: все параметры оптимизируются,
    # Auto‑GA v3 адаптирует mut/elitism/pop, есть early stopping.
    population_size = 120      # чуть меньше 200, но всё ещё богато
    generations = 200          # достаточно для сходимости с Auto‑GA
    elitism = 3
    auto_mode = True

    base_mutation_rate = 0.30
    min_mutation_rate = 0.05
    max_mutation_rate = 0.70

    patience = 40              # ранний стоп, если нет улучшения
    min_improvement = 0.01

    print(
        f"Starting optimization: pop={population_size}, "
        f"gens={generations}, elitism={elitism}, auto_mode={auto_mode}"
    )

    result = optimize_profile(
        blocks=blocks,
        base_profile=initial_profile,
        override_profile=profile_override,
        start_ts=None,
        end_ts=None,
        population_size=population_size,
        generations=generations,
        elitism=elitism,
        auto_mode=auto_mode,
        base_mutation_rate=base_mutation_rate,
        min_mutation_rate=min_mutation_rate,
        max_mutation_rate=max_mutation_rate,
        patience=patience,
        min_improvement=min_improvement,
        progress_callback=lambda gen, fit, note: print(
            f"Gen {gen}: best_fit={fit:.4f}" + (f" | {note}" if note else "")
        ),
    )

    # summary
    if result.history:
        print("Optimization finished. Generations run:", len(result.history))
        print("Best generation:", result.history[-1].generation)
        print("Best fitness:", result.history[-1].best_fitness)
    else:
        print("Optimization finished. No history recorded.")

    print("Profile diff (changes):")
    diff = result.profile_diff()
    print(json.dumps(diff, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
