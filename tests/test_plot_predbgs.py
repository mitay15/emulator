# tests/test_plot_predbgs.py
import pytest
import matplotlib.pyplot as plt
from pathlib import Path

from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline

PLOTS_DIR = Path("data/reports/plots")


@pytest.mark.visual
def test_plot_predbgs(all_blocks):
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    for path, inputs, expected, block_index in all_blocks:
        # run_autoisf_pipeline returns (variable_sens, pred, dosing)
        variable_sens, pred, dosing = run_autoisf_pipeline(inputs)

        plt.figure(figsize=(10, 4))
        # pred may be PredictionsResult with lists pred_iob/pred_cob/pred_uam/pred_zt
        if getattr(pred, "pred_iob", None):
            plt.plot(pred.pred_iob, label="IOB")
        if getattr(pred, "pred_cob", None):
            plt.plot(pred.pred_cob, label="COB")
        if getattr(pred, "pred_uam", None):
            plt.plot(pred.pred_uam, label="UAM")
        if getattr(pred, "pred_zt", None):
            plt.plot(pred.pred_zt, label="ZT")

        plt.title(f"Block {block_index} — predBGs")
        plt.legend()
        plt.tight_layout()

        out = PLOTS_DIR / f"block_{block_index}_predbgs.png"
        plt.savefig(out)
        plt.close()

    assert True
