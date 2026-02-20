import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

print("TEST STARTED")

from parser.timeline import TimelineEvent
from parser.timeline_state import TimelineStateBuilder

print("IMPORT OK")

def test_basic_state():
    print("BUILDING EVENTS")

    events = [
        TimelineEvent(1000, "GLUCOSE", {"glucose": 120}, "raw1"),
        TimelineEvent(2000, "IOB", {"iob": 0.5}, "raw2"),
        TimelineEvent(3000, "COB", {"cob": 20}, "raw3"),
    ]

    tsb = TimelineStateBuilder(events)
    states = tsb.build()

    print("STATES:", len(states))
    for ts, st in states:
        print("STATE:", ts, st)

test_basic_state()
