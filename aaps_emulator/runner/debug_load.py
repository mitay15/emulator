from aaps_emulator.runner.load_logs import load_logs

objs = load_logs("data/logs/AndroidAPS.2026-01-15.0.log.zip")

print("TOTAL OBJECTS:", len(objs))
for i, o in enumerate(objs[:20]):
    print(i, o)
