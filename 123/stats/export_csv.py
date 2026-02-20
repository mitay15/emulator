import csv


def export_cycles_to_csv(cycles, path: str):
    if not cycles:
        return

    fieldnames = [
        "bg",
        "delta",
        "target_bg",
        "isf",
        "autoisf_factor",
        "insulinReq",
        "rate",
        "duration",
        "reason",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()

        for c in cycles:
            g = c.get("glucose") or {}
            p = c.get("profile") or {}
            s = c.get("suggested") or {}
            row = {
                "bg": g.get("glucose"),
                "delta": g.get("delta"),
                "target_bg": p.get("target_bg"),
                "isf": p.get("sens"),
                "autoisf_factor": c.get("autoisf"),
                "insulinReq": s.get("insulinReq"),
                "rate": s.get("rate"),
                "duration": s.get("duration"),
                "reason": s.get("reason"),
            }
            w.writerow(row)
