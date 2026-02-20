from statistics import mean


class CycleStats:
    """
    cycles — список dict:
        {
          "glucose": {...},
          "profile": {...},
          "autoisf": float | None,
          "result": {...},   # resultJson
          "suggested": {...} # из resultJson или suggested
        }
    """

    def __init__(self):
        self.cycles = []

    def total_cycles(self):
        return len(self.cycles)

    def all_bg(self):
        return [c["glucose"]["glucose"] for c in self.cycles if c.get("glucose")]

    def all_targets(self):
        return [c["profile"]["target_bg"] for c in self.cycles if c.get("profile")]

    def all_isf(self):
        return [c["profile"]["sens"] for c in self.cycles if c.get("profile")]

    def all_insulin_req(self):
        return [c["suggested"]["insulinReq"] for c in self.cycles if c.get("suggested")]

    def all_rates(self):
        return [c["suggested"]["rate"] for c in self.cycles if c.get("suggested")]

    def min_bg(self):
        return min(self.all_bg()) if self.cycles else None

    def max_bg(self):
        return max(self.all_bg()) if self.cycles else None

    def avg_bg(self):
        return mean(self.all_bg()) if self.cycles else None

    def avg_isf(self):
        return mean(self.all_isf()) if self.cycles else None

    def avg_insulin_req(self):
        return mean(self.all_insulin_req()) if self.cycles else None

    def max_insulin_req(self):
        return max(self.all_insulin_req()) if self.cycles else None

    def avg_rate(self):
        return mean(self.all_rates()) if self.cycles else None

    def max_rate(self):
        return max(self.all_rates()) if self.cycles else None

    def summary(self):
        if not self.cycles:
            return "Нет данных для статистики."

        rep = []
        rep.append("=== СТАТИСТИКА ПО ЦИКЛАМ (JSON) ===")
        rep.append(f"Всего циклов: {self.total_cycles()}")
        rep.append("")
        rep.append("--- BG ---")
        rep.append(f"Минимальный BG: {self.min_bg():.2f}")
        rep.append(f"Максимальный BG: {self.max_bg():.2f}")
        rep.append(f"Средний BG: {self.avg_bg():.2f}")
        rep.append("")
        rep.append("--- ISF ---")
        rep.append(f"Средний ISF: {self.avg_isf():.2f}")
        rep.append("")
        rep.append("--- InsulinReq ---")
        rep.append(f"Средний InsulinReq: {self.avg_insulin_req():.3f}")
        rep.append(f"Максимальный InsulinReq: {self.max_insulin_req():.3f}")
        rep.append("")
        rep.append("--- Temp Basal ---")
        rep.append(f"Средний rate: {self.avg_rate():.3f}")
        rep.append(f"Максимальный rate: {self.max_rate():.3f}")
        return "\n".join(rep)
