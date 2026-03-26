# aaps_emulator/runner/kotlin_parser.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_number_re = re.compile(r"^-?\d+[.,]?\d*$")


def _to_number_if_needed(s: str) -> Any:
    if s is None:
        return None
    s = s.strip()
    if s == "null":
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    # quoted string
    if (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    ):
        return s[1:-1]
    # numeric?
    if _number_re.match(s.replace(" ", "")):
        s2 = s.replace(",", ".")
        try:
            if "." in s2:
                return float(s2)
            else:
                return int(s2)
        except Exception:
            return s
    return s


def _find_matching(s: str, start: int, open_ch: str, close_ch: str) -> int:
    """Find index of matching close_ch for open_ch at start (start points to open_ch)."""
    depth = 0
    i = start
    L = len(s)
    while i < L:
        ch = s[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("No matching bracket found")


def _split_fields(content: str) -> List[Tuple[str, str]]:
    """
    Parse content inside parentheses into list of (key, raw_value) pairs.
    Handles nested parentheses and brackets.
    """
    fields: List[Tuple[str, str]] = []
    i = 0
    L = len(content)
    key = None
    while i < L:
        # skip whitespace
        while i < L and content[i].isspace():
            i += 1
        if i >= L:
            break
        # parse key (until '=' or comma or end)
        j = i
        while j < L and content[j] not in "=,()[]":
            j += 1
        if j < L and content[j] == "=":
            key = content[i:j].strip()
            i = j + 1  # move past '='
            # skip whitespace
            while i < L and content[i].isspace():
                i += 1
            if i >= L:
                fields.append((key, ""))
                break
            ch = content[i]
            if ch == "(":
                end = _find_matching(content, i, "(", ")")
                val = content[i : end + 1]
                i = end + 1
            elif ch == "[":
                end = _find_matching(content, i, "[", "]")
                val = content[i : end + 1]
                i = end + 1
            elif ch.isalpha():
                k = i
                while k < L and (content[k].isalnum() or content[k] in "_"):
                    k += 1
                m = k
                while m < L and content[m].isspace():
                    m += 1
                if m < L and content[m] == "(":
                    end = _find_matching(content, m, "(", ")")
                    val = content[i : end + 1]
                    i = end + 1
                else:
                    k = i
                    while k < L and content[k] != ",":
                        k += 1
                    val = content[i:k].strip()
                    i = k
            else:
                k = i
                depth_par = 0
                depth_br = 0
                while k < L:
                    c = content[k]
                    if c == "(":
                        depth_par += 1
                    elif c == ")":
                        if depth_par == 0:
                            break
                        depth_par -= 1
                    elif c == "[":
                        depth_br += 1
                    elif c == "]":
                        depth_br -= 1
                    elif c == "," and depth_par == 0 and depth_br == 0:
                        break
                    k += 1
                val = content[i:k].strip()
                i = k
            # consume trailing comma if present
            while i < L and content[i].isspace():
                i += 1
            if i < L and content[i] == ",":
                i += 1
            fields.append((key, val))
        else:
            # no '=', treat as flag or positional token
            k = i
            depth_par = 0
            depth_br = 0
            while k < L:
                c = content[k]
                if c == "(":
                    depth_par += 1
                elif c == ")":
                    if depth_par == 0:
                        break
                    depth_par -= 1
                elif c == "[":
                    depth_br += 1
                elif c == "]":
                    depth_br -= 1
                elif c == "," and depth_par == 0 and depth_br == 0:
                    break
                k += 1
            token = content[i:k].strip()
            i = k
            while i < L and content[i].isspace():
                i += 1
            if i < L and content[i] == ",":
                i += 1
            fields.append((token, "true"))
    return fields


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return ""
    # nested object: starts with Name(
    m = re.match(r"^([A-Za-z_]\w*)\s*\(", raw)
    if m:
        # parse nested object
        return parse_kotlin_object(raw)
    # list
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if inner == "":
            return []
        items = []
        i = 0
        L = len(inner)
        while i < L:
            while i < L and inner[i].isspace():
                i += 1
            if i >= L:
                break
            if inner[i] == "[":
                end = _find_matching(inner, i, "[", "]")
                items.append(_parse_value(inner[i : end + 1]))
                i = end + 1
            elif inner[i].isalpha():
                j = i
                while j < L and (inner[j].isalnum() or inner[j] in "_"):
                    j += 1
                k = j
                while k < L and inner[k].isspace():
                    k += 1
                if k < L and inner[k] == "(":
                    end = _find_matching(inner, k, "(", ")")
                    items.append(_parse_value(inner[i : end + 1]))
                    i = end + 1
                else:
                    j = i
                    while j < L and inner[j] != ",":
                        j += 1
                    items.append(_to_number_if_needed(inner[i:j].strip()))
                    i = j
            else:
                j = i
                depth_par = 0
                depth_br = 0
                while j < L:
                    c = inner[j]
                    if c == "(":
                        depth_par += 1
                    elif c == ")":
                        depth_par -= 1
                    elif c == "[":
                        depth_br += 1
                    elif c == "]":
                        depth_br -= 1
                    elif c == "," and depth_par == 0 and depth_br == 0:
                        break
                    j += 1
                token = inner[i:j].strip()
                items.append(_to_number_if_needed(token))
                i = j
            while i < L and inner[i].isspace():
                i += 1
            if i < L and inner[i] == ",":
                i += 1
        return items
    # plain value
    return _to_number_if_needed(raw)


def parse_kotlin_object(s: str) -> Dict[str, Any]:
    """
    Parse a single Kotlin-style object string like:
    Name(field1=val1, field2=Nested(...), list=[1,2,3])
    Returns dict with "__type__": "Name" and parsed fields.
    """
    s = s.strip()
    m = re.match(r"^([A-Za-z_]\w*)\s*\(", s)
    if not m:
        raise ValueError("String does not start with object name and '('")
    name = m.group(1)
    start_par = s.find("(", m.end() - 1)
    end_par = _find_matching(s, start_par, "(", ")")
    content = s[start_par + 1 : end_par].strip()
    obj: Dict[str, Any] = {"__type__": name}
    if content == "":
        return obj
    pairs = _split_fields(content)
    for k, raw_val in pairs:
        key = k.strip()
        if "=" in key:
            key = key.split("=", 1)[0].strip()
        try:
            val = _parse_value(raw_val)
        except Exception:
            val = raw_val
        obj[key] = val
    return obj
