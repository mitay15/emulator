import sys
import subprocess

from aaps_emulator.optimizer.genetic_optimizer import run_optimizer
from aaps_emulator.runner.compare_runner import compare_logs
from aaps_emulator.runner.build_inputs import build_inputs_from_logs


def run_ga():
    print("🚀 Running Auto‑GA v3 optimizer…")
    result = run_optimizer(max_generations=10, population_size=20)
    print("✔ Done. Best fitness:", result.best_fitness)


def run_compare():
    print("🔍 Running compare_runner…")
    stats = compare_logs(return_stats=True)
    print("✔ Done. Total blocks:", stats.get("total_blocks"))


def run_inputs():
    print("📦 Generating inputs_before_algo_block_* from logs…")
    build_inputs_from_logs()
    print("✔ Done.")


def run_gui():
    print("🖥  Launching Streamlit GUI…")
    subprocess.run(["streamlit", "run", "aaps_emulator/gui/gui_simulator.py"])


def run_tests():
    print("🧪 Running pytest…")
    subprocess.run(["pytest", "-q"])


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py [ga|compare|inputs|gui|test]")
        return

    cmd = sys.argv[1]

    if cmd == "ga":
        run_ga()
    elif cmd == "compare":
        run_compare()
    elif cmd == "inputs":
        run_inputs()
    elif cmd == "gui":
        run_gui()
    elif cmd == "test":
        run_tests()
    else:
        print("Unknown command:", cmd)
        print("Usage: python run.py [ga|compare|inputs|gui|test]")


if __name__ == "__main__":
    main()
