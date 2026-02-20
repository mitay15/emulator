def clean_num(s):
    if s is None:
        return None
    s = s.replace(",", ".").strip()
    s = s.rstrip(".")
    try:
        return float(s)
    except:
        return None
