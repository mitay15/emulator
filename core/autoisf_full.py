# autoisf_full.py

import math


def round2(x, d=2):
    if x is None or math.isnan(x):
        return x
    scale = 10**d
    return math.floor(x * scale + 0.5) / scale


def interpolate(xdata, lower_weight, higher_weight):
    polyX = [50.0, 60.0, 80.0, 90.0, 100.0, 110.0, 150.0, 180.0, 200.0]
    polyY = [-0.5, -0.5, -0.3, -0.2, 0.0, 0.0, 0.5, 0.7, 0.7]

    polymax = len(polyX) - 1
    step = polyX[0]
    sVal = polyY[0]
    stepT = polyX[polymax]
    sValold = polyY[polymax]

    newVal = 1.0
    lowVal = 1.0
    lowLabl = step

    if step > xdata:
        stepT = polyX[1]
        sValold = polyY[1]
        lowVal = sVal
        topVal = sValold
        lowX = step
        topX = stepT
        myX = xdata
        newVal = lowVal + (topVal - lowVal) / (topX - lowX) * (myX - lowX)

    elif stepT < xdata:
        step = polyX[polymax - 1]
        sVal = polyY[polymax - 1]
        lowVal = sVal
        topVal = sValold
        lowX = step
        topX = stepT
        myX = xdata
        newVal = lowVal + (topVal - lowVal) / (topX - lowX) * (myX - lowX)

    else:
        for i in range(polymax + 1):
            step = polyX[i]
            sVal = polyY[i]
            if step == xdata:
                newVal = sVal
                break
            elif step > xdata:
                topVal = sVal
                lowX = lowLabl
                myX = xdata
                topX = step
                newVal = lowVal + (topVal - lowVal) / (topX - lowX) * (myX - lowX)
                break
            lowVal = sVal
            lowLabl = step

    if xdata > 100:
        newVal *= higher_weight
    else:
        newVal *= lower_weight

    return newVal


def within_limits(
    liftISF,
    minISFReduction,
    maxISFReduction,
    sensitivityRatio,
    temptargetSet,
    high_temptarget_raises_sensitivity,
    target_bg,
    normalTarget,
):
    lift = liftISF

    if lift < minISFReduction:
        lift = minISFReduction
    elif lift > maxISFReduction:
        lift = maxISFReduction

    if (
        high_temptarget_raises_sensitivity
        and temptargetSet
        and target_bg > normalTarget
    ):
        finalISF = lift * sensitivityRatio
    elif lift >= 1:
        finalISF = max(lift, sensitivityRatio)
    else:
        finalISF = min(lift, sensitivityRatio)

    return finalISF


def compute_variable_sens(
    profile,
    gs,
    autosens_ratio,
    autoISF_min,
    autoISF_max,
    bgAccel_weight,
    bgBrake_weight,
    pp_weight,
    dura_weight,
    lower_range_weight,
    higher_range_weight,
    target_bg,
    normalTarget,
    isTempTarget,
    high_temptarget_raises_sensitivity,
    low_temptarget_lowers_sensitivity,
):
    """
    Полный AutoISF 3.0.1 — 1:1 перенос из AAPS.
    """

    sens = profile.sens

    # -----------------------------
    # 1. SensitivityRatio (Autosens or TempTarget)
    # -----------------------------
    if (
        high_temptarget_raises_sensitivity and isTempTarget and target_bg > normalTarget
    ) or (
        low_temptarget_lowers_sensitivity and isTempTarget and target_bg < normalTarget
    ):
        halfBasalTarget = profile.half_basal_exercise_target
        c = halfBasalTarget - normalTarget

        if c * (c + target_bg - normalTarget) <= 0:
            sensitivityRatio = profile.autosens_max
        else:
            sensitivityRatio = c / (c + target_bg - normalTarget)
            sensitivityRatio = min(sensitivityRatio, profile.autosens_max)
            sensitivityRatio = round2(sensitivityRatio, 2)
    else:
        sensitivityRatio = autosens_ratio

    # Если AutoISF выключен
    if not profile.enable_autoISF or gs is None:
        return round2(sens / sensitivityRatio, 1)

    # -----------------------------
    # 2. Инициализация факторов
    # -----------------------------
    sens_modified = False
    pp_ISF = 1.0
    acce_ISF = 1.0
    dura_ISF = 1.0

    # -----------------------------
    # 3. Parabola / Acceleration ISF
    # -----------------------------
    fit_corr = gs.corrSqu
    bg_acce = gs.bgAcceleration
    acce_weight = 1.0

    if fit_corr >= 0.9:
        fit_share = 10 * (fit_corr - 0.9)
        cap_weight = 1.0

        bg_off = target_bg + 10 - gs.glucose

        if acce_weight == 1.0 and gs.glucose < target_bg:
            if bg_acce > 0:
                if bg_acce > 1:
                    cap_weight = 0.5
                acce_weight = bgBrake_weight
            elif bg_acce < 0:
                acce_weight = bgAccel_weight
        else:
            if bg_acce < 0:
                acce_weight = bgBrake_weight
            elif bg_acce > 0:
                acce_weight = bgAccel_weight

        acce_ISF = 1.0 + bg_acce * cap_weight * acce_weight * fit_share

        if acce_ISF != 1.0:
            sens_modified = True

    # -----------------------------
    # 4. bg_ISF (range_ISF)
    # -----------------------------
    bg_off = target_bg + 10 - gs.glucose
    bg_ISF = 1 + interpolate(100 - bg_off, lower_range_weight, higher_range_weight)

    if bg_ISF < 1.0:
        lift = min(bg_ISF, acce_ISF)
        if acce_ISF > 1.0:
            lift = bg_ISF * acce_ISF

        final_ISF = within_limits(
            lift,
            autoISF_min,
            autoISF_max,
            sensitivityRatio,
            isTempTarget,
            high_temptarget_raises_sensitivity,
            target_bg,
            normalTarget,
        )
        return min(720.0, round2(sens / final_ISF, 1))

    if bg_ISF > 1.0:
        sens_modified = True

    # -----------------------------
    # 5. pp_ISF
    # -----------------------------
    if bg_off > 0:
        pass
    elif gs.shortAvgDelta < 0:
        pass
    else:
        pp_ISF = 1.0 + max(0.0, gs.delta * pp_weight)
        if pp_ISF != 1.0:
            sens_modified = True

    # -----------------------------
    # 6. dura_ISF
    # -----------------------------
    dura05 = gs.duraISFminutes
    avg05 = gs.duraISFaverage

    if dura05 >= 10.0 and avg05 > target_bg:
        dura05Weight = dura05 / 60.0
        avg05Weight = dura_weight / target_bg
        dura_ISF = 1.0 + dura05Weight * avg05Weight * (avg05 - target_bg)
        sens_modified = True

    # -----------------------------
    # 7. Финальный фактор
    # -----------------------------
    if sens_modified:
        lift = max(dura_ISF, bg_ISF, acce_ISF, pp_ISF)
        if acce_ISF < 1.0:
            lift *= acce_ISF

        final_ISF = within_limits(
            lift,
            autoISF_min,
            autoISF_max,
            sensitivityRatio,
            isTempTarget,
            high_temptarget_raises_sensitivity,
            target_bg,
            normalTarget,
        )
        return round2(sens / final_ISF, 1)

    # -----------------------------
    # 8. Если ничего не изменилось
    # -----------------------------
    return round2(sens / sensitivityRatio, 1)
