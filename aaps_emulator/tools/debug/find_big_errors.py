# aaps_emulator/tools/debug/find_big_errors.py
"""
Найти строки с большими расхождениями по insulinReq и rate.

Пример запуска:
  python -m aaps_emulator.tools.debug.find_big_errors --csv aaps_emulator/logs/autoisf_diffs.csv
"""

import argparse

import pandas as pd


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--csv",
        required=True,
        help="Путь к CSV/TSV с колонками: idx, aaps_insreq_ref, py_insreq, err_ins, aaps_rate_ref, py_rate, err_rate",
    )
    p.add_argument(
        "--threshold_ins",
        type=float,
        default=0.5,
        help="Порог по |err_ins| для вывода (по умолчанию 0.5 U)",
    )
    p.add_argument(
        "--threshold_rate",
        type=float,
        default=0.5,
        help="Порог по |err_rate| для вывода (по умолчанию 0.5 U/h)",
    )
    args = p.parse_args()

    # читаем как whitespace‑разделённый или CSV — pandas сам поймёт
    df = pd.read_csv(args.csv, sep=None, engine="python")

    # если нет err_ins / err_rate — пытаемся вычислить
    if "err_ins" not in df.columns and {"aaps_insreq_ref", "py_insreq"} <= set(df.columns):
        df["err_ins"] = df["py_insreq"] - df["aaps_insreq_ref"]

    if "err_rate" not in df.columns and {"aaps_rate_ref", "py_rate"} <= set(df.columns):
        df["err_rate"] = df["py_rate"] - df["aaps_rate_ref"]

    cols_needed = [
        "idx",
        "aaps_insreq_ref",
        "py_insreq",
        "err_ins",
        "aaps_rate_ref",
        "py_rate",
        "err_rate",
    ]
    missing = [c for c in cols_needed if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing columns in {args.csv}: {missing}")

    mask = (df["err_ins"].abs() > args.threshold_ins) | (df["err_rate"].abs() > args.threshold_rate)

    bad = df.loc[mask, cols_needed].copy()

    if bad.empty:
        print("Нет строк с ошибками выше порогов.")
        return

    print("Строки с большими расхождениями (отсортированы по |err_ins|, затем по |err_rate|):")
    bad["abs_err_ins"] = bad["err_ins"].abs()
    bad["abs_err_rate"] = bad["err_rate"].abs()
    bad = bad.sort_values(["abs_err_ins", "abs_err_rate"], ascending=False)

    print(bad.to_string(index=False))


if __name__ == "__main__":
    main()
