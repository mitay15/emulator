# aaps_emulator/core/autoisf_pipeline.py
from __future__ import annotations

import logging

from aaps_emulator.runner.build_inputs import AutoIsfInputs
from aaps_emulator.core.autoisf_module import compute_variable_sens
from aaps_emulator.core.predictions import run_predictions, PredictionsResult
from aaps_emulator.core.determine_basal import run_determine_basal, DosingResult

from aaps_emulator.core.autoisf_structs import (
    GlucoseStatusAutoIsf,
    OapsProfileAutoIsf,
    AutosensResult,
    MealData,
    IobTotal,
    TempBasal,
)

logger = logging.getLogger(__name__)


def _ensure_dataclass(value, cls):
    if value is None or isinstance(value, cls):
        return value
    if isinstance(value, dict):
        return cls(**value)
    return value


def _normalize_inputs(inputs: AutoIsfInputs) -> AutoIsfInputs:
    inputs.glucose_status = _ensure_dataclass(inputs.glucose_status, GlucoseStatusAutoIsf)
    inputs.profile = _ensure_dataclass(inputs.profile, OapsProfileAutoIsf)
    inputs.autosens = _ensure_dataclass(inputs.autosens, AutosensResult)
    inputs.meal = _ensure_dataclass(inputs.meal, MealData)
    inputs.current_temp = _ensure_dataclass(inputs.current_temp, TempBasal)

    if inputs.iob_data_array and isinstance(inputs.iob_data_array[0], dict):
        inputs.iob_data_array = [
            _ensure_dataclass(x, IobTotal) for x in inputs.iob_data_array
        ]

    return inputs


def run_autoisf_pipeline(inputs: AutoIsfInputs):
    inputs = _normalize_inputs(inputs)

    sensitivity_ratio = inputs.autosens.ratio if inputs.autosens else 1.0

    variable_sens = compute_variable_sens(
        glucose_status=inputs.glucose_status,
        profile=inputs.profile,
        meal=inputs.meal,
        autosens=inputs.autosens,
        iob_array=inputs.iob_data_array,
        sensitivity_ratio=sensitivity_ratio,
    )

    # --- safe variable_sens fallback and debug logging ---
    try:
        _vs = variable_sens
    except NameError:
        _vs = None

    try:
        if _vs is None or float(_vs) <= 0:
            _autosens = getattr(inputs, "autosens", None)
            _autosens_ratio = getattr(_autosens, "ratio", None) if _autosens is not None else None
            if _autosens_ratio is not None and float(_autosens_ratio) > 0:
                variable_sens = float(_autosens_ratio)
            else:
                _prof_sens = getattr(inputs.profile, "sens", None)
                try:
                    variable_sens = float(_prof_sens) if _prof_sens is not None and float(_prof_sens) > 0 else 1.0
                except Exception:
                    variable_sens = 1.0
        else:
            variable_sens = float(_vs)
    except Exception:
        variable_sens = 1.0

    # log resolved value for debugging
    try:
        _autosens_for_log = getattr(inputs, "autosens", None)
        _autosens_ratio_for_log = getattr(_autosens_for_log, "ratio", None) if _autosens_for_log is not None else None
        _prof_sens_for_log = getattr(inputs.profile, "sens", None)
        logger.debug(
            "variable_sens resolved to %s (computed=%s, autosens=%s, profile.sens=%s)",
            variable_sens,
            _vs,
            _autosens_ratio_for_log,
            _prof_sens_for_log,
        )
    except Exception:
        # never fail pipeline because of logging
        pass
    # --- end fallback and debug ---

    # propagate into profile for downstream code that expects it
    try:
        inputs.profile.variable_sens = variable_sens
    except Exception:
        # ignore if profile is not settable
        pass

    pred: PredictionsResult = run_predictions(inputs)

    dosing: DosingResult = run_determine_basal(inputs, pred, variable_sens)

    # ensure eventualBG override compatibility
    try:
        dbg = getattr(pred, "autoisf_debug_check", {}) or {}
        if isinstance(dbg, dict):
            if "eventualBG" in dbg:
                pred.eventual_bg = dbg["eventualBG"]
            elif "eventual_bg" in dbg:
                pred.eventual_bg = dbg["eventual_bg"]
    except Exception:
        pass

    return variable_sens, pred, dosing
