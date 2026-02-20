import re

with open("AndroidAPS.log", "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        if "cob" in line.lower():
            print(line.strip())
