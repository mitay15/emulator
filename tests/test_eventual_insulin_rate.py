import pytest

from aaps_emulator.core.eventual_insulin_rate import (
    apply_basal_limits,
    combine_pred_curves,
    insulin_required_from_eventual,
    mgdl_to_mmol,
    rate_from_insulinReq,
)


class DummyProfile:
    def __init__(self, current_basal=0.7, max_basal=2.4, max_daily_basal=0.8, max_delta_rate=2.0):
        self.current_basal = current_basal
        self.max_basal = max_basal
        self.max_daily_basal = max_daily_basal
        self.max_delta_rate = max_delta_rate


def test_mgdl_mmol_roundtrip():
    assert mgdl_to_mmol(180.0) == pytest.approx(10.0)


def test_combine_pred_curves_empty():
    res = combine_pred_curves({})
    assert isinstance(res, dict)
    assert "eventual_mgdl" in res


def test_insulin_required_and_rate():
    eventual_mmol = 10.0
    target = 6.0
    sens = 2.0
    ins_req = insulin_required_from_eventual(eventual_mmol, target, sens)
    assert ins_req == pytest.approx((10.0 - 6.0) / 2.0)
    rate = rate_from_insulinReq(ins_req, duration_min=30)
    assert rate == pytest.approx(ins_req * 60.0 / 30.0)


def test_apply_basal_limits_respect_max_daily():
    profile = DummyProfile()
    rate = 5.0
    limits = apply_basal_limits(rate, profile, respect_max_daily=True)
    assert limits["raw_rate_after_max_basal"] <= profile.max_basal
    assert limits["final_rate"] <= profile.max_daily_basal


def test_apply_basal_limits_ignore_max_daily():
    profile = DummyProfile()
    rate = 5.0
    limits = apply_basal_limits(rate, profile, respect_max_daily=False)
    assert limits["final_rate"] <= profile.max_basal
