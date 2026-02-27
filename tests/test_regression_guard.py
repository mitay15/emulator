from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf


def test_regression_no_crash_on_minimal_input():
    class Obj:
        pass

    gs = Obj()
    gs.glucose = 7.0
    gs.delta = 0
    prof = Obj()
    prof.current_basal = 1.0
    prof.sens = 6.0
    prof.variable_sens = 6.0
    prof.max_basal = 3.0
    prof.max_daily_basal = 3.0
    prof.target_bg = 6.0

    res = determine_basal_autoisf(gs, None, [], prof, None, None, rt=None)
    assert res.rate >= 0
