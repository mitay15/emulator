# analysis/plots.py
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter, AutoDateLocator
from matplotlib import dates as mdates
from matplotlib.offsetbox import AnnotationBbox, TextArea

from parser.timeline import TimelineEvent

TIR_LOW = 3.9
TIR_HIGH = 10.0


def _ts_to_dt(ts_ms: int) -> datetime:
    return datetime.fromtimestamp(ts_ms / 1000)


def _setup_time_axis(ax, ylabel: str):
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", linestyle="--", linewidth=0.4, alpha=0.6)
    ax.xaxis.set_major_formatter(DateFormatter("%d.%m %H:%M"))
    ax.xaxis.set_major_locator(AutoDateLocator())


def _bg_to_mmol(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    return v / 18.0 if v > 30 else v


def _interp_bg_at_ts(bg_events: List[TimelineEvent], ts_ms: int) -> Tuple[Optional[datetime], Optional[float]]:
    """
    Interpolate BG (mmol/L) at timestamp ts_ms (ms).
    Returns (datetime, bg_mmol) or (None, None) if impossible.
    """
    if not bg_events:
        return None, None

    bg_sorted = sorted(bg_events, key=lambda e: e.ts)

    if ts_ms <= bg_sorted[0].ts:
        v = _bg_to_mmol(bg_sorted[0].data.get("glucose") or bg_sorted[0].data.get("value"))
        return _ts_to_dt(bg_sorted[0].ts), v
    if ts_ms >= bg_sorted[-1].ts:
        v = _bg_to_mmol(bg_sorted[-1].data.get("glucose") or bg_sorted[-1].data.get("value"))
        return _ts_to_dt(bg_sorted[-1].ts), v

    left = None
    right = None
    for i in range(1, len(bg_sorted)):
        if bg_sorted[i - 1].ts <= ts_ms <= bg_sorted[i].ts:
            left = bg_sorted[i - 1]
            right = bg_sorted[i]
            break

    if left is None or right is None:
        nearest = min(bg_sorted, key=lambda e: abs(e.ts - ts_ms))
        v = _bg_to_mmol(nearest.data.get("glucose") or nearest.data.get("value"))
        return _ts_to_dt(nearest.ts), v

    t0, t1 = left.ts, right.ts
    v0 = _bg_to_mmol(left.data.get("glucose") or left.data.get("value"))
    v1 = _bg_to_mmol(right.data.get("glucose") or right.data.get("value"))

    if v0 is None or v1 is None:
        nearest = left if abs(ts_ms - left.ts) < abs(ts_ms - right.ts) else right
        v = _bg_to_mmol(nearest.data.get("glucose") or nearest.data.get("value"))
        return _ts_to_dt(nearest.ts), v

    if t1 == t0:
        interp_v = v0
    else:
        frac = (ts_ms - t0) / (t1 - t0)
        interp_v = v0 + (v1 - v0) * frac

    return _ts_to_dt(ts_ms), interp_v


def _make_tooltip(ax, initial_text: str = "") -> Tuple[AnnotationBbox, TextArea]:
    ta = TextArea(initial_text)
    ab = AnnotationBbox(
        ta,
        (0, 0),
        xybox=(20, 20),
        xycoords='data',
        boxcoords="offset points",
        pad=0.4,
        bboxprops=dict(facecolor="white", edgecolor="black", alpha=0.95),
        arrowprops=dict(arrowstyle="->")
    )
    ab.set_visible(False)
    ax.add_artist(ab)
    return ab, ta


def _detect_uam_segments(bg_events: List[TimelineEvent], carb_events: List[TimelineEvent]):
    if len(bg_events) < 2:
        return []

    carb_times = [c.ts for c in carb_events]
    segments = []

    def has_recent_carbs(ts, window_ms=2 * 60 * 60 * 1000):
        return any(abs(ts - t) <= window_ms for t in carb_times)

    bg_sorted = sorted(bg_events, key=lambda e: e.ts)

    for i in range(1, len(bg_sorted)):
        prev = bg_sorted[i - 1]
        cur = bg_sorted[i]

        dt_min = (cur.ts - prev.ts) / 60000.0
        if dt_min <= 0:
            continue

        prev_bg = _bg_to_mmol(prev.data.get("glucose") or prev.data.get("value"))
        cur_bg = _bg_to_mmol(cur.data.get("glucose") or cur.data.get("value"))
        if prev_bg is None or cur_bg is None:
            continue

        dv = cur_bg - prev_bg
        rate = dv / dt_min

        if rate > 0.2 and not has_recent_carbs(cur.ts):
            segments.append((prev.ts, cur.ts))

    return segments


def _unique_carbs_total(carbs: List[TimelineEvent]) -> float:
    seen = set()
    total = 0.0
    for e in carbs:
        c = float(e.data.get("carbs", 0.0) or 0.0)
        key = (e.ts, round(c, 1))
        if key in seen:
            continue
        seen.add(key)
        total += c
    return total


def _compute_stats(bg: List[TimelineEvent],
                   carbs: List[TimelineEvent],
                   smb: List[TimelineEvent],
                   bolus: List[TimelineEvent]):
    bg_vals = []
    for e in bg:
        v = e.data.get("glucose") or e.data.get("value")
        if v is not None:
            bg_vals.append(_bg_to_mmol(v))

    bg_vals = [v for v in bg_vals if v is not None]

    avg_bg = sum(bg_vals) / len(bg_vals) if bg_vals else None
    min_bg = min(bg_vals) if bg_vals else None
    max_bg = max(bg_vals) if bg_vals else None

    total_carbs = _unique_carbs_total(carbs)
    total_smb = sum(e.data.get("insulin", 0.0) for e in smb)
    total_bolus = sum(e.data.get("insulin", 0.0) for e in bolus)
    total_insulin = total_smb + total_bolus

    in_range = [v for v in bg_vals if TIR_LOW <= v <= TIR_HIGH]
    tir = (len(in_range) / len(bg_vals) * 100.0) if bg_vals else None

    return {
        "avg_bg": avg_bg,
        "min_bg": min_bg,
        "max_bg": max_bg,
        "total_carbs": total_carbs,
        "total_insulin": total_insulin,
        "tir": tir,
    }


# ---------- helper: hit test in pixels ----------
def _hit_test_pixels(ax, xdata_list, ydata_list, event, tol_px=6) -> Optional[int]:
    """
    Manual hit test: transform data coords to display coords and compute pixel distance.
    Returns index of first point within tol_px, or None.
    """
    if not xdata_list:
        return None
    trans = ax.transData
    pts = []
    for x, y in zip(xdata_list, ydata_list):
        if hasattr(x, "timetuple"):
            xn = mdates.date2num(x)
        else:
            xn = x
        px, py = trans.transform((xn, y))
        pts.append((px, py))
    ex, ey = event.x, event.y
    best_idx = None
    best_dist2 = tol_px * tol_px
    for i, (px, py) in enumerate(pts):
        dx = px - ex
        dy = py - ey
        d2 = dx * dx + dy * dy
        if d2 <= best_dist2:
            best_idx = i
            best_dist2 = d2
    return best_idx


def build_overview_layers(fig, events):
    fig.clear()

    gs = fig.add_gridspec(2, 1, height_ratios=[2, 1], hspace=0.08)
    ax_top = fig.add_subplot(gs[0])
    ax_bottom = fig.add_subplot(gs[1], sharex=ax_top)
    ax_bottom_right = ax_bottom.twinx()

    bg = [e for e in events if e.kind == "GLUCOSE"]
    iob = [e for e in events if e.kind == "IOB"]
    cob = [e for e in events if e.kind == "COB"]
    pred = [e for e in events if e.kind == "RESULT"]
    smb = [e for e in events if e.kind == "SMB"]
    bolus = [e for e in events if e.kind == "BOLUS"]
    carbs = [e for e in events if e.kind == "CARBS"]

    layers: Dict[str, Any] = {}

    if not bg:
        ax_top.set_title("No BG data")
        _setup_time_axis(ax_top, "BG (mmol/L)")
        _setup_time_axis(ax_bottom, "IOB / COB")
        fig.tight_layout()
        enable_zoom(fig)
        enable_pan(fig)
        return layers

    # BG arrays (datetime and mmol)
    bg_x = [_ts_to_dt(e.ts) for e in bg]
    bg_y = [_bg_to_mmol(e.data.get("glucose") or e.data.get("value")) for e in bg]

    # TIR zone
    ax_top.axhspan(TIR_LOW, TIR_HIGH, color="lightblue", alpha=0.25, zorder=0)

    # BG line
    ln_bg, = ax_top.plot(bg_x, bg_y, color="#1f77b4", linewidth=1.2, label="BG")
    layers["BG"] = ln_bg

    bg_colors = ["green" if (y is not None and TIR_LOW <= y <= TIR_HIGH) else "red" for y in bg_y]

    # --------------------------
    # SMB: own timestamp, interpolated BG for Y
    # --------------------------
    smb_objs = []
    smb_x, smb_y, smb_vals, smb_events = [], [], [], []
    smb_arrows = []  # store arrow Annotation artists for hit-testing
    for e in smb:
        ts = e.ts
        dt, bg_val = _interp_bg_at_ts(bg, ts)
        if dt is None or bg_val is None:
            continue
        smb_x.append(dt)
        smb_y.append(bg_val)
        smb_vals.append(float(e.data.get("insulin", 0.0) or 0.0))
        smb_events.append(e)

    for idx, (x, y, v) in enumerate(zip(smb_x, smb_y, smb_vals)):
        stagger = (idx % 3) * 0.12
        top = y + 0.35 + stagger
        mid = y + 0.12 + stagger
        ln = ax_top.plot([x, x], [top, mid], color="#ffd700", linewidth=2, zorder=6)
        smb_objs.extend(ln)
        # create arrow annotation and keep reference
        arr = ax_top.annotate(
            "",
            xy=(x, mid - 0.02),
            xytext=(x, top),
            arrowprops=dict(arrowstyle="-|>", color="#ffd700", lw=1.4),
            zorder=7
        )
        smb_objs.append(arr)
        smb_arrows.append(arr)
        if v >= 0.4:
            txt = ax_top.text(x, top + 0.05, f"{v:.1f}", fontsize=8, color="#ffd700", ha="center", va="bottom", zorder=8)
            smb_objs.append(txt)

    layers["SMB"] = smb_objs
    layers["SMB_ARROWS"] = smb_arrows

    # --------------------------
    # Bolus: own timestamp, interpolated BG for Y
    # --------------------------
    bol_x, bol_y, bol_txt, bol_events = [], [], [], []
    for e in bolus:
        ts = e.ts
        dt, bg_val = _interp_bg_at_ts(bg, ts)
        if dt is None or bg_val is None:
            continue
        bol_x.append(dt)
        bol_y.append(bg_val)
        val = float(e.data.get("insulin", 0.0) or 0.0)
        bol_txt.append(f"{val:.1f}U")
        bol_events.append(e)

    bolus_objs = []
    for idx, (x, y, t) in enumerate(zip(bol_x, bol_y, bol_txt)):
        stagger = (idx % 3) * 0.18
        txt = ax_top.text(x, y + 0.45 + stagger, t, fontsize=8, color="#ff8800", ha="center", va="bottom", zorder=7)
        bolus_objs.append(txt)
    layers["Bolus"] = bolus_objs

    # --------------------------
    # Carbs: own timestamp, interpolated BG for Y (star marker)
    # --------------------------
    carb_x, carb_y, carb_txt, carb_events = [], [], [], []
    for e in carbs:
        ts = e.ts
        dt, bg_val = _interp_bg_at_ts(bg, ts)
        if dt is None or bg_val is None:
            continue
        carb_x.append(dt)
        carb_y.append(bg_val)
        carb_txt.append(f"{int(e.data.get('carbs', 0))}g")
        carb_events.append(e)

    carbs_objs = []
    for idx, (x, y, t) in enumerate(zip(carb_x, carb_y, carb_txt)):
        stagger = (idx % 3) * 0.18
        txt = ax_top.text(x, y - 0.55 - stagger, t, fontsize=8, color="black", ha="center", va="top", zorder=6)
        carbs_objs.append(txt)
    layers["Carbs"] = carbs_objs

    # Create pickable/hoverable scatters (after annotations)
    sc_bg = ax_top.scatter(bg_x, bg_y, c=bg_colors, s=40, edgecolors="black", linewidths=0.3, zorder=40)
    layers["BG_POINTS"] = sc_bg

    sc_smb = ax_top.scatter(smb_x, smb_y, s=140, facecolors='none', edgecolors='none', alpha=0.01, zorder=50)
    layers["SMB_SCATTER"] = sc_smb

    sc_bolus = None
    if bol_x:
        sc_bolus = ax_top.scatter(bol_x, bol_y, color="#ff8800", s=140, marker="v", edgecolors="black", linewidths=0.7, zorder=46)

    sc_carbs = None
    if carb_x:
        sc_carbs = ax_top.scatter(carb_x, carb_y, color="#ffeb3b", edgecolors="black", s=120, marker="*", zorder=45)

    ax_top.set_title("BG / Carbs / SMB / Bolus")
    _setup_time_axis(ax_top, "BG (mmol/L)")

    # PredBG / IOB / COB (bottom)
    if pred:
        pred_x = []
        pred_y = []
        for e in pred:
            dt = _ts_to_dt(e.ts)
            predBGs = e.data.get("predBGs")
            if predBGs and "IOB" in predBGs:
                v = predBGs["IOB"][0]
                pred_x.append(dt)
                pred_y.append(_bg_to_mmol(v))
            else:
                pred_x.append(dt)
                pred_y.append(None)
        ln_pred, = ax_bottom.plot(pred_x, pred_y, color="green", linestyle="--", label="PredBG")
        layers["PredBG"] = ln_pred
    else:
        layers["PredBG"] = ax_bottom.plot([], [])[0]

    if iob:
        iob_x = [_ts_to_dt(e.ts) for e in iob]
        iob_y = [e.data.get("iob") for e in iob]
        ln_iob, = ax_bottom.plot(iob_x, iob_y, color="#2ca02c", label="IOB")
        layers["IOB"] = ln_iob
    else:
        layers["IOB"] = ax_bottom.plot([], [])[0]

    if cob:
        cob_x = [_ts_to_dt(e.ts) for e in cob]
        cob_y = [e.data.get("cob") for e in cob]
        ln_cob, = ax_bottom_right.plot(cob_x, cob_y, color="#ff7f0e", label="COB")
        layers["COB"] = ln_cob
    else:
        layers["COB"] = ax_bottom_right.plot([], [])[0]

    ax_bottom.set_title("PredBG / IOB / COB / UAM")
    _setup_time_axis(ax_bottom, "IOB (U)")
    ax_bottom_right.set_ylabel("COB (g)")

    # UAM highlight
    uam_segments = _detect_uam_segments(bg, carbs)
    for start_ts, end_ts in uam_segments:
        ax_bottom.axvspan(_ts_to_dt(start_ts), _ts_to_dt(end_ts), color="red", alpha=0.12, zorder=0)

    # Statistics on the right: use tight_layout + subplots_adjust to avoid warning
    stats = _compute_stats(bg, carbs, smb, bolus)
    lines = []
    if stats["avg_bg"] is not None:
        lines.append(f"Avg BG: {stats['avg_bg']:.1f} mmol/L")
    if stats["min_bg"] is not None and stats["max_bg"] is not None:
        lines.append(f"Min BG: {stats['min_bg']:.1f}")
        lines.append(f"Max BG: {stats['max_bg']:.1f}")
    lines.append(f"Total carbs: {stats['total_carbs']:.0f} g")
    lines.append(f"Total insulin: {stats['total_insulin']:.2f} U")
    if stats["tir"] is not None:
        lines.append(f"TIR {TIR_LOW:.1f}–{TIR_HIGH:.1f}: {stats['tir']:.1f}%")

    text = "\n".join(lines)
    fig.tight_layout()
    fig.subplots_adjust(right=0.78)
    fig.text(0.82, 0.95, text, transform=fig.transFigure, va="top", ha="left", fontsize=9,
             bbox=dict(boxstyle="round", facecolor="white", alpha=0.95))

    # --------------------------
    # Tooltips: single AnnotationBbox + TextArea per type; update via motion hit-test
    # --------------------------
    bg_ab, bg_ta = _make_tooltip(ax_top, "")
    smb_ab, smb_ta = _make_tooltip(ax_top, "")
    bolus_ab, bolus_ta = _make_tooltip(ax_top, "")
    carb_ab, carb_ta = _make_tooltip(ax_top, "")

    # Keep TextArea references in mutable dicts to avoid local rebind issues
    bg_ta_box = {"ta": bg_ta}
    smb_ta_box = {"ta": smb_ta}
    bolus_ta_box = {"ta": bolus_ta}
    carb_ta_box = {"ta": carb_ta}

    for ab in (bg_ab, smb_ab, bolus_ab, carb_ab):
        ab.set_zorder(200)

    def _find_near_event_value(events_list, ts, window_ms=150000):
        for e in events_list:
            if abs(e.ts - ts) <= window_ms:
                if e.kind == "IOB":
                    return e.data.get("iob")
                if e.kind == "COB":
                    return e.data.get("cob")
                if e.kind == "SMB":
                    return e.data.get("insulin")
                if e.kind == "BOLUS":
                    return e.data.get("insulin")
                if e.kind == "CARBS":
                    return e.data.get("carbs")
        return None

    def _update_textarea_box(box: Dict[str, TextArea], ab: AnnotationBbox, text: str):
        """
        Update TextArea stored in box safely. If update fails, replace ab.offsetbox and update box['ta'].
        """
        try:
            child = box["ta"].get_children()[0]
            child.set_text(text)
            return box["ta"]
        except Exception:
            new_ta = TextArea(text)
            ab.offsetbox = new_ta
            box["ta"] = new_ta
            return new_ta

    # motion handler: use manual pixel hit-test for hover
    def on_motion(event):
        if event.inaxes != ax_top:
            changed = False
            for ab in (bg_ab, smb_ab, bolus_ab, carb_ab):
                if ab.get_visible():
                    ab.set_visible(False)
                    changed = True
            if changed and getattr(event, "canvas", None) is not None:
                event.canvas.draw_idle()
            return

        # BG hover (обновлённый: НЕ включает SMB)
        idx_bg = _hit_test_pixels(ax_top, bg_x, bg_y, event, tol_px=6)
        if idx_bg is not None:
            ts = bg[idx_bg].ts
            dt = _ts_to_dt(ts).strftime("%d.%m %H:%M:%S")
            bg_val = bg_y[idx_bg]
            iob_val = _find_near_event_value(iob, ts)
            cob_val = _find_near_event_value(cob, ts)
            bol_val = _find_near_event_value(bolus, ts)
            carb_val = _find_near_event_value(carbs, ts)

            # Собираем текст: SMB здесь НЕ упоминается
            text = f"{dt}\nBG: {bg_val:.1f} mmol/L"
            if iob_val is not None:
                text += f"\nIOB: {iob_val:.2f} U"
            if cob_val is not None:
                text += f"\nCOB: {int(cob_val)} g"
            if bol_val is not None:
                text += f"\nBolus: {bol_val:.2f} U"
            if carb_val is not None:
                text += f"\nCarbs: {int(carb_val)} g"

            _update_textarea_box(bg_ta_box, bg_ab, text)
            bg_ab.xy = (bg_x[idx_bg], bg_y[idx_bg])
            bg_ab.set_visible(True)
            smb_ab.set_visible(False)
            bolus_ab.set_visible(False)
            carb_ab.set_visible(False)
            if getattr(event, "canvas", None) is not None:
                event.canvas.draw_idle()
            return
        else:
            if bg_ab.get_visible():
                bg_ab.set_visible(False)


        # SMB hover: first try arrow bbox hit-test (preferred), then fallback to point hit-test
        renderer = None
        try:
            renderer = event.canvas.get_renderer()
        except Exception:
            renderer = None

        smb_hit = None
        # check arrow annotations' bbox (if renderer available)
        if renderer is not None and smb_arrows:
            for i, arr in enumerate(smb_arrows):
                try:
                    bbox = arr.get_window_extent(renderer)
                    # inflate bbox by a few pixels for easier hover
                    pad = 6
                    x0, y0 = bbox.x0 - pad, bbox.y0 - pad
                    x1, y1 = bbox.x1 + pad, bbox.y1 + pad
                    if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                        smb_hit = i
                        break
                except Exception:
                    continue

        # fallback: pixel hit-test on smb points
        if smb_hit is None:
            smb_hit = _hit_test_pixels(ax_top, smb_x, smb_y, event, tol_px=8)

        if smb_hit is not None:
            ts = smb_events[smb_hit].ts
            dt = _ts_to_dt(ts).strftime("%d.%m %H:%M:%S")
            v = smb_vals[smb_hit]
            text = f"{dt}\nSMB: {v:.2f} U"
            _update_textarea_box(smb_ta_box, smb_ab, text)
            smb_ab.xy = (smb_x[smb_hit], smb_y[smb_hit])
            smb_ab.set_visible(True)
            bg_ab.set_visible(False)
            bolus_ab.set_visible(False)
            carb_ab.set_visible(False)
            if getattr(event, "canvas", None) is not None:
                event.canvas.draw_idle()
            return
        else:
            if smb_ab.get_visible():
                smb_ab.set_visible(False)

        # Bolus hover
        idx_bol = _hit_test_pixels(ax_top, bol_x, bol_y, event, tol_px=8) if bol_x else None
        if idx_bol is not None:
            ts = bol_events[idx_bol].ts
            dt = _ts_to_dt(ts).strftime("%d.%m %H:%M:%S")
            v = float(bol_events[idx_bol].data.get("insulin", 0.0) or 0.0)
            text = f"{dt}\nBolus: {v:.2f} U"
            _update_textarea_box(bolus_ta_box, bolus_ab, text)
            bolus_ab.xy = (bol_x[idx_bol], bol_y[idx_bol])
            bolus_ab.set_visible(True)
            bg_ab.set_visible(False)
            smb_ab.set_visible(False)
            carb_ab.set_visible(False)
            if getattr(event, "canvas", None) is not None:
                event.canvas.draw_idle()
            return
        else:
            if bolus_ab.get_visible():
                bolus_ab.set_visible(False)

        # Carbs hover
        idx_carb = _hit_test_pixels(ax_top, carb_x, carb_y, event, tol_px=8) if carb_x else None
        if idx_carb is not None:
            ts = carb_events[idx_carb].ts
            dt = _ts_to_dt(ts).strftime("%d.%m %H:%M:%S")
            v = int(carb_events[idx_carb].data.get("carbs", 0) or 0)
            text = f"{dt}\nCarbs: {v} g"
            _update_textarea_box(carb_ta_box, carb_ab, text)
            carb_ab.xy = (carb_x[idx_carb], carb_y[idx_carb])
            carb_ab.set_visible(True)
            bg_ab.set_visible(False)
            smb_ab.set_visible(False)
            bolus_ab.set_visible(False)
            if getattr(event, "canvas", None) is not None:
                event.canvas.draw_idle()
            return
        else:
            if carb_ab.get_visible():
                carb_ab.set_visible(False)

    fig.canvas.mpl_connect("motion_notify_event", on_motion)

    # Zoom and pan
    enable_zoom(fig)
    enable_pan(fig)

    return layers


def enable_zoom(fig):
    def on_scroll(event):
        ax = event.inaxes
        if ax is None:
            return

        base = 1.2
        scale = 1 / base if event.button == 'up' else base

        xdata = event.xdata
        ydata = event.ydata
        if xdata is None or ydata is None:
            return

        x_left, x_right = ax.get_xlim()
        y_bottom, y_top = ax.get_ylim()

        ax.set_xlim([xdata - (xdata - x_left) * scale, xdata + (x_right - xdata) * scale])
        ax.set_ylim([ydata - (ydata - y_bottom) * scale, ydata + (y_top - ydata) * scale])

        if getattr(event, "canvas", None) is not None:
            event.canvas.draw_idle()

    fig.canvas.mpl_connect("scroll_event", on_scroll)


def enable_pan(fig):
    pan_state = {"press": None, "xpress_pix": None, "xlim_on_press": None, "ax": None}

    def on_press(event):
        if event.button == 1 and event.inaxes:
            pan_state["press"] = True
            pan_state["xpress_pix"] = event.x
            pan_state["xlim_on_press"] = event.inaxes.get_xlim()
            pan_state["ax"] = event.inaxes

    def on_release(event):
        pan_state["press"] = None
        pan_state["xpress_pix"] = None
        pan_state["xlim_on_press"] = None
        pan_state["ax"] = None

    def on_move(event):
        if not pan_state["press"]:
            return
        if event.inaxes != pan_state["ax"]:
            return
        try:
            dx_pix = event.x - pan_state["xpress_pix"]
            ax = pan_state["ax"]
            x0, x1 = pan_state["xlim_on_press"]
            trans = ax.transData.inverted()
            p0 = trans.transform((0, 0))[0]
            p1 = trans.transform((dx_pix, 0))[0]
            dx_data = p1 - p0
            ax.set_xlim(x0 - dx_data, x1 - dx_data)
            if getattr(event, "canvas", None) is not None:
                event.canvas.draw_idle()
        except Exception:
            pass

    fig.canvas.mpl_connect('button_press_event', on_press)
    fig.canvas.mpl_connect('button_release_event', on_release)
    fig.canvas.mpl_connect('motion_notify_event', on_move)
