from core.suggested import SuggestedData
from core.predictions import PredictionsData


class DetermineBasalEngine:
    """
    Эмулятор, учитывающий predBGs.
    Работает с CycleInput.to_core() + predictions.
    """

    def __init__(self, max_basal=5.0, min_temp_duration=30):
        self.max_basal = max_basal
        self.min_temp_duration = min_temp_duration

    def compute_from_input(self, ci):
        g, p, autoisf, iob = ci.to_core()
        pred = PredictionsData(ci.predictions)

        if not g or not p:
            return None

        # 1) ISF
        isf = p.sens
        if autoisf and autoisf.factor:
            isf = p.sens * autoisf.factor

        # 2) deviation по текущему BG
        deviation = g.glucose - p.target_bg

        # 3) insulinReq по BG
        insulin_bg = deviation / isf if isf else 0

        # 4) insulinReq по предсказаниям
        insulin_pred = 0
        pred_dev = 0
        if pred.min_pred():
            pred_dev = pred.min_pred() - p.target_bg
            insulin_pred = pred_dev / isf if isf else 0

        # 5) итог
        insulinReq = max(0, insulin_bg + insulin_pred)

        # 6) temp basal
        rate = min(self.max_basal, insulinReq * 2)
        duration = self.min_temp_duration

        reason = (
            f"[EMU] BGdev={deviation:.1f}, PredDev={pred_dev:.1f}, "
            f"ISF={isf}, insulinReq={insulinReq:.3f}"
        )

        return SuggestedData({
            "insulinReq": round(insulinReq, 3),
            "rate": round(rate, 3),
            "duration": duration,
            "reason": reason
        })
