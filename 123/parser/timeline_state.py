# parser/timeline_state.py

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from parser.timeline import TimelineEvent
import copy

# ВАЖНО: импортируем CycleInput
from emulator.cycle_model import CycleInput


# ---------------------------------------------------------
# 1. TimelineState — текущее состояние AAPS в момент времени
# ---------------------------------------------------------
@dataclass
class TimelineState:
    ts: int = 0

    # BG
    glucose: Optional[Dict[str, Any]] = None

    # IOB / COB
    iob: Optional[Dict[str, Any]] = None
    cob: Optional[float] = None

    # Autosens / AutoISF
    autosens: Optional[Dict[str, Any]] = None
    autoisf: Optional[Dict[str, Any]] = None

    # Targets
    target_bg: Optional[float] = None
    temp_target: Optional[Dict[str, Any]] = None

    # Basal
    basal_profile: Optional[Dict[str, Any]] = None
    temp_basal: Optional[Dict[str, Any]] = None

    # Settings (maxIOB, SMB flags, UAM flags, etc.)
    settings: Dict[str, Any] = field(default_factory=dict)

    # Predictions (from RESULT)
    predictions: Optional[Dict[str, Any]] = None

    # -----------------------------------------------------
    # Преобразование в CycleInput для движка
    # -----------------------------------------------------
    def to_cycle_input(self):
        """
        Возвращает объект CycleInput, который понимает движок determine_basal.
        """

        # Дефолты, если профиль отсутствует
        sens = self._extract_isf() or 50
        target = self._extract_target() or 100
        basal = self.basal_profile or {"00:00": 0.6}

        return CycleInput(
            glucose=self.glucose,
            profile={
                "sens": sens,
                "target_bg": target,
                "basal_profile": basal,
            },
            autosens=self.autosens,
            autoisf=self._extract_autoisf_factor(),
            iob=self.iob,
            cob=self.cob,
            predictions=self.predictions,
        )

    # ---------------- internal helpers ----------------
    def _extract_isf(self):
        if self.autoisf and "factor" in self.autoisf:
            return self.autoisf["factor"]
        if self.autosens and "ratio" in self.autosens:
            return self.autosens["ratio"]
        return None

    def _extract_target(self):
        if self.temp_target and "target" in self.temp_target:
            return self.temp_target["target"]
        return self.target_bg

    def _extract_autoisf_factor(self):
        if self.autoisf and "factor" in self.autoisf:
            return self.autoisf["factor"]
        return None


# ---------------------------------------------------------
# 2. TimelineStateBuilder — строит состояние по событиям
# ---------------------------------------------------------
class TimelineStateBuilder:
    def __init__(self, events: List[TimelineEvent]):
        self.events = events
        self.state = TimelineState()

    def build(self) -> List[Tuple[int, TimelineState]]:
        out = []

        for ev in self.events:
            self.state.ts = ev.ts

            if ev.kind == "GLUCOSE":
                self.state.glucose = ev.data

            elif ev.kind == "IOB":
                self.state.iob = ev.data

            elif ev.kind == "COB":
                self.state.cob = ev.data.get("cob")

            elif ev.kind == "AUTOSENS":
                self.state.autosens = ev.data

            elif ev.kind == "AUTOISF":
                self.state.autoisf = ev.data

            elif ev.kind == "TARGET":
                self.state.temp_target = ev.data

            elif ev.kind == "TEMP_BASAL":
                self.state.temp_basal = ev.data

            # -------------------------
            # PROFILE (основной профиль)
            # -------------------------
            elif ev.kind == "PROFILE":
                # AAPS хранит профиль в разных форматах, но обычно:
                # { "basalprofile": {...}, "target_bg": X, "isf": Y, ... }
                self.state.basal_profile = ev.data.get("basalprofile")
                if "target_bg" in ev.data:
                    self.state.target_bg = ev.data["target_bg"]
                self.state.settings.update(ev.data)

            # -------------------------
            # PROFILE SWITCH
            # -------------------------
            elif ev.kind == "PROFILE_SWITCH":
                prof = ev.data.get("profile")
                if prof:
                    self.state.basal_profile = prof.get("basalprofile")
                    if "target_bg" in prof:
                        self.state.target_bg = prof["target_bg"]
                    self.state.settings.update(prof)

            # -------------------------
            # SETTINGS (preferencesJson)
            # -------------------------
            elif ev.kind == "SETTINGS":
                self.state.settings.update(ev.data)
                if "target_bg" in ev.data:
                    self.state.target_bg = ev.data["target_bg"]

            # -------------------------
            # RESULT (predBGs)
            # -------------------------
            elif ev.kind == "RESULT":
                self.state.predictions = ev.data.get("predBGs")

            # SMB / BOLUS / CARBS — не меняют state напрямую

            out.append((ev.ts, copy.deepcopy(self.state)))

        return out
