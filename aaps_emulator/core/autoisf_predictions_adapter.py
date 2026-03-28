# aaps_emulator/core/autoisf_predictions_adapter.py
from __future__ import annotations

from .autoisf_structs import AutoIsfInputs, CorePredResultAlias
from .predictions import run_predictions


def compute_core_predictions(inputs: AutoIsfInputs) -> CorePredResultAlias:
    """
    Преобразует PredictionsResult → CorePredResultAlias.
    Используется AutoISF (без DynISF).
    """
    pred = run_predictions(inputs)
    gs = inputs.glucose_status

    return CorePredResultAlias(
        bg=getattr(gs, "glucose", None),
        delta=getattr(gs, "delta", None),
        eventual_bg=pred.eventual_bg,
        min_pred_bg=pred.min_pred_bg,
        min_guard_bg=pred.min_guard_bg,
        pred_iob=list(pred.pred_iob),
        pred_cob=list(pred.pred_cob),
        pred_uam=list(pred.pred_uam),
        pred_zt=list(pred.pred_zt),
        trace=[],
        raw={"predictions": pred.__dict__},
    )
