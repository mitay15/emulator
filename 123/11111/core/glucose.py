class GlucoseData:
    def __init__(self, j: dict):
        self.glucose = j.get("glucose")
        self.delta = j.get("delta")
        self.short_avg = j.get("shortAvgDelta")
        self.long_avg = j.get("longAvgDelta")
        self.bg_accel = j.get("bgAcceleration")

    def __repr__(self):
        return f"GlucoseData(glucose={self.glucose}, delta={self.delta})"
