from typing import List, Dict, Any
from parser.timeline import TimelineEvent


def analyze_smb_effectiveness(events: List[TimelineEvent]) -> Dict[str, Any]:
    smb_events = [e for e in events if e.kind == "SMB"]
    bg_events = [e for e in events if e.kind == "BG"]

    if not smb_events or not bg_events:
        return {"count": 0, "avg_delta_per_unit": 0.0, "points": []}

    def find_bg_at(ts_target: int):
        best = None
        best_dt = None
        for bg in bg_events:
            dt = abs(bg.ts - ts_target)
            if best is None or dt < best_dt:
                best = bg
                best_dt = dt
        return best

    points = []
    deltas = []

    for smb in smb_events:
        ins = smb.data.get("insulin")
        if not ins or ins <= 0:
            continue

        bg_before = find_bg_at(smb.ts)
        bg_after = find_bg_at(smb.ts + 60 * 60 * 1000)

        if not bg_before or not bg_after:
            continue

        v_before = bg_before.data.get("glucose") or bg_before.data.get("value")
        v_after = bg_after.data.get("glucose") or bg_after.data.get("value")
        if v_before is None or v_after is None:
            continue

        delta = v_after - v_before
        per_unit = delta / ins
        deltas.append(per_unit)

        points.append({
            "timestamp": smb.ts,
            "delta_per_unit": per_unit,
        })

    if not deltas:
        return {"count": 0, "avg_delta_per_unit": 0.0, "points": []}

    avg = sum(deltas) / len(deltas)
    return {"count": len(deltas), "avg_delta_per_unit": avg, "points": points}
