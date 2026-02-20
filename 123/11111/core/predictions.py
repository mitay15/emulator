class PredictionsData:
    def __init__(self, j: dict | None):
        if not j:
            self.iob = None
            self.zt = None
            self.uam = None
            return

        self.iob = j.get("IOB")
        self.zt = j.get("ZT")
        self.uam = j.get("UAM")

    def min_pred(self):
        vals = []
        if self.iob:
            vals += self.iob
        if self.zt:
            vals += self.zt
        if self.uam:
            vals += self.uam
        return min(vals) if vals else None
