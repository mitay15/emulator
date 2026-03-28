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

    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]

    if _number_re.match(s.replace(" ", "")):
        s2 = s.replace(",", ".")
        try:
            return float(s2) if "." in s2 else int(s2)
        except Exception:
            return s

    return s


def _find_matching(s: str, start: int, open_ch: str, close_ch: str) -> int:
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("No matching bracket found")


def _split_fields(content: str) -> List[Tuple[str, str]]:
    fields: List[Tuple[str, str]] = []
    i = 0
    L = len(content)

    while i < L:
        while i < L and content[i].isspace():
            i += 1
        if i >= L:
            break

        # key
        j = i
        while j < L and content[j] not in "=,()[]":
            j += 1

        if j < L and content[j] == "=":
            key = content[i:j].strip()
            i = j + 1
            while i < L and content[i].isspace():
                i += 1
            if i >= L:
                fields.append((key, ""))
                break

            ch = content[i]
            if ch in "([":
                end = _find_matching(content, i, ch, ")" if ch == "(" else "]")
                val = content[i : end + 1]
                i = end + 1
            elif ch.isalpha():
                k = i
                while k < L and (content[k].isalnum() or content[k] == "_"):
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
                depth_par = depth_br = 0
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

            while i < L and content[i].isspace():
                i += 1
            if i < L and content[i] == ",":
                i += 1

            fields.append((key, val))
        else:
            # positional / flag
            k = i
            depth_par = depth_br = 0
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
            if token:
                fields.append((token, "true"))

    return fields


def _parse_list(inner: str) -> List[Any]:
    if not inner.strip():
        return []

    items: List[Any] = []
    i = 0
    L = len(inner)

    while i < L:
        while i < L and inner[i].isspace():
            i += 1
        if i >= L:
            break

        ch = inner[i]
        if ch == "[":
            end = _find_matching(inner, i, "[", "]")
            items.append(_parse_value(inner[i : end + 1]))
            i = end + 1
        elif ch.isalpha():
            j = i
            while j < L and (inner[j].isalnum() or inner[j] == "_"):
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
            depth_par = depth_br = 0
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


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return ""
    m = re.match(r"^([A-Za-z_]\w*)\s*\(", raw)
    if m:
        return parse_kotlin_object(raw)
    if raw.startswith("[") and raw.endswith("]"):
        return _parse_list(raw[1:-1])
    return _to_number_if_needed(raw)


def parse_kotlin_object(s: str) -> Dict[str, Any]:
    s = s.strip()

    m = re.match(r"^([A-Za-z_]\w*)\s*\(", s)
    if not m:
        raise ValueError("String does not start with object name and '('")
    name = m.group(1)
    start_par = s.find("(", m.end() - 1)
    end_par = _find_matching(s, start_par, "(", ")")
    content = s[start_par + 1 : end_par].strip()

    obj: Dict[str, Any] = {"__type__": name}
    if not content:
        return obj

    for k, raw_val in _split_fields(content):
        key = k.split("=", 1)[0].strip()
        try:
            val = _parse_value(raw_val)
        except Exception:
            val = raw_val
        obj[key] = val

    return obj
