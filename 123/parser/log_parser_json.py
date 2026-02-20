import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional


class AAPS34JSONParser:

    # --------------------------
    # JSON extraction
    # --------------------------

    def _extract_json_after_key(self, line: str, key: str):
        idx = line.find(key)
        if idx == -1:
            return None

        start = None
        for ch in ["{", "["]:
            pos = line.find(ch, idx)
            if pos != -1:
                start = pos if start is None else min(start, pos)

        if start is None:
            return None

        opening = line[start]
        closing = "}" if opening == "{" else "]"

        depth = 0
        for i in range(start, len(line)):
            if line[i] == opening:
                depth += 1
            elif line[i] == closing:
                depth -= 1
                if depth == 0:
                    raw = line[start:i + 1]
                    try:
                        return json.loads(raw)
                    except:
                        return None
        return None

    def _ensure_dict(self, js):
        if js is None:
            return None
        if isinstance(js, dict):
            return js
        if isinstance(js, list) and js and isinstance(js[0], dict):
            return js[0]
        return None

    # --------------------------
    # ISO8601 → UTC
    # --------------------------

    def _parse_iso8601(self, value: str) -> Optional[int]:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except:
            return None

    # --------------------------
    # USER ENTRY (локальное → UTC)
    # --------------------------

    def _parse_user_entry_datetime(self, line: str) -> Optional[int]:
        m = re.search(r"USER ENTRY:\s+(\d{2}\.\d{2}\.\d{4}) (\d{2}:\d{2}:\d{2})", line)
        if not m:
            return None

        date_str, time_str = m.group(1), m.group(2)
        local_dt = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M:%S")

        m2 = re.search(r"utcOffset=(\d+)", line)
        offset_ms = int(m2.group(1)) if m2 else 0

        utc_dt = local_dt - timedelta(milliseconds=offset_ms)
        return int(utc_dt.timestamp() * 1000)

    # --------------------------
    # JSON timestamp extraction
    # --------------------------

    def extract_timestamp_from_json(self, js: Dict[str, Any]) -> Optional[int]:
        if "timestamp" in js and isinstance(js["timestamp"], (int, float)):
            return int(js["timestamp"])

        if "timestamp" in js and isinstance(js["timestamp"], str):
            try:
                dt = datetime.fromisoformat(js["timestamp"].replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except:
                pass

        for key in ("date", "time"):
            if key in js:
                try:
                    return int(js[key])
                except:
                    pass

        return None

    # --------------------------
    # JSON BLOCK PARSERS
    # --------------------------

    def parse_glucose_json(self, line: str):
        return self._ensure_dict(self._extract_json_after_key(line, "glucoseStatusJson"))

    def parse_iob_json(self, line: str):
        return self._ensure_dict(self._extract_json_after_key(line, "iobDataJson"))

    def parse_result_json(self, line: str):
        return self._ensure_dict(self._extract_json_after_key(line, "resultJson"))

    def parse_suggested_json(self, line: str):
        return self._ensure_dict(self._extract_json_after_key(line, "suggested"))

    def parse_autosens_json(self, line: str):
        return self._ensure_dict(self._extract_json_after_key(line, "autosensDataJson"))

    def parse_meal_json(self, line: str):
        return self._ensure_dict(self._extract_json_after_key(line, "mealDataJson"))

    # --------------------------
    # USER ENTRY EVENTS
    # --------------------------

    def parse_user_entry_events(self, line: str) -> List[Dict[str, Any]]:
        if "USER ENTRY:" not in line:
            return []

        m_ts = re.search(r"Timestamp\(value=(\d+)\)", line)
        if m_ts:
            ts = int(m_ts.group(1))
        else:
            ts = self._parse_user_entry_datetime(line)

        if ts is None:
            return []

        events = []

        # CARBS — игнорируем CarbDialog (дубль)
        if " CARBS " in line and "Gram(value=" in line:

            if "CarbDialog" in line:
                return []  # ← ключевой фикс

            m = re.search(r"Gram\(value=([\d\.]+)\)", line)
            if m:
                events.append({
                    "kind": "CARBS",
                    "timestamp": ts,
                    "carbs": float(m.group(1))
                })

        # SMB
        if " SMB " in line and "Insulin(value=" in line:
            m = re.search(r"Insulin\(value=([\d\.]+)\)", line)
            if m:
                events.append({
                    "kind": "SMB",
                    "timestamp": ts,
                    "insulin": float(m.group(1))
                })

        # BOLUS WIZARD (без CARBS!)
        if "BOLUS_WIZARD" in line:
            m_ins = re.search(r"Insulin\(value=([\d\.]+)\)", line)
            if m_ins:
                events.append({
                    "kind": "BOLUS",
                    "timestamp": ts,
                    "insulin": float(m_ins.group(1))
                })

        return events

    # --------------------------
    # FAST SCAN
    # --------------------------

    def fast_scan(self, line: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        # BG
        if "glucoseStatusJson" in line:
            out["glucose"] = self.parse_glucose_json(line)

        # IOB
        if "iobDataJson" in line:
            out["iob"] = self.parse_iob_json(line)

        # RESULT
        if "resultJson" in line:
            js = self.parse_result_json(line)
            out["result"] = js
            if js and "cob" in js:
                out["cob"] = {
                    "cob": js["cob"],
                    "timestamp": js.get("timestamp")
                }

        # SUGGESTED (главный источник COB)
        if "suggested={" in line:
            js = self.parse_suggested_json(line)
            out["suggested"] = js
            if js and "COB" in js:
                out["cob"] = {
                    "cob": js["COB"],
                    "timestamp": js.get("timestamp")
                }

        # AUTOSENS
        if "autosensDataJson" in line:
            js = self.parse_autosens_json(line)
            out["autosens"] = js
            if js and "cob" in js:
                out["cob"] = {
                    "cob": js["cob"],
                    "timestamp": js.get("timestamp")
                }

        # MEAL
        if "mealDataJson" in line:
            js = self.parse_meal_json(line)
            out["meal"] = js
            if js and ("mealCOB" in js or "cob" in js):
                out["cob"] = {
                    "cob": js.get("mealCOB") or js.get("cob"),
                    "timestamp": js.get("timestamp")
                }

        # USER ENTRY
        ue = self.parse_user_entry_events(line) or []
        for ev in ue:
            out[ev["kind"].lower()] = ev

        # PROFILE
        if "profileJson" in line:
            js = self._ensure_dict(self._extract_json_after_key(line, "profileJson"))
            if js:
                out["profile"] = js

        # PROFILE SWITCH
        if "profileSwitch" in line:
            js = self._ensure_dict(self._extract_json_after_key(line, "profileSwitch"))
            if js:
                out["profileSwitch"] = js

        # PREFERENCES (settings)
        if "preferencesJson" in line:
            js = self._ensure_dict(self._extract_json_after_key(line, "preferencesJson"))
            if js:
                out["preferences"] = js


        return out
