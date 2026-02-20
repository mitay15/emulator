import re
from autoisf_structs import (
    GlucoseStatus, IobTotal, MealData, AutosensResult,
    CurrentTemp, OapsProfileAutoIsf
)
from autoisf_algorithm import determine_basal_autoisf


# ============================================================
#  УСТОЙЧИВЫЕ ПАРСЕРЫ ЧИСЕЛ
# ============================================================

def clean_num(s: str):
    if s is None:
        return None
    s = s.replace(",", ".").strip()
    s = s.rstrip(".")  # убираем лишние точки
    try:
        return float(s)
    except:
        return None


def num(name, text, default=None):
    m = re.search(rf"{name}=([0-9.,\-]+)", text)
    if not m:
        return default
    return clean_num(m.group(1))


def from_console(pattern, text, default=None):
    m = re.search(pattern, text)
    if not m:
        return default
    return clean_num(m.group(1))


# ============================================================
#  ВСТАВЬ СЮДА ЛЮБУЮ RT(...) СТРОКУ
# ============================================================

RT_LINE = r"""
[97883] 14:14:38.598 [DefaultDispatcher-worker-1] D/APS: [OpenAPSAutoISFPlugin.invoke():467]: Result: RT(algorithm=AUTO_ISF, runningDynamicIsf=true, timestamp=1768389278274, temp=absolute, bg=139.0, tick=+7, eventualBG=226.0, targetBG=115.2, snoozeBG=null, insulinReq=0.55, carbsReq=null, carbsReqWithin=null, units=null, deliverAt=1768389278274, sensitivityRatio=1.0, reason=COB: 26,3, Dev: 3,7, BGI: -0,2, ISF: 4,3, CR: 15,8, Target: 6,4, minPredBG 8,8, minGuardBG 8,1, IOBpredBG 5,2, COBpredBG 8,8, UAMpredBG 12,6; Eventual BG 12,6 >= 6,4,  insulinReq 0.55; setting 60m low temp of 0.0U/h. Waiting 3m 5s to microbolus again., duration=60, rate=0.0, predBGs=Predictions(IOB=[139, 145, 150], ZT=[139, 135], COB=[139, 145], aCOB=null, UAM=[139, 145]), COB=26.307844209291304, IOB=1.334, variable_sens=77.8, isfMgdlForCarbs=null, consoleLog=[], consoleError=[Autosens ratio: 1.0; , Basal unchanged: 0.7;, ISF unchanged: 86.4, CR: 15.8])
"""


# ============================================================
#  ОСНОВНОЙ ТЕСТ
# ============================================================

def main():
    if "Result: RT(" not in RT_LINE:
        print("RT(...) не найдено")
        return

    body = RT_LINE.split("Result: RT(", 1)[1].rsplit(")", 1)[0]

    # ----------- ПАРСИМ ЧИСЛА ИЗ RT -----------
    bg = num("bg", body)
    tick = num("tick", body, default=0)  # ← если tick нет → 0
    eventualBG = num("eventualBG", body)
    targetBG = num("targetBG", body)
    insulinReq = num("insulinReq", body)
    duration = int(num("duration", body, default=0))
    rate = num("rate", body)
    iob = num("IOB", body)
    cob = num("COB", body)
    variable_sens = num("variable_sens", body)

    # ----------- ПАРСИМ ИЗ consoleError -----------
    isf_mgdl = from_console(r"ISF unchanged: ([0-9.,]+)", body)
    cr = from_console(r"CR: ([0-9.,]+)", body)
    basal = from_console(r"Basal unchanged: ([0-9.,]+)", body)

    isf_mmol = (isf_mgdl / 18.0) if isf_mgdl else 6.0

    # ============================================================
    #  СОБИРАЕМ СТРУКТУРЫ AAPS
    # ============================================================

    glucose_status = GlucoseStatus(
        glucose=bg / 18.0,
        delta=tick / 18.0,
        short_avg_delta=tick / 18.0,
        long_avg_delta=tick / 36.0,
        date=0,
        noise=0
    )

    iob_data = IobTotal(
        iob=iob,
        activity=0.00023,
        iob_with_zero_temp=None
    )

    meal_data = MealData(
        carbs=0,
        meal_cob=cob,
        last_carb_time=0,
        slope_from_max_deviation=0.0,
        slope_from_min_deviation=0.0
    )

    autosens = AutosensResult(
        ratio=1.0,
        sens_result="Autosens ratio: 1.0"
    )

    current_temp = CurrentTemp(
        duration=0,
        rate=basal,
        minutes_running=0
    )

    profile = OapsProfileAutoIsf(
        min_bg=5.0,
        max_bg=7.8,
        target_bg=targetBG / 18.0,
        sens=isf_mmol,
        carb_ratio=cr,
        current_basal=basal,
        max_basal=3.0,
        max_daily_basal=2.0,
        max_iob=3.0,
        autosens_max=1.2,
        sensitivity_raises_target=False,
        resistance_lowers_target=False,
        adv_target_adjustments=True,
        enable_uam=True,
        exercise_mode=False,
        high_temptarget_raises_sensitivity=False,
        low_temptarget_lowers_sensitivity=False,
        half_basal_exercise_target=100,
        temptarget_set=False,
        remainingCarbsCap=90,
        maxSMBBasalMinutes=90,
        maxUAMSMBBasalMinutes=90,
        bolus_increment=0.1,
        skip_neutral_temps=False,
        enableSMB_always=False,
        enableSMB_with_COB=False,
        enableSMB_after_carbs=False,
        enableSMB_with_temptarget=False,
        allowSMB_with_high_temptarget=False,
        SMBInterval=5,
        smb_delivery_ratio=0.5,
        smb_delivery_ratio_min=0.5,
        smb_delivery_ratio_max=0.5,
        smb_delivery_ratio_bg_range=3.0,
        smb_max_range_extension=1.0,
        autoISF_version="3.0.1",
        variable_sens=variable_sens / 18.0
    )

    # ============================================================
    #  ЗАПУСК PYTHON‑АЛГОРИТМА
    # ============================================================

    rt = determine_basal_autoisf(
        glucose_status=glucose_status,
        currenttemp=current_temp,
        iob_data_array=[iob_data],
        profile=profile,
        autosens_data=autosens,
        meal_data=meal_data,
        microBolusAllowed=False,
        currentTime=0,
        flatBGsDetected=False,
        autoIsfMode=True,
        loop_wanted_smb="none",
        profile_percentage=100,
        smb_ratio=0.5,
        smb_max_range_extension=1.0,
        iob_threshold_percent=100,
        auto_isf_consoleError=[],
        auto_isf_consoleLog=[]
    )

    # ============================================================
    #  ВЫВОД СРАВНЕНИЯ
    # ============================================================

    print("\n=== EXPECTED (LOG) ===")
    print("eventualBG:", eventualBG / 18.0)
    print("targetBG  :", targetBG / 18.0)
    print("rate      :", rate)
    print("duration  :", duration)
    print("insulinReq:", insulinReq)

    print("\n=== PYTHON ===")
    print("eventualBG:", rt.eventualBG)
    print("targetBG  :", rt.targetBG)
    print("rate      :", rt.rate)
    print("duration  :", rt.duration)
    print("insulinReq:", rt.insulinReq)


if __name__ == "__main__":
    main()
