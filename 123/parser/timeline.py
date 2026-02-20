import os
from typing import List
from parser.log_parser_json import AAPS34JSONParser


class TimelineEvent:
    def __init__(self, ts: int, kind: str, data: dict, raw: str):
        self.ts = ts
        self.kind = kind
        self.data = data
        self.raw = raw


class TimelineBuilder:
    def __init__(self, folder: str):
        self.folder = folder
        self.parser = AAPS34JSONParser()

    def _safe_ts(self, ts):
        """Приводим timestamp к int, если возможно."""
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            return int(ts)
        if isinstance(ts, str):
            # если строка — пробуем преобразовать
            if ts.isdigit():
                return int(ts)
            # ISO8601?
            try:
                return self.parser._parse_iso8601(ts)
            except:
                return None
        return None

    def build_timeline(self) -> List[TimelineEvent]:
        events: List[TimelineEvent] = []

        for root, _, files in os.walk(self.folder):
            for fn in files:
                if not fn.lower().endswith((".txt", ".log")):
                    continue

                path = os.path.join(root, fn)
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            fs = self.parser.fast_scan(line)
                            if not fs:
                                continue

                            # BG
                            if "glucose" in fs and isinstance(fs["glucose"], dict):
                                ts = self._safe_ts(
                                    self.parser.extract_timestamp_from_json(fs["glucose"])
                                )
                                if ts:
                                    events.append(TimelineEvent(ts, "GLUCOSE", fs["glucose"], line))

                            # IOB
                            if "iob" in fs and isinstance(fs["iob"], dict):
                                ts = self._safe_ts(
                                    self.parser.extract_timestamp_from_json(fs["iob"])
                                )
                                if ts:
                                    events.append(TimelineEvent(ts, "IOB", fs["iob"], line))

                            # COB
                            if "cob" in fs and isinstance(fs["cob"], dict):
                                ts = self._safe_ts(fs["cob"].get("timestamp"))
                                if ts:
                                    events.append(TimelineEvent(ts, "COB", fs["cob"], line))

                            # RESULT
                            if "result" in fs and isinstance(fs["result"], dict):
                                ts = self._safe_ts(
                                    self.parser.extract_timestamp_from_json(fs["result"])
                                )
                                if ts:
                                    events.append(TimelineEvent(ts, "RESULT", fs["result"], line))

                            # SMB / BOLUS / CARBS
                            for k in ("smb", "bolus", "carbs"):
                                if k in fs and isinstance(fs[k], dict):
                                    ts = self._safe_ts(fs[k].get("timestamp"))
                                    if ts:
                                        events.append(TimelineEvent(ts, k.upper(), fs[k], line))

                            # PROFILE
                            if "profile" in fs and isinstance(fs["profile"], dict):
                                ts = self._safe_ts(fs["profile"].get("timestamp"))
                                if ts:
                                    events.append(TimelineEvent(ts, "PROFILE", fs["profile"], line))

                            # PROFILE SWITCH
                            if "profileSwitch" in fs and isinstance(fs["profileSwitch"], dict):
                                ts = self._safe_ts(fs["profileSwitch"].get("timestamp"))
                                if ts:
                                    events.append(TimelineEvent(ts, "PROFILE_SWITCH", fs["profileSwitch"], line))

                            # SETTINGS
                            if "preferences" in fs and isinstance(fs["preferences"], dict):
                                ts = self._safe_ts(fs["preferences"].get("timestamp"))
                                if ts:
                                    events.append(TimelineEvent(ts, "SETTINGS", fs["preferences"], line))


                except Exception as e:
                    print("Error reading", path, e)

        # теперь ts гарантированно int → сортировка безопасна
        events.sort(key=lambda e: e.ts)
        return events
