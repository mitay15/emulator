class AutoISFData:
    def __init__(self, factor: float | None):
        self.factor = factor

    def __repr__(self):
        return f"AutoISFData(factor={self.factor})"
