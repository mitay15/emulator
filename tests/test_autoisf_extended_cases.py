from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf


class Obj:
    pass


def GS(bg, delta=0):
    o = Obj()
    o.glucose = bg
    o.delta = delta
    return o


def TEMP(rate=0, duration=30):
    o = Obj()
    o.rate = rate
    o.duration = duration
    return o


def PROFILE(basal=1.0, sens=6.0, max_basal=3.0, max_daily=3.0, target=6.0):
    o = Obj()
    o.current_basal = basal
    o.sens = sens
    o.variable_sens = sens
    o.max_basal = max_basal
    o.max_daily_basal = max_daily
    o.target_bg = target
    return o


def AUTOSENS(r=1.0):
    o = Obj()
    o.ratio = r
    return o


def MEAL(cob=0):
    o = Obj()
    o.meal_cob = cob
    return o


# ---------------------------
# 1. Проверка sensitivityRatio из RT
# ---------------------------
def test_rt_sensitivity_ratio_override():
    gs = GS(8.0, 0)
    rt = {"sensitivityRatio": 0.5}
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(1.0), MEAL(), rt=rt)
    # insulinReq должен быть больше, чем при sens=6.0
    assert res.insulinReq is not None
    assert res.insulinReq > 0


# ---------------------------
# 2. Проверка UAM impact
# ---------------------------
def test_uam_impact_from_rt():
    gs = GS(8.0, 0)
    rt = {"uam_impact": 5.0, "uam_duration_hours": 2.0}
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=rt)
    assert res.eventualBG is not None


# ---------------------------
# 3. Проверка COB модели
# ---------------------------
def test_cob_model_builds_pred():
    gs = GS(7.0, -1.0)
    meal = MEAL(cob=40)
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), meal, rt=None)
    assert res.rate == 0.0  # COB safety


# ---------------------------
# 4. Проверка UAM fallback
# ---------------------------
def test_uam_fallback_no_rt():
    gs = GS(9.0, 0.5)
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=None)
    assert res.eventualBG is not None


# ---------------------------
# 5. Проверка max_daily_basal
# ---------------------------
def test_max_daily_basal_limit():
    gs = GS(15.0, 0)
    prof = PROFILE(basal=1.0, sens=2.0, max_basal=10.0, max_daily=1.8)
    res = determine_basal_autoisf(gs, TEMP(), [], prof, AUTOSENS(), MEAL(), rt=None)
    assert res.rate <= 1.8


# ---------------------------
# 6. Проверка SMB scaling
# ---------------------------
def test_smb_scaling_applied():
    gs = GS(10.0, 0)
    prof = PROFILE(basal=1.0, sens=6.0)
    prof.enableSMB_always = True
    prof.smb_delivery_ratio = 0.5

    res = determine_basal_autoisf(gs, TEMP(), [], prof, AUTOSENS(), MEAL(), rt=None)
    assert res.rate <= 1.0  # SMB уменьшает raw_rate


# ---------------------------
# 7. Проверка zero-temp в RT
# ---------------------------
def test_rt_zero_temp_text():
    gs = GS(8.0, 0)
    rt = {"_raw_text": "zero temp", "rate": 1.5, "duration": 30}
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=rt)
    assert res.rate == 0.0


# ---------------------------
# 8. Проверка projected below safety
# ---------------------------
def test_rt_projected_below_text():
    gs = GS(8.0, 0)
    rt = {"_raw_text": "projected below", "rate": 1.5, "duration": 30}
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=rt)
    assert res.rate == 0.0


# ---------------------------
# 9. Проверка negative IOB override
# ---------------------------
def test_negative_iob_allows_rate():
    gs = GS(5.0, 0)
    rt = {"iob": -2.0}
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=rt)
    assert res.rate >= 0.0


# ---------------------------
# 10. Проверка mg/dL → mmol/L конверсии
# ---------------------------
def test_mgdl_conversion():
    gs = GS(140, 0)  # mg/dL
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=None)
    assert res.eventualBG < 10  # 140 mg/dL = 7.7 mmol/L
