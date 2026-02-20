from parser.timeline import TimelineBuilder

tb = TimelineBuilder("data")
events = tb.build_timeline()

print("BG:", len([e for e in events if e.kind == "BG"]))
print("APS:", len([e for e in events if e.kind == "APS"]))
print("SMB:", len([e for e in events if e.kind == "SMB"]))
print("CARBS:", len([e for e in events if e.kind == "CARBS"]))
print("MEAL:", len([e for e in events if e.kind == "MEAL"]))
print("AUTOSENS:", len([e for e in events if e.kind == "AUTOSENS"]))
print("BOLUS:", len([e for e in events if e.kind == "BOLUS"]))
