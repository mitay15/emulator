# aaps_emulator/core/autoisf_predictions_adapter.py
from __future__ import annotations

from aaps_emulator.autoisf_structs import AutoIsfInputs, CorePredResultAlias
from aaps_emulator.predictions import run_predictions


def compute_core_predictions(inputs: AutoIsfInputs) -> CorePredResultAlias:
    """
    Wrapper over run_predictions returning CorePredResultAlias for AutoISF module.
    Uses AutoISF (no DynISF).
    """
    res = run_predictions(inputs)

    # map PredictionsResult -> CorePredResultAlias
    return CorePredResultAlias(
        bg=getattr(inputs.glucose_status, "glucose", None),
        delta=getattr(inputs.glucose_status, "delta", None),
        eventual_bg=getattr(res, "eventual_bg", None),
        min_pred_bg=getattr(res, "min_pred_bg", None),
        min_guard_bg=getattr(res, "min_guard_bg", None),
        pred_iob=getattr(res, "pred_iob", []) or [],
        pred_cob=getattr(res, "pred_cob", []) or [],
        pred_uam=getattr(res, "pred_uam", []) or [],
        pred_zt=getattr(res, "pred_zt", []) or [],
        trace=[],
    )
