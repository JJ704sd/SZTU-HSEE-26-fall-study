# -*- coding: utf-8 -*-
"""依据实跑结果生成报告用图：图 1 逐句边界 F1 对照、图 2 训练过程与双向/单向消融。

数据来源：outputs/exp2_results.json（习题一逐句结果）与 outputs/exp2_train.json（训练记录）。
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = Path(__file__).resolve().parent
OUT = BASE / "outputs"
FIGS = BASE / "figs"
FIGS.mkdir(exist_ok=True)

for name in ("SimHei", "Microsoft YaHei"):
    if any(f.name == name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [name]
        break
plt.rcParams["axes.unicode_minus"] = False

BLUE = "#7FA8D0"
ORANGE = "#E8A87C"
RED = "#C0504D"


def fig1():
    """P01—P10 逐句边界 F1 对照。"""
    res = json.loads((OUT / "exp2_results.json").read_text(encoding="utf-8"))
    rows = res["习题一_P01到P10"]
    ids = [r["id"] for r in rows]
    base = [r["base_f1"] for r in rows]
    dic = [r["dict_f1"] for r in rows]

    fig, ax = plt.subplots(figsize=(11.6, 3.9), dpi=200)
    x = range(len(ids))
    w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], base, w, label="jieba 基线",
                color=BLUE, edgecolor="none")
    b2 = ax.bar([i + w / 2 for i in x], dic, w, label="加医学词典",
                color=ORANGE, edgecolor="none")
    for bars in (b1, b2):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.015,
                    f"{bar.get_height():.2f}", ha="center", va="bottom",
                    fontsize=6.6, color="#404040")
    ax.set_xticks(list(x))
    ax.set_xticklabels(ids, fontsize=9)
    ax.set_ylim(0, 1.18)
    ax.set_ylabel("句级边界 F1", fontsize=10)
    ax.grid(axis="y", color="#D0D0D0", linestyle=":", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#909090")
    ax.spines["bottom"].set_color("#909090")
    ax.tick_params(colors="#404040", labelsize=9)
    leg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.16), ncol=2,
                    frameon=False, fontsize=10)
    for t in leg.get_texts():
        t.set_color("#303030")
    fig.tight_layout()
    path = FIGS / "fig1_p01_p10_f1.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("图 1 ->", path)


def fig2():
    """训练过程（左：双向；右：单向消融）。"""
    tr = json.loads((OUT / "exp2_train.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.1), dpi=200)
    for ax, key, title in ((axes[0], "bidirectional", "(a) 双向 BiLSTM"),
                           (axes[1], "unidirectional", "(b) 单向 LSTM（消融）")):
        h = tr[key]["history"]
        ep = [x["epoch"] for x in h]
        tl = [x["train_loss"] for x in h]
        tf = [x["train_f1"] for x in h]
        vf = [x["val_f1"] for x in h]
        ax2 = ax.twinx()
        l1, = ax.plot(ep, tl, color=RED, linewidth=1.7, label="train_loss")
        l2, = ax2.plot(ep, tf, color="#2E5FA3", linewidth=1.7, label="train F1")
        l3, = ax2.plot(ep, vf, color="#C9A0A6", linewidth=1.7, linestyle="--",
                       label="val F1")
        ax.set_xlabel("epoch", fontsize=10)
        ax.set_ylabel("训练损失", fontsize=10, color=RED)
        ax2.set_ylabel("边界 F1", fontsize=10)
        ax.set_title(title, fontsize=11, color="#202020")
        ax.grid(color="#D0D0D0", linestyle=":", linewidth=0.8)
        ax.set_axisbelow(True)
        for s in ("top",):
            ax.spines[s].set_visible(False)
            ax2.spines[s].set_visible(False)
        ax.tick_params(labelsize=9)
        ax2.tick_params(labelsize=9)
        lines = [l1, l2, l3]
        leg = ax.legend(lines, [l.get_label() for l in lines],
                        loc="center right", fontsize=8.5, frameon=False)
        for t in leg.get_texts():
            t.set_color("#303030")
    fig.tight_layout()
    path = FIGS / "fig2_training_curves.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("图 2 ->", path)


if __name__ == "__main__":
    fig1()
    fig2()
