import re

LOG_FILE = "AndroidAPS.2026-01-14.0.log"  # поменяй при необходимости

rt_re = re.compile(r"Result: RT\((.*)\)")
num_re = lambda name: re.compile(rf"{name}=([0-9.,\-]+)")

fields = ["bg", "tick", "eventualBG", "targetBG", "duration", "rate", "IOB", "variable_sens"]

with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
    for lineno, line in enumerate(f, start=1):
        m = rt_re.search(line)
        if not m:
            continue
        body = m.group(1)
        print(f"\n[{lineno}] {line.strip()}")
        for name in fields:
            m2 = num_re(name).search(body)
            if m2:
                val = m2.group(1).replace(",", ".")
                print(f"  {name}: {val}")
