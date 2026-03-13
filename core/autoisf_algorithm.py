from __future__ import annotations

from dataclasses import dataclass

from core.autoisf_structs import AutoIsfInputs
from core.predictions import run_predictions


@dataclass
class RT:
    rate: float
    duration: int
    insulinReq: float
    eventualBG_final: float


def run_smb_tail(inputs: AutoIsfInputs):
    """
    Упрощённый SMB-хвост (backward compatibility).
    Использует pred.eventual_bg и sens из profile.variable_sens (если есть) или profile.sens.
    """
    # ensure inputs look sane
    if inputs is None:
        raise ValueError("inputs is required")

    pred = run_predictions(inputs)

    eventual = getattr(pred, "eventual_bg", None)
    if eventual is None:
        eventual = 0.0

    sens = (
        getattr(inputs.profile, "variable_sens", None)
        or getattr(inputs.profile, "sens", None)
        or 1.0
    )
    target = (
        getattr(inputs.profile, "min_bg", 0.0) + getattr(inputs.profile, "max_bg", 0.0)
    ) / 2.0
    basal = getattr(inputs.profile, "current_basal", 0.0)

    insulinReq = round((eventual - target) / sens, 2) if sens != 0 else 0.0
    rate = basal + 2 * insulinReq

    return RT(
        rate=rate,
        duration=30,
        insulinReq=insulinReq,
        eventualBG_final=eventual,
    )


def autoisf_algorithm(*args, **kwargs):
    """
    Compatibility wrapper for old tests.
    New architecture uses run_smb_tail(inputs).
    """
    inputs = kwargs.get("inputs")
    if inputs is None:
        raise ValueError("autoisf_algorithm now requires 'inputs=' argument")

    rt = run_smb_tail(inputs)

    return {
        "eventual_bg": rt.eventualBG_final,
        "insulin_req": rt.insulinReq,
        "rate": rt.rate,
        "duration": rt.duration,
        "smb": None,
        "trace": [],
    }
