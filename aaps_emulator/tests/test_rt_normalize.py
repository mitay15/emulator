import pytest

from aaps_emulator.parsing.rt_parser import normalize_rt


def test_normalize_rt_from_string_mgdl_and_keys():
    s = "eventualBG=144 duration=30 rate=0.5 insulinReq=0.2 variableSens=7"
    r = normalize_rt(s)

    # keys present and normalized to snake_case
    assert "eventual_bg" in r
    assert "duration" in r
    assert "rate" in r
    assert "insulin_req" in r
    assert "variable_sens" in r

    # mg/dL -> mmol/L conversion (144 mg/dL -> 8.0 mmol/L)
    assert pytest.approx(r["eventual_bg"], rel=1e-6) == 144.0 / 18.0

    # numeric coercions
    assert r["duration"] == 30
    assert pytest.approx(r["rate"], rel=1e-6) == 0.5
    assert pytest.approx(r["insulin_req"], rel=1e-6) == 0.2
    assert pytest.approx(r["variable_sens"], rel=1e-6) == 7.0


def test_normalize_rt_from_dict_no_conversion_needed():
    src = {"eventual_bg": 6.5, "targetBG": 120, "iob": "1.5"}
    r = normalize_rt(src)

    # eventual_bg already numeric and <=30 -> treated as mmol/L (no conversion)
    assert pytest.approx(r["eventual_bg"], rel=1e-6) == 6.5

    # targetBG (camelCase) should be mapped to target_bg and converted (120 mg/dL -> 120/18)
    assert pytest.approx(r["target_bg"], rel=1e-6) == 120.0 / 18.0

    # iob string -> float
    assert pytest.approx(r["iob"], rel=1e-6) == 1.5
