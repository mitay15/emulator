from dataclasses import dataclass
from core.glucose import GlucoseData
from core.profile import ProfileData
from core.autoisf import AutoISFData
from core.iob import IOBData


@dataclass
class CycleInput:
    glucose: dict | None
    profile: dict | None
    autosens: None = None
    autoisf: float | None = None
    iob: dict | None = None
    cob: float | None = None
    predictions: dict | None = None

    def to_core(self):
        g = GlucoseData(self.glucose) if self.glucose else None
        p = ProfileData(self.profile) if self.profile else None
        ai = AutoISFData(self.autoisf) if self.autoisf is not None else None
        iob = IOBData(self.iob) if self.iob else None
        return g, p, ai, iob
