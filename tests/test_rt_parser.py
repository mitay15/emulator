import pytest
from aaps_emulator.core.autoisf_algorithm import _extract_predicted_eventual_from_rt

def test_extract_eventual_from_keyvalue_mgdl():
    s = "eventualBG=244.0 duration=30 rate=0.46"
    ev = _extract_predicted_eventual_from_rt(s)
    assert pytest.approx(ev, rel=1e-6) == 244.0 / 18.0


def test_extract_eventual_from_text_phrase_mmol():
    s = "Eventual BG 13,4 ; setting 30m low temp of 0.46U/h"
    ev = _extract_predicted_eventual_from_rt(s)
    assert pytest.approx(ev, rel=1e-6) == 13.4

def test_no_rt_returns_none():
    assert _extract_predicted_eventual_from_rt(None) is None

def test_extract_from_dict_predBGs():
    rt = {"predBGs": [120, 130, 140]}
    ev = _extract_predicted_eventual_from_rt(rt)
    # 140 mg/dL -> 7.777 mmol/L
    assert pytest.approx(ev, rel=1e-6) == 140 / 18.0

def test_string_without_eventual():
    s = "Some random log without eventualBG"
    assert _extract_predicted_eventual_from_rt(s) is None
