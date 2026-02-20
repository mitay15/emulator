import matplotlib.pyplot as plt


def plot_bg(cycles):
    bg = [c["glucose"]["glucose"] for c in cycles if c.get("glucose")]
    if not bg:
        return
    plt.figure()
    plt.plot(bg, marker="o")
    plt.title("BG по циклам")
    plt.xlabel("Цикл")
    plt.ylabel("BG")
    plt.grid(True)


def plot_isf(cycles):
    isf = [c["profile"]["sens"] for c in cycles if c.get("profile")]
    if not isf:
        return
    plt.figure()
    plt.plot(isf, marker="o")
    plt.title("ISF по циклам")
    plt.xlabel("Цикл")
    plt.ylabel("ISF")
    plt.grid(True)


def plot_insulin_req(cycles):
    ins = [c["suggested"]["insulinReq"] for c in cycles if c.get("suggested")]
    if not ins:
        return
    plt.figure()
    plt.plot(ins, marker="o")
    plt.title("InsulinReq по циклам")
    plt.xlabel("Цикл")
    plt.ylabel("InsulinReq")
    plt.grid(True)


def plot_predicted_bg(cycles):
    for idx, c in enumerate(cycles):
        result = c.get("result") or {}
        pred = result.get("predBGs")
        if not pred:
            continue

        plt.figure(figsize=(10, 4))
        if "IOB" in pred:
            plt.plot(pred["IOB"], label="IOB")
        if "ZT" in pred:
            plt.plot(pred["ZT"], label="ZeroTemp")
        if "UAM" in pred:
            plt.plot(pred["UAM"], label="UAM")

        plt.title(f"Predicted BGs — Cycle {idx}")
        plt.xlabel("Шаг")
        plt.ylabel("BG")
        plt.legend()
        plt.grid(True)


def show_all():
    plt.show()
