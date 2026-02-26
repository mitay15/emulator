import pytest

from aaps_emulator.core.autoisf_algorithm import determine_basal_autoisf


class Dummy:
    pass


def make_profile():
    p = Dummy()
    p.sens = 6.0
    p.max_basal = 3.0
    p.target_bg = 6.0
    p.current_basal = 1.0
    return p


def make_glucose(bg=6.0, delta=0.0):
    g = Dummy()
    g.glucose = bg
    g.delta = delta
    return g


def test_rt_lowtemp_forces_zero_rate():
    gs = make_glucose()
    profile = make_profile()
    rt = "setting 30m low temp of 0.46U/h"

    res = determine_basal_autoisf(gs, None, None, profile, None, None, rt=rt)
    assert res.rate == 0.0


def test_rt_eventualBG_overrides_projection():
    gs = make_glucose(bg=10.0, delta=-1.0)
    profile = make_profile()
    rt = "eventualBG=144"  # mg/dL → 8.0 mmol/L

    res = determine_basal_autoisf(gs, None, None, profile, None, None, rt=rt)
    assert pytest.approx(res.eventualBG, rel=1e-6) == 144 / 18


def test_rt_rate_has_priority():
    gs = make_glucose(bg=10.0, delta=0.0)
    profile = make_profile()
    rt = "rate=1.23 duration=30"

    res = determine_basal_autoisf(gs, None, None, profile, None, None, rt=rt)
    assert pytest.approx(res.rate, rel=1e-6) == 1.23
