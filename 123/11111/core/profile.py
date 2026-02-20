class ProfileData:
    def __init__(self, j: dict):
        self.target_bg = j.get("target_bg")
        self.sens = j.get("sens")
        self.carb_ratio = j.get("carb_ratio")
        self.current_basal = j.get("current_basal")
        self.max_basal = j.get("max_basal")
        self.max_iob = j.get("max_iob")

    def __repr__(self):
        return f"ProfileData(target={self.target_bg}, ISF={self.sens})"
