# tools/diff_report.py
from pathlib import Path

import numpy as np
import pandas as pd

CRIT_BG = 10  # critical difference for eventualBG
CRIT_INSULIN = 0.20  # critical difference for insulinReq
CRIT_RATE = 0.20  # critical difference for basal rate


def load(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    # keep only rows where AAPS actually ran AutoISF
    if "aaps_eventual_bg" in df.columns:
        df = df[df["aaps_eventual_bg"].notna()]

    # create diffs (guard missing columns)
    if "eventual_bg" in df.columns and "aaps_eventual_bg" in df.columns:
        df["diff_eventual_bg"] = df["eventual_bg"] - df["aaps_eventual_bg"]
    else:
        df["diff_eventual_bg"] = np.nan

    if "insulin_req" in df.columns and "aaps_insulin_req" in df.columns:
        df["diff_insulin_req"] = df["insulin_req"] - df["aaps_insulin_req"]
    else:
        df["diff_insulin_req"] = np.nan

    if "rate" in df.columns and "aaps_rate" in df.columns:
        df["diff_rate"] = df["rate"] - df["aaps_rate"]
    else:
        df["diff_rate"] = np.nan

    # absolute values
    df["abs_diff_eventual_bg"] = df["diff_eventual_bg"].abs()
    df["abs_diff_insulin_req"] = df["diff_insulin_req"].abs()
    df["abs_diff_rate"] = df["diff_rate"].abs()

    return df


# -----------------------------
# 1. Summary
# -----------------------------
def summary(df: pd.DataFrame):
    print("\n==============================")
    print("📊 SUMMARY OF DIFFERENCES")
    print("==============================")

    for col in ["abs_diff_eventual_bg", "abs_diff_insulin_req", "abs_diff_rate"]:
        if col in df.columns:
            print(f"\n{col}:")
            print(f"  mean = {df[col].mean():.4f}")
            print(f"  median = {df[col].median():.4f}")
            print(f"  max = {df[col].max():.4f}")
            print(f"  95th percentile = {df[col].quantile(0.95):.4f}")


# -----------------------------
# 2. Critical differences
# -----------------------------
def critical(df: pd.DataFrame):
    print("\n==============================")
    print("🚨 CRITICAL DIFFERENCES")
    print("==============================")

    crit = df[
        (df["abs_diff_eventual_bg"] > CRIT_BG)
        | (df["abs_diff_insulin_req"] > CRIT_INSULIN)
        | (df["abs_diff_rate"] > CRIT_RATE)
    ]

    print(f"\nTotal critical blocks: {len(crit)}")

    if len(crit) > 0:
        cols = [
            "datetime",
            "bg",
            "eventual_bg",
            "aaps_eventual_bg",
            "diff_eventual_bg",
            "insulin_req",
            "aaps_insulin_req",
            "diff_insulin_req",
            "rate",
            "aaps_rate",
            "diff_rate",
        ]
        existing = [c for c in cols if c in crit.columns]
        print("\nTop-20 critical:")
        print(
            crit.sort_values("abs_diff_eventual_bg", ascending=False)
            .head(20)[existing]
            .to_string(index=False)
        )


# -----------------------------
# 3. Zones by BG
# -----------------------------
def zones(df: pd.DataFrame):
    print("\n==============================")
    print("📈 REPORTS BY BG ZONES")
    print("==============================")

    if "bg" not in df.columns:
        print("No 'bg' column in dataframe")
        return

    zones = {
        "Low (<80)": df[df["bg"] < 80],
        "Normal (80–140)": df[(df["bg"] >= 80) & (df["bg"] <= 140)],
        "High (140–180)": df[(df["bg"] > 140) & (df["bg"] <= 180)],
        "Very High (>180)": df[df["bg"] > 180],
    }

    for name, z in zones.items():
        print(f"\n--- {name} ---")
        print(f"Blocks count: {len(z)}")
        if len(z) == 0:
            continue
        for col in ["abs_diff_eventual_bg", "abs_diff_insulin_req", "abs_diff_rate"]:
            if col in z.columns:
                print(f"Mean {col} = {z[col].mean():.3f}")


# -----------------------------
# 4. Temp basal / SMB filter
# -----------------------------
def temp_smb(df: pd.DataFrame):
    print("\n==============================")
    print("⚙️ TEMP BASAL / SMB")
    print("==============================")

    if "duration" in df.columns:
        temp = df[df["duration"] > 0]
    else:
        temp = pd.DataFrame()

    if "smb" in df.columns:
        smb = df[df["smb"].notna() & (df["smb"] > 0)]
    else:
        smb = pd.DataFrame()

    print(f"\nTemp basal active: {len(temp)} blocks")
    if len(temp) > 0 and "abs_diff_rate" in temp.columns:
        print(f"Mean |diff_rate| = {temp['abs_diff_rate'].mean():.3f}")

    print(f"\nSMB active: {len(smb)} blocks")
    if len(smb) > 0 and "abs_diff_insulin_req" in smb.columns:
        print(f"Mean |diff_insulin_req| = {smb['abs_diff_insulin_req'].mean():.3f}")


# -----------------------------
# 5. Top errors
# -----------------------------
def top_errors(df: pd.DataFrame):
    print("\n==============================")
    print("🏆 TOP-20 ERRORS")
    print("==============================")

    if "abs_diff_eventual_bg" not in df.columns:
        print("No error column found")
        return

    top = df.sort_values("abs_diff_eventual_bg", ascending=False).head(20)
    cols = [
        "datetime",
        "bg",
        "eventual_bg",
        "aaps_eventual_bg",
        "diff_eventual_bg",
        "insulin_req",
        "aaps_insulin_req",
        "diff_insulin_req",
        "rate",
        "aaps_rate",
        "diff_rate",
    ]
    existing = [c for c in cols if c in top.columns]
    print(top[existing].to_string(index=False))


# -----------------------------
# MAIN
# -----------------------------
def analyze(csv_path: Path):
    df = load(csv_path)

    summary(df)
    critical(df)
    zones(df)
    temp_smb(df)
    top_errors(df)


if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[2]
    DATA = ROOT / "data"
    csv_path = DATA / "reports" / "autoisf_results.csv"

    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
    else:
        analyze(csv_path)
