import re
from aaps_emulator.parsing.utils import clean_num

def parse_rt(rt_line):
    def get(name):
        m = re.search(rf"{name}=([0-9.\-E]+)", rt_line)
        return clean_num(m.group(1).rstrip(",")) if m else None

    return {
        "bg": get("bg"),
        "tick": get("tick"),
        "eventualBG": get("eventualBG"),
        "targetBG": get("targetBG"),
        "insulinReq": get("insulinReq"),
        "duration": int(get("duration") or 0),
        "rate": get("rate"),
        "iob": get("IOB"),
        "variable_sens": get("variable_sens")
    }
