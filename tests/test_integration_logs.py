from aaps_emulator.analysis.compare_runner import run_compare_on_all_logs


def test_python_matches_aaps_on_logs(logs_path):
    rows, blocks, inputs = run_compare_on_all_logs(str(logs_path))

    mismatches = []

    for r in rows:
        ev_ref = r.get("eventualBG_ref")
        ev_py = r.get("eventualBG_py")

        if ev_ref is not None and ev_py is not None and abs(ev_ref - ev_py) > 0.2:
            mismatches.append(("eventualBG", r["idx"], ev_ref, ev_py))

        rate_ref = r.get("rate_ref")
        rate_py = r.get("rate_py")

        if rate_ref is not None and rate_py is not None and abs(rate_ref - rate_py) > 0.1:
            mismatches.append(("rate", r["idx"], rate_ref, rate_py))

    assert len(mismatches) == 0, f"Mismatches found: {mismatches[:10]}"
