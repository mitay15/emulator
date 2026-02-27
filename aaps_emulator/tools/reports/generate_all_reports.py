from pathlib import Path

from aaps_emulator.analysis import metrics
from aaps_emulator.tools.reports import autoisf_full_report, autoisf_plotly_report

REPORTS_DIR = Path("reports/last_run")


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating full text report...")
    autoisf_full_report.main()

    print("Generating Plotly report...")
    autoisf_plotly_report.main()

    print("Computing metrics...")
    metrics.compute_metrics()

    print("All reports and metrics generated in", REPORTS_DIR)


if __name__ == "__main__":
    main()
