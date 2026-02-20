def compare_suggested_vs_emulator(cycles, emulator):
    diffs = []

    for c in cycles:
        g = c.get("glucose")
        p = c.get("profile")
        s = c.get("suggested")
        result = c.get("result")

        if not (g and p and s and result):
            continue

        from emulator.cycle_model import CycleInput

        ci = CycleInput(
            glucose=g,
            profile=p,
            autosens=None,
            autoisf=c.get("autoisf"),
            iob=None,
            cob=None,
            predictions=result.get("predBGs"),
        )

        emu = emulator.compute_from_input(ci)
        if not emu:
            continue

        real = s.get("insulinReq")
        if not real or real == 0:
            continue

        diff = (emu.insulinReq - real) / real * 100.0
        diffs.append(diff)

    if not diffs:
        return diffs, None

    avg = sum(diffs) / len(diffs)
    return diffs, avg
