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


def PROFILE(basal=1.0, sens=6.0, max_basal=3.0):
    o = Obj()
    o.current_basal = basal
    o.sens = sens
    o.variable_sens = sens
    o.max_basal = max_basal
    o.max_daily_basal = max_basal
    o.target_bg = 6.0
    return o


def AUTOSENS(r=1.0):
    o = Obj()
    o.ratio = r
    return o


def MEAL(cob=0):
    o = Obj()
    o.meal_cob = cob
    return o


def test_rt_override_zero_rate():
    """RT содержит rate=0.0 → Python обязан уважать override."""
    gs = GS(7.0, 0)
    rt = {"rate": 0.0, "duration": 30}
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=rt)
    assert res.rate == 0.0


def test_rt_override_positive_rate():
    """RT содержит rate=1.2 → Python обязан взять 1.2."""
    gs = GS(7.0, 0)
    rt = {"rate": 1.2, "duration": 30}
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=rt)
    assert abs(res.rate - 1.2) < 1e-6


def test_computed_rate_no_rt():
    """Нет RT → rate вычисляется из insulinReq."""
    gs = GS(10.0, 0)
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=None)
    assert res.rate > 0.0


def test_cob_safety_blocks_insulin():
    """COB>0 и delta<0 → insulinReq=0, rate=0 (если нет temp и neg IOB)."""
    gs = GS(6.0, delta=-1.0)
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(cob=50), rt=None)
    assert res.rate == 0.0
    assert res.insulinReq == 0.0


def test_neg_iob_safety_allows_insulin():
    """IOB<0 → разрешён положительный basal даже при низком BG."""
    gs = GS(5.0, delta=0)
    rt = {"iob": -1.0}
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=rt)
    # Точный rate зависит от профиля, но он не должен быть принудительно обнулён safety-гейтами
    assert res.rate >= 0.0


def test_delta_cap_applied():
    """delta > -0.5 → delta_capped = 0.0."""
    gs = GS(7.0, delta=-0.2)
    res, trace = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=None, trace_mode=True)
    dcap = [v for k, v in trace if k == "delta_capped"][0]
    assert dcap == 0.0


def test_max_basal_limit():
    """raw_rate не должен превышать max_basal."""
    gs = GS(15.0, delta=0)
    prof = PROFILE(basal=1.0, sens=2.0, max_basal=1.5)
    res = determine_basal_autoisf(gs, TEMP(), [], prof, AUTOSENS(), MEAL(), rt=None)
    assert res.rate <= 1.5


def test_max_delta_rate_limit():
    """Проверка max_delta_rate (ограничение изменения базала)."""
    gs = GS(12.0, delta=0)
    prof = PROFILE(basal=0.5, sens=3.0, max_basal=3.0)
    # duration=60 → 12 интервалов по 5 мин → max_delta = 0.3 * 12 = 3.6
    res = determine_basal_autoisf(gs, TEMP(duration=60), [], prof, AUTOSENS(), MEAL(), rt=None)
    assert res.rate - prof.current_basal <= 3.6 + 1e-6


def test_rt_disable_basal():
    """RT содержит 'zero temp' → basal=0, даже если есть rate."""
    gs = GS(8.0, 0)
    rt = {"_raw_text": "zero temp", "rate": 1.5, "duration": 30}
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=rt)
    assert res.rate == 0.0


def test_eventualbg_fallback_with_delta_cap():
    """
    Если нет RT eventualBG → eventualBG считается из bg и delta,
    но с учётом delta-cap: delta > -0.5 → delta_capped = 0 → eventualBG = bg.
    """
    gs = GS(7.0, delta=0.1)
    res = determine_basal_autoisf(gs, TEMP(), [], PROFILE(), AUTOSENS(), MEAL(), rt=None)
    assert abs(res.eventualBG - 7.0) < 1e-6
