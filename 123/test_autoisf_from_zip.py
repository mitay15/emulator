import zipfile
import re
from autoisf_structs import *
from autoisf_algorithm import determine_basal_autoisf


# ============================================================
# 1. НАХОДИМ ZIP В ПАПКЕ data/
# ============================================================

ZIP_PATH = "data/aaps_logs.zip"   # ← поменяй на свой ZIP


# ============================================================
# 2. ЧИТАЕМ ЛОГ ИЗ ZIP
# ============================================================

def read_log_from_zip(zip_path):
    with zipfile.ZipFile(zip_path, "r") as z:
        for name in z.namelist():
            if name.endswith(".log") or name.endswith(".txt"):
                print(f"Используем лог: {name}")
                with z.open(name) as f:
                    return f.read().decode("utf-8", errors="ignore")
    raise FileNotFoundError("В ZIP нет логов .log или .txt")


log_text = read_log_from_zip(ZIP_PATH)


# ============================================================
# 3. ИЗВЛЕКАЕМ ДАННЫЕ ИЗ ЛОГА
# ============================================================

def extract(pattern, text, default=None, cast=float):
    m = re.search(pattern, text)
    if not m:
        return default
    return cast(m.group(1))


bg = extract(r"bg=(\d+\.?\d*)", log_text)
delta = extract(r"tick=\+?(-?\d+)", log_text)
eventualBG = extract(r"eventualBG=(\d+\.?\d*)", log_text)
targetBG = extract(r"targetBG=(\d+\.?\d*)", log_text)
iob = extract(r"IOB=([0-9.]+)", log_text)
activity = extract(r"activity=([0-9.]+)", log_text)
sens = extract(r"ISF: ([0-9.,]+)", log_text, cast=lambda x: float(x.replace(",", ".")))
cr = extract(r"CR: ([0-9.]+)", log_text)
basal = extract(r"current basal of ([0-9.]+)", log_text, default=0.5)
duration = extract(r"duration=(\d+)", log_text, cast=int)
rate = extract(r"rate=([0-9.]+)", log_text)

print("\n=== ИЗВЛЕЧЁННЫЕ ДАННЫЕ ===")
print("BG:", bg)
print("delta:", delta)
print("eventualBG:", eventualBG)
print("targetBG:", targetBG)
print("IOB:", iob)
print("activity:", activity)
print("ISF:", sens)
print("CR:", cr)
print("basal:", basal)
print("duration:", duration)
print("rate:", rate)


# ============================================================
# 4. СОЗДАЁМ ОБЪЕКТЫ ДЛЯ PYTHON‑АЛГОРИТМА
# ============================================================

glucose_status = GlucoseStatus(
    glucose=bg / 18,
    delta=delta / 18,
    short_avg_delta=delta / 18,
    long_avg_delta=delta / 18,
    date=0,
    noise=0
)

iob_data = IobTotal(
    iob=iob,
    activity=activity,
    iob_with_zero_temp=None
)

meal_data = MealData(
    carbs=0,
    meal_cob=0,
    last_carb_time=0,
    slope_from_max_deviation=0,
    slope_from_min_deviation=0
)

autosens = AutosensResult(
    ratio=1.0,
    sens_result=""
)

current_temp = CurrentTemp(
    duration=0,
    rate=basal,
    minutes_running=0
)

profile = OapsProfileAutoIsf(
    min_bg=5.0,
    max_bg=7.8,
    target_bg=targetBG / 18,
    sens=sens / 18,
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
    maxSMBBasalMinutes=30,
    maxUAMSMBBasalMinutes=30,
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
    variable_sens=136/18
)


# ============================================================
# 5. ЗАПУСКАЕМ PYTHON‑АЛГОРИТМ
# ============================================================

result = determine_basal_autoisf(
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
# 6. СРАВНИВАЕМ С ЛОГОМ
# ============================================================

print("\n=== PYTHON RESULT ===")
print("duration:", result.duration)
print("rate:", result.rate)
print("eventualBG:", result.eventualBG)
print("targetBG:", result.targetBG)

print("\n=== EXPECTED (FROM LOG) ===")
print("duration:", duration)
print("rate:", rate)
print("eventualBG:", eventualBG / 18)
print("targetBG:", targetBG / 18)

print("\n=== DIFFERENCE ===")
print("duration:", result.duration - duration)
print("rate:", result.rate - rate)
print("eventualBG:", result.eventualBG - (eventualBG / 18))
print("targetBG:", result.targetBG - (targetBG / 18))
