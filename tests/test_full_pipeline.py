# tests/test_full_pipeline.py
import pytest

from aaps_emulator.core.glucose_status_autoisf import BucketedEntry, compute_glucose_status_autoisf
from aaps_emulator.core.future_iob_engine import generate_future_iob
from aaps_emulator.core.predictions import run_predictions
from aaps_emulator.core.autoisf_structs import (
    AutoIsfInputs,
    OapsProfileAutoIsf,
    AutosensResult,
    MealData,
    IobTotal,
)
from aaps_emulator.core.autoisf_pipeline import run_autoisf_pipeline


@pytest.mark.integration
def test_full_pipeline_smoke():
    now = 1_700_000_000_000
    data = [
        BucketedEntry(timestamp=now - i * 300000, value=130 + i * 2, recalculated=130 + i * 2)
        for i in range(5)
    ]
    gs = compute_glucose_status_autoisf(data)

    iob_now = IobTotal(iob=1.2, activity=0.03, lastBolusTime=now - 20 * 60 * 1000)
    iob_array = generate_future_iob(iob_now)

    profile = OapsProfileAutoIsf(
        current_basal=1.0,
        max_basal=3.0,
        max_daily_basal=3.0,
        min_bg=90,
        max_bg=110,
        sens=50,
        variable_sens=0,
        carb_ratio=10,
        enableUAM=True,
        enable_autoISF=True,
        bgAccel_ISF_weight=0.01,
        bgBrake_ISF_weight=0.01,
        pp_ISF_weight=0.01,
        dura_ISF_weight=0.01,
        lower_ISFrange_weight=0.0,
        higher_ISFrange_weight=0.0,
    )
    autosens = AutosensResult(ratio=1.0)
    meal = MealData(mealCOB=20, carbs=40, lastCarbTime=now - 30 * 60 * 1000)

    inputs = AutoIsfInputs(
        glucose_status=gs,
        current_temp=None,
        iob_data_array=iob_array,
        profile=profile,
        autosens=autosens,
        meal=meal,
        rt=None,
        raw_block=None,
    )

    pred = run_predictions(inputs)
    # PredictionsResult uses eventual_bg
    assert getattr(pred, "eventual_bg", None) is not None

    vs, pred2, dosing = run_autoisf_pipeline(inputs)
    assert vs is not None and vs > 0
    assert getattr(pred2, "eventual_bg", None) is not None
