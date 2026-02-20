class SuggestedData:
    def __init__(self, j: dict):
        self.insulinReq = j.get("insulinReq")
        self.rate = j.get("rate")
        self.duration = j.get("duration")
        self.reason = j.get("reason")

    def __repr__(self):
        return (
            f"SuggestedData(insulinReq={self.insulinReq}, "
            f"rate={self.rate}, duration={self.duration})"
        )
