# aaps_emulator/core/cob_uam_pred.py


def build_pred_from_rt_lists(rt: dict):
    """
    Возвращает предсказания из RT (если есть) в mg/dL.
    Ключи: pred_iob, pred_cob, pred_uam, pred_zt
    """
    pred_iob = rt.get("pred_iob") or rt.get("predIOB") or rt.get("pred_iob") or []
    pred_cob = rt.get("pred_cob") or rt.get("predCOB") or rt.get("pred_cob") or []
    pred_uam = rt.get("pred_uam") or rt.get("predUAM") or rt.get("pred_uam") or []
    pred_zt = rt.get("pred_zt") or rt.get("predZT") or rt.get("pred_zt") or []
    return {
        "pred_iob": pred_iob,
        "pred_cob": pred_cob,
        "pred_uam": pred_uam,
        "pred_zt": pred_zt,
    }


def simple_cob_absorption(meal_cob_g: float, cat_hours: float = 2.0, step_minutes: int = 5):
    """
    Простая модель распределения углеводов по CAT (равномерно).
    Возвращает pred_cob_g (накопленные граммы по шагам), ci_per_5m (грамм/шаг), cob_g.
    Caller должен преобразовать граммы в mg/dL через профиль.
    """
    if not meal_cob_g or meal_cob_g <= 0:
        return {"pred_cob": [], "ci_per_5m": 0.0, "cob_g": 0.0}

    steps = int((cat_hours * 60) / step_minutes)
    if steps <= 0:
        return {"pred_cob": [], "ci_per_5m": 0.0, "cob_g": meal_cob_g}

    per_step_g = meal_cob_g / steps
    pred_cob_g = []
    cum = 0.0
    for _i in range(steps):
        cum += per_step_g
        pred_cob_g.append(cum)

    return {"pred_cob": pred_cob_g, "ci_per_5m": per_step_g, "cob_g": meal_cob_g}


def build_uam_pred(uam_impact_mg_per_5m: float, uam_duration_hours: float, step_minutes: int = 5):
    """
    Треугольная модель UAM (mg/dL per 5m).
    """
    if not uam_impact_mg_per_5m or uam_duration_hours <= 0:
        return []

    steps = int((uam_duration_hours * 60) / step_minutes)
    if steps <= 0:
        return []

    peak = uam_impact_mg_per_5m
    pred = []
    for i in range(steps):
        frac = 1.0 - abs((i - steps / 2) / (steps / 2))
        val = max(0.0, peak * frac)
        pred.append(val)
    return pred
