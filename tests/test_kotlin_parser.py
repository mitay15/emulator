import pytest

from runner.kotlin_parser import parse_kotlin_object


@pytest.mark.unit
def test_simple_object():
    s = "GlucoseStatusAutoIsf(glucose=127.0, delta=1.0, date=1768425315211)"
    obj = parse_kotlin_object(s)
    assert obj["__type__"] == "GlucoseStatusAutoIsf"
    assert obj["glucose"] == 127.0
    assert obj["delta"] == 1.0
    assert obj["date"] == 1768425315211


@pytest.mark.unit
def test_nested_iob():
    s = "IobTotal(time=1768425333719, iob=0.016, iobWithZeroTemp=IobTotal(time=1768420776000, iob=0.0))"
    obj = parse_kotlin_object(s)
    assert obj["__type__"] == "IobTotal"
    assert isinstance(obj["iobWithZeroTemp"], dict)
    assert obj["iobWithZeroTemp"]["time"] == 1768420776000
