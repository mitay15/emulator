import pytest

from aaps_emulator.core.rt_parser import extract_lowtemp_rate, parse_rt_to_dict


def test_lowtemp_simple():
    s = "setting 30m low temp of 0.46U/h"
    parsed = parse_rt_to_dict(s)
    rate = extract_lowtemp_rate(parsed)
    assert pytest.approx(rate, rel=1e-6) == 0.46


def test_lowtemp_comparison():
    s = "temp 0,10 < 1,56U/hr"
    parsed = parse_rt_to_dict(s)
    rate = extract_lowtemp_rate(parsed)
    assert pytest.approx(rate, rel=1e-6) == 1.56


def test_lowtemp_fallback():
    s = "temp basal 0.30 U/h"
    parsed = parse_rt_to_dict(s)
    rate = extract_lowtemp_rate(parsed)
    assert pytest.approx(rate, rel=1e-6) == 0.30
