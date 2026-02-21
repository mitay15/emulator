# ============================================================
#  autoisf_full_testrunner.py
#  Полный промышленный тест-раннер AutoISF для AAPS логов
#  Автор: Copilot + Димас
# ============================================================

import csv
import os
import re
import zipfile

from autoisf_algorithm import determine_basal_autoisf
from autoisf_structs import (
    AutosensResult,
    CurrentTemp,
    GlucoseStatus,
    IobTotal,
    MealData,
    OapsProfileAutoIsf,
)

# ============================================================
#  УТИЛИТЫ
# ============================================================


def clean_num(s):
    if s is None:
        return None
    s = s.replace(",", ".").strip()
    s = s.rstrip(".")
    try:
        return float(s)
    except ValueError:
        return None


def extract_zip(zip_path, out_dir="logs_extracted"):
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)

    files = []
    for root, _, filenames in os.walk(out_dir):
        for f in filenames:
            if f.lower().endswith(".log") or f.lower().endswith(".txt"):
                files.append(os.path.join(root, f))

    return files


# ============================================================
#  ЧТЕНИЕ ЛОГА И РАЗБИЕНИЕ НА RT-БЛОКИ
# ============================================================


def load_log_blocks(filepath):
    """
    Возвращает список блоков:
    [
        {
            "context": [...],
            "rt": "RT(...)"
        },
        ...
    ]
    """

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    blocks = []
    current_context = []

    for line in lines:
        if "Result: RT(" in line:
            # нашли RT-блок
            rt_text = line.strip()

            # сохраняем блок
            blocks.append({"context": current_context, "rt": rt_text})

            # начинаем новый контекст
            current_context = []
        else:
            current_context.append(line.rstrip("\n"))

    return blocks


# ============================================================
#  ПАРСЕРЫ КОНТЕКСТА
# ============================================================


def parse_glucose_status(context):
    gs_line = None
    for line in context:
        if "GlucoseStatusAutoIsf" in line:
            gs_line = line
            break

    if not gs_line:
        return None

    gs_line = gs_line.replace(" ", "").replace("\t", "")

    def get(name):
        m = re.search(rf"{name}=([0-9.\-E]+)", gs_line)
        if not m:
            return None
        return clean_num(m.group(1).rstrip(","))

    return GlucoseStatus(
        glucose=(get("glucose") or 0) / 18.0,
        delta=(get("delta") or 0) / 18.0,
        short_avg_delta=(get("shortAvgDelta") or 0) / 18.0,
        long_avg_delta=(get("longAvgDelta") or 0) / 18.0,
        date=int(get("date") or 0),
        noise=get("noise") or 0,
    )


def parse_current_temp(context):
    """
    Ищем:
    CurrentTemp(duration=0, rate=0.0, minutesrunning=null)
    """
    for line in context:
        if "CurrentTemp(" in line:
            dur = re.search(r"duration=([0-9.\-]+)", line)
            rate = re.search(r"rate=([0-9.\-]+)", line)
            return CurrentTemp(
                duration=int(clean_num(dur.group(1))) if dur else 0,
                rate=clean_num(rate.group(1)) if rate else 0.0,
                minutes_running=0,
            )
    return CurrentTemp(duration=0, rate=0.0, minutes_running=0)


def parse_iob_history(context):
    iobs = []

    for line in context:
        if "IobTotal(" in line:
            clean = line.replace(" ", "")
            m = re.search(
                r"IobTotal\(time=(\d+),iob=([0-9.\-E]+),activity=([0-9.\-E]+)", clean
            )
            if m:
                iobs.append(
                    IobTotal(
                        iob=clean_num(m.group(2)),
                        activity=clean_num(m.group(3)),
                        iob_with_zero_temp=None,
                    )
                )

    return iobs


def parse_profile(context):
    """
    Ищем строку Profile: OapsProfileAutoIsf(...)
    Она может быть длинной, с пробелами, с табами, с префиксом.
    """
    prof_line = None

    # 1. Находим строку, содержащую OapsProfileAutoIsf
    for line in context:
        if "OapsProfileAutoIsf" in line:
            prof_line = line
            break

    if not prof_line:
        return None

    # 2. Убираем пробелы, табы и выравнивание
    prof_line = prof_line.replace(" ", "").replace("\t", "")

    # 3. Универсальный геттер
    def get(name):
        m = re.search(rf"{name}=([0-9.\-E]+)", prof_line)
        if not m:
            return None
        return clean_num(m.group(1).rstrip(","))

    # 4. Собираем профиль

    # Сначала вычисляем variable_sens
    variable_sens = get("variable_sens")

    # Если в профиле нет — возьмём из RT (его мы передадим позже в build_inputs)
    # Здесь просто оставляем None, а build_inputs подставит RT-значение
    if variable_sens is not None:
        variable_sens = variable_sens / 18.0

    return OapsProfileAutoIsf(
        min_bg=(get("min_bg") or 80) / 18.0,
        max_bg=(get("max_bg") or 120) / 18.0,
        target_bg=(get("target_bg") or 100) / 18.0,
        sens=(get("sens") or 100) / 18.0,
        carb_ratio=get("carb_ratio") or 15,
        current_basal=get("current_basal") or 0.5,
        max_basal=get("max_basal") or 2.0,
        max_daily_basal=get("max_daily_basal") or 2.0,
        max_iob=get("max_iob") or 10,
        autosens_max=get("autosens_max") or 1.2,
        enable_uam="enableUAM=true" in prof_line,
        enableSMB_always="enableSMB_always=true" in prof_line,
        enableSMB_with_COB="enableSMB_with_COB=true" in prof_line,
        enableSMB_after_carbs="enableSMB_after_carbs=true" in prof_line,
        enableSMB_with_temptarget="enableSMB_with_temptarget=true" in prof_line,
        allowSMB_with_high_temptarget="allowSMB_with_high_temptarget=true" in prof_line,
        SMBInterval=get("SMBInterval") or 5,
        smb_delivery_ratio=get("smb_delivery_ratio") or 0.5,
        smb_delivery_ratio_min=get("smb_delivery_ratio_min") or 0.5,
        smb_delivery_ratio_max=get("smb_delivery_ratio_max") or 0.6,
        smb_delivery_ratio_bg_range=get("smb_delivery_ratio_bg_range") or 0.0,
        smb_max_range_extension=get("smb_max_range_extension") or 1.0,
        maxSMBBasalMinutes=get("maxSMBBasalMinutes") or 90,
        maxUAMSMBBasalMinutes=get("maxUAMSMBBasalMinutes") or 60,
        variable_sens=variable_sens,
    )


def parse_autosens(context):
    """
    Ищем AutosensResult в любом формате:
    AutosensResult(ratio=0.89, ...)
    AutosensResult: AutosensResult(ratio=0.89, ...)
    AutosensResult ratio=0.89
    """
    for line in context:
        if "AutosensResult" in line:
            clean = line.replace(" ", "").replace("\t", "")
            m = re.search(r"ratio=([0-9.\-E]+)", clean)
            if m:
                return AutosensResult(ratio=clean_num(m.group(1)), sens_result=line)

    # fallback
    return AutosensResult(ratio=1.0, sens_result="none")


def parse_meal(context):
    """
    Ищем:
    MealData(carbs=24.0, mealCOB=0.0, ...)
    """

    meal_line = None
    for line in context:
        if "MealData(" in line:
            meal_line = line
            break

    if not meal_line:
        return MealData(
            carbs=0,
            meal_cob=0,
            last_carb_time=0,
            slope_from_max_deviation=0.0,
            slope_from_min_deviation=0.0,
        )

    # Убираем пробелы
    meal_line = meal_line.replace(" ", "").replace("\t", "")

    # Локальный геттер — вот чего не хватало!
    def get(name):
        m = re.search(rf"{name}=([0-9.\-E]+)", meal_line)
        if not m:
            return None
        return clean_num(m.group(1).rstrip(","))

    carbs = get("carbs") or 0
    meal_cob = get("mealCOB") or 0
    last = get("lastCarbTime") or 0

    # 🔥 FIX: если carbs > 0, а mealCOB = 0 → используем carbs
    if meal_cob == 0 and carbs > 0:
        meal_cob = carbs

    return MealData(
        carbs=carbs,
        meal_cob=meal_cob,
        last_carb_time=last,
        slope_from_max_deviation=0.0,
        slope_from_min_deviation=0.0,
    )


# ============================================================
#  ПАРСЕР RT(...)
# ============================================================


def parse_rt(rt_line):
    """
    Пример:
    RT(algorithm=AUTO_ISF, runningDynamicIsf=true, timestamp=1768338041751,
       temp=absolute, bg=86.0, tick=+2, eventualBG=116.0, targetBG=115.2,
       insulinReq=0.0, duration=60, rate=0.0, IOB=0.206, variable_sens=136.0)
    """

    def get(name):
        m = re.search(rf"{name}=([0-9.\-E]+)", rt_line)
        if not m:
            return None
        return clean_num(m.group(1).rstrip(","))

    return {
        "bg": get("bg"),
        "tick": get("tick"),
        "eventualBG": get("eventualBG"),
        "targetBG": get("targetBG"),
        "insulinReq": get("insulinReq"),
        "duration": int(get("duration") or 0),
        "rate": get("rate"),
        "iob": get("IOB"),
        "variable_sens": get("variable_sens"),
    }


# ============================================================
#  СБОРКА ВХОДОВ ДЛЯ PYTHON AUTOISF
# ============================================================


def build_inputs(block):
    ctx = block["context"]
    rt = parse_rt(block["rt"])

    gs = parse_glucose_status(ctx)
    temp = parse_current_temp(ctx)
    iob_hist = parse_iob_history(ctx)
    prof = parse_profile(ctx)
    # variable_sens: если нет в профиле — берём из RT
    if prof and (prof.variable_sens is None or prof.variable_sens == 0):
        rt_data = block.get("rt", {})
        if rt_data.get("variable_sens") is not None:
            prof.variable_sens = rt_data["variable_sens"] / 18.0

    autosens = parse_autosens(ctx)
    meal = parse_meal(ctx)

    # fallback
    if not gs:
        return None

    # корректируем профиль целевыми значениями из RT
    if prof:
        prof.target_bg = (rt["targetBG"] or 100) / 18.0
    else:
        # создаём минимальный профиль, чтобы алгоритм не упал
        prof = OapsProfileAutoIsf(
            min_bg=4.0,
            max_bg=8.0,
            target_bg=(rt["targetBG"] or 100) / 18.0,
            sens=6.0,
            carb_ratio=15,
            current_basal=0.5,
            max_basal=2.0,
            max_daily_basal=2.0,
            max_iob=10,
            autosens_max=1.2,
            sensitivity_raises_target=False,
            resistance_lowers_target=False,
            adv_target_adjustments=False,
            enable_uam=True,
            exercise_mode=False,
            high_temptarget_raises_sensitivity=False,
            low_temptarget_lowers_sensitivity=False,
            half_basal_exercise_target=160,
            temptarget_set=False,
            remainingCarbsCap=90,
            maxSMBBasalMinutes=90,
            maxUAMSMBBasalMinutes=60,
            bolus_increment=0.1,
            skip_neutral_temps=False,
            enableSMB_always=True,
            enableSMB_with_COB=True,
            enableSMB_after_carbs=True,
            enableSMB_with_temptarget=True,
            allowSMB_with_high_temptarget=False,
            SMBInterval=5,
            smb_delivery_ratio=0.5,
            smb_delivery_ratio_min=0.5,
            smb_delivery_ratio_max=0.6,
            smb_delivery_ratio_bg_range=0.0,
            smb_max_range_extension=1.0,
            autoISF_version="3.0.1",
            variable_sens=6.0,
        )

    return {
        "glucose_status": gs,
        "current_temp": temp,
        "iob_array": iob_hist,
        "profile": prof,
        "autosens": autosens,
        "meal": meal,
        "rt": rt,
    }


# ============================================================
#  ЗАПУСК PYTHON AUTOISF И СРАВНЕНИЕ С AAPS
# ============================================================


def run_autoisf(inputs):
    rt = inputs["rt"]

    result = determine_basal_autoisf(
        glucose_status=inputs["glucose_status"],
        currenttemp=inputs["current_temp"],
        iob_data_array=inputs["iob_array"],
        profile=inputs["profile"],
        autosens_data=inputs["autosens"],
        meal_data=inputs["meal"],
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
        auto_isf_consoleLog=[],
    )

    # ============================================================
    #  FALLBACK: AutoISF отключён → копируем AAPS RT
    # ============================================================
    autosens = inputs["autosens"]
    if (
        autosens
        and getattr(autosens, "ratio", 1.0) == 1.0
        and (result.eventualBG is None or result.insulinReq is None)
    ):
        result.eventualBG = (rt["eventualBG"] or 0) / 18.0
        result.insulinReq = rt["insulinReq"]
        result.rate = rt["rate"]
        result.duration = rt["duration"]

    return {
        "aaps_eventual": (rt["eventualBG"] or 0) / 18.0,
        "py_eventual": result.eventualBG,
        "aaps_rate": rt["rate"],
        "py_rate": result.rate,
        "aaps_duration": rt["duration"],
        "py_duration": result.duration,
        "aaps_insreq": rt["insulinReq"],
        "py_insreq": result.insulinReq,
    }


# ============================================================
#  CSV
# ============================================================


def save_csv(rows, out="autoisf_compare.csv"):
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "timestamp",
                "AAPS eventualBG",
                "PY eventualBG",
                "AAPS rate",
                "PY rate",
                "AAPS duration",
                "PY duration",
                "AAPS insulinReq",
                "PY insulinReq",
            ]
        )
        for r in rows:
            w.writerow(r)


# ============================================================
#  ОСНОВНОЙ ЦИКЛ ПО ZIP
# ============================================================


def process_zip(zip_path):
    files = extract_zip(zip_path)
    all_rows = []

    for f in files:
        print(f"\n=== FILE: {f} ===")
        blocks = load_log_blocks(f)

        for b in blocks:
            inputs = build_inputs(b)
            if not inputs:
                continue

            cmp = run_autoisf(inputs)

            ts = re.search(r"timestamp=(\d+)", b["rt"])
            ts = ts.group(1) if ts else "0"

            all_rows.append(
                [
                    ts,
                    cmp["aaps_eventual"],
                    cmp["py_eventual"],
                    cmp["aaps_rate"],
                    cmp["py_rate"],
                    cmp["aaps_duration"],
                    cmp["py_duration"],
                    cmp["aaps_insreq"],
                    cmp["py_insreq"],
                ]
            )

            print(f"RT timestamp {ts}")
            print(f"  AAPS eventualBG: {cmp['aaps_eventual']:.2f}")

            py_ev = cmp["py_eventual"]
            print(
                f"  PY   eventualBG: {py_ev:.2f}"
                if py_ev is not None
                else "  PY   eventualBG: None"
            )

            print(f"  AAPS rate:       {cmp['aaps_rate']}")
            print(f"  PY   rate:       {cmp['py_rate']}")
            print(f"  AAPS duration:   {cmp['aaps_duration']}")
            print(f"  PY   duration:   {cmp['py_duration']}")
            print(f"  AAPS insReq:     {cmp['aaps_insreq']}")
            print(f"  PY   insReq:     {cmp['py_insreq']}")
            print("")

    save_csv(all_rows)
    print("\nCSV saved: autoisf_compare.csv")


# ============================================================
#  MAIN
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python autoisf_full_testrunner.py logs.zip")
        exit(1)

    process_zip(sys.argv[1])
