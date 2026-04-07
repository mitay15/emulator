# run.py
import shutil
import argparse
import subprocess
import os

from aaps_emulator.optimizer.genetic_optimizer import optimize_profile
from aaps_emulator.runner.compare_runner import compare_logs
from aaps_emulator.runner.build_inputs import build_inputs_from_logs


# ---------------------------------------------------------
#  Цвета
# ---------------------------------------------------------
class C:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"


# ---------------------------------------------------------
#  Auto‑GA v3
# ---------------------------------------------------------
def run_ga(args):
    print(f"{C.CYAN}🚀 Running Auto‑GA v3 optimizer…{C.END}")

    blocks = [(0, 1000, [{"dummy": True}])]
    base_profile = {"sens": 50, "carb_ratio": 10, "current_basal": 1.0}
    override_profile = {}

    result = optimize_profile(
        blocks=blocks,
        base_profile=base_profile,
        override_profile=override_profile,
        generations=args.generations,
        population_size=args.population,
        elitism=args.elitism,
        auto_mode=args.auto,
    )

    best_fitness = result.history[-1].best_fitness
    print(f"{C.GREEN}✔ Done. Best fitness: {best_fitness}{C.END}")


# ---------------------------------------------------------
#  Compare Runner
# ---------------------------------------------------------
def run_compare(args):
    print(f"{C.CYAN}🔍 Running compare_runner…{C.END}")

    stats = compare_logs(
        fast=args.fast,
        return_stats=True,
        extract_clean=args.extract_clean,
    )

    print(f"{C.GREEN}✔ Done. Total blocks: {stats.get('total_blocks')}{C.END}")


# ---------------------------------------------------------
#  Build Inputs
# ---------------------------------------------------------
def run_inputs(args):
    print(f"{C.CYAN}📦 Generating inputs_before_algo_block_* from logs…{C.END}")
    build_inputs_from_logs(logs_dir=args.logs, out_dir=args.out)
    print(f"{C.GREEN}✔ Done.{C.END}")


# ---------------------------------------------------------
#  GUI
# ---------------------------------------------------------
def run_gui(args):
    print(f"{C.CYAN}🖥  Launching Streamlit GUI…{C.END}")

    if shutil.which("streamlit") is None:
        print(f"{C.RED}❌ Streamlit не установлен.{C.END}")
        print(f"{C.YELLOW}Установи командой: pip install streamlit{C.END}")
        return

    subprocess.run(["streamlit", "run", "aaps_emulator/gui/gui_simulator.py"])


# ---------------------------------------------------------
#  Tests
# ---------------------------------------------------------
def run_tests(args):
    print(f"{C.CYAN}🧪 Running pytest…{C.END}")
    subprocess.run(["pytest", "-q"])


# ---------------------------------------------------------
#  Clean (кроссплатформенная очистка)
# ---------------------------------------------------------
def run_clean(args=None):
    print(f"{C.YELLOW}🧹 Cleaning project...{C.END}")

    paths = [
        "data/cache",
        "data/reports",
        "data/clean",
        "__pycache__",
        ".pytest_cache",
    ]

    for p in paths:
        if os.path.exists(p):
            try:
                shutil.rmtree(p, ignore_errors=True)
                print(f"{C.GREEN}✔ Removed {p}{C.END}")
            except Exception as e:
                print(f"{C.RED}❌ Failed to remove {p}: {e}{C.END}")

    # recreate empty dirs
    for p in ["data/cache", "data/reports", "data/clean"]:
        os.makedirs(p, exist_ok=True)

    print(f"{C.GREEN}✔ Clean complete.{C.END}")


# ---------------------------------------------------------
#  Prepare (inputs + compare + tests)
# ---------------------------------------------------------
def run_prepare(args):
    print(f"{C.CYAN}🔧 Preparing project…{C.END}")

    run_inputs(args)
    run_compare(args)
    run_tests(args)

    print(f"{C.GREEN}✔ Project fully prepared.{C.END}")


# ---------------------------------------------------------
#  Fresh (clean + inputs + compare + test)
# ---------------------------------------------------------
def run_fresh(args):
    print(f"{C.CYAN}🔄 Full project reset and validation...{C.END}")

    run_clean()
    run_inputs(args)
    run_compare(args)
    run_tests(args)

    print(f"{C.GREEN}✔ Fresh run complete. Project is fully validated.{C.END}")


# ---------------------------------------------------------
#  Main CLI
# ---------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="AAPS Emulator — Developer CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    sub = parser.add_subparsers(dest="cmd")

    # GA
    p_ga = sub.add_parser("ga", help="Run Auto‑GA optimizer")
    p_ga.add_argument("--generations", type=int, default=3)
    p_ga.add_argument("--population", type=int, default=6)
    p_ga.add_argument("--elitism", type=int, default=1)
    p_ga.add_argument("--auto", action="store_true", help="Enable Auto‑GA v3 adaptive mode")
    p_ga.set_defaults(func=run_ga)

    # Compare
    p_cmp = sub.add_parser("compare", help="Compare Python vs AAPS logs")
    p_cmp.add_argument("--fast", action="store_true")
    p_cmp.add_argument("--extract-clean", action="store_true")
    p_cmp.set_defaults(func=run_compare)

    # Inputs
    p_in = sub.add_parser("inputs", help="Generate inputs_before_algo_block_*")
    p_in.add_argument("--logs", default="data/logs")
    p_in.add_argument("--out", default="data/cache")
    p_in.set_defaults(func=run_inputs)

    # GUI
    p_gui = sub.add_parser("gui", help="Launch Streamlit GUI")
    p_gui.set_defaults(func=run_gui)

    # Tests
    p_test = sub.add_parser("test", help="Run pytest")
    p_test.set_defaults(func=run_tests)

    # Prepare
    p_prep = sub.add_parser("prepare", help="Generate inputs + compare + tests")
    p_prep.add_argument("--logs", default="data/logs")
    p_prep.add_argument("--out", default="data/cache")
    p_prep.add_argument("--fast", action="store_true")
    p_prep.add_argument("--extract-clean", action="store_true")
    p_prep.set_defaults(func=run_prepare)

    # Clean
    p_clean = sub.add_parser("clean", help="Clean all generated files and caches")
    p_clean.set_defaults(func=run_clean)

    # Fresh
    p_fresh = sub.add_parser("fresh", help="Clean + inputs + compare + tests")
    p_fresh.add_argument("--logs", default="data/logs")
    p_fresh.add_argument("--out", default="data/cache")
    p_fresh.add_argument("--fast", action="store_true")
    p_fresh.add_argument("--extract-clean", action="store_true")
    p_fresh.set_defaults(func=run_fresh)

    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
