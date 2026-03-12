# tests/test_heatmap.py
import pytest
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline

HEATMAP_PATH = Path("data/reports/heatmap/heatmap.png")


@pytest.mark.visual
def test_heatmap(all_blocks):
    diffs_vs = []
    diffs_eventual = []
    blocks = []

    for path, inputs, expected, block_index in all_blocks:
        variable_sens, pred, dosing = run_autoisf_pipeline(inputs)

        if "variable_sens" in expected:
            diffs_vs.append(abs(variable_sens - expected["variable_sens"]))
        else:
            diffs_vs.append(0)

        if "eventualBG" in expected:
            diffs_eventual.append(abs(pred.eventual_bg - expected["eventualBG"]))
        else:
            diffs_eventual.append(0)

        blocks.append(block_index)

    HEATMAP_PATH.parent.mkdir(parents=True, exist_ok=True)

    data = np.array([diffs_vs, diffs_eventual])

    plt.figure(figsize=(12, 3))
    plt.imshow(data, cmap="hot", aspect="auto")
    plt.colorbar(label="Absolute error")
    plt.yticks([0, 1], ["variable_sens", "eventualBG"])
    plt.xticks(range(len(blocks)), blocks, rotation=90)
    plt.tight_layout()
    plt.savefig(HEATMAP_PATH)

    assert HEATMAP_PATH.exists()
