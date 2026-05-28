#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Figure 10: Confusion matrices (raw counts only, 3 tasks).

This script intentionally uses only known confusion-matrix counts and does NOT
read S13_classification_reports_Z1_Z4.xlsx or generate any Figure 9 outputs.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUTPUT_DIR = Path(r"E:\Barrel_SEM_Z1_Z4_New\07_figures_main")

TASK1 = {
    "name": "Zone classification",
    "panel": "(a)",
    "labels": ["Z1", "Z2", "Z3", "Z4"],
    "counts": np.array([[11, 5, 8, 8], [5, 12, 14, 1], [1, 11, 5, 15], [0, 3, 1, 28]], dtype=int),
}

TASK2_BASE_LABELS = ["High damage", "Low damage", "Medium damage"]
TASK2_BASE_COUNTS = np.array([[29, 0, 3], [8, 10, 14], [15, 1, 48]], dtype=int)
TASK2_REORDER = [1, 2, 0]  # Low, Medium, High
TASK2 = {
    "name": "Damage severity classification",
    "panel": "(b)",
    "labels": [TASK2_BASE_LABELS[i] for i in TASK2_REORDER],
    "counts": TASK2_BASE_COUNTS[np.ix_(TASK2_REORDER, TASK2_REORDER)],
}

TASK3 = {
    "name": "Failure mode classification",
    "panel": "(c)",
    "labels": ["Cracking-related", "Severe mixed", "Wear-dominated"],
    "counts": np.array([[4, 8, 0], [0, 67, 3], [0, 1, 41]], dtype=int),
}

TASKS = [TASK1, TASK2, TASK3]


def format_matrix_for_summary(matrix: np.ndarray) -> str:
    lines = ["[" + ", ".join(str(int(v)) for v in row) + "]" for row in matrix]
    return "[\n  " + "\n  ".join(lines) + "\n]"


def draw_task_confusion(ax, counts: np.ndarray, labels, title: str):
    im = ax.imshow(counts, cmap="Blues", aspect="equal")
    vmax = float(np.max(counts))

    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=0, ha="center")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(title)

    ax.set_xticks(np.arange(-0.5, len(labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(labels), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)

    threshold = vmax * 0.5 if vmax > 0 else 0
    for i in range(counts.shape[0]):
        for j in range(counts.shape[1]):
            value = int(counts[i, j])
            text_color = "white" if value > threshold else "black"
            ax.text(j, i, f"{value}", ha="center", va="center", color=text_color, fontsize=10)

    return im


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    mpl.rcParams["figure.facecolor"] = "white"
    mpl.rcParams["axes.facecolor"] = "white"
    mpl.rcParams["font.family"] = "sans-serif"
    mpl.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5), constrained_layout=True)

    last_im = None
    for ax, task in zip(axes, TASKS):
        last_im = draw_task_confusion(ax, task["counts"], task["labels"], f"{task['panel']} {task['name']}")

    cbar = fig.colorbar(last_im, ax=axes, shrink=0.9, pad=0.02)
    cbar.set_label("Count")

    png_path = OUTPUT_DIR / "Figure_10_normalized_confusion_matrices.png"
    tif_path = OUTPUT_DIR / "Figure_10_normalized_confusion_matrices.tif"
    pdf_path = OUTPUT_DIR / "Figure_10_normalized_confusion_matrices.pdf"

    png_path_alt = OUTPUT_DIR / "Figure_10_confusion_matrices.png"
    tif_path_alt = OUTPUT_DIR / "Figure_10_confusion_matrices.tif"
    pdf_path_alt = OUTPUT_DIR / "Figure_10_confusion_matrices.pdf"

    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    fig.savefig(tif_path, dpi=600, bbox_inches="tight")
    fig.savefig(pdf_path, dpi=600, bbox_inches="tight")
    fig.savefig(png_path_alt, dpi=600, bbox_inches="tight")
    fig.savefig(tif_path_alt, dpi=600, bbox_inches="tight")
    fig.savefig(pdf_path_alt, dpi=600, bbox_inches="tight")
    plt.close(fig)

    xlsx_path = OUTPUT_DIR / "Figure10_normalized_confusion_matrices.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for i, task in enumerate(TASKS, start=1):
            df = pd.DataFrame(task["counts"], index=task["labels"], columns=task["labels"])
            df.to_excel(writer, sheet_name=f"Task{i}_counts")

    txt_path = OUTPUT_DIR / "Figure10_confusion_matrix_summary.txt"
    lines = [
        "Figure 10 confusion matrix summary",
        "=" * 40,
        "Data source: known confusion-matrix counts from previous model outputs",
        "This version displays raw confusion-matrix counts rather than row-normalized percentages.",
        "",
    ]

    for idx, task in enumerate(TASKS, start=1):
        lines.append(f"Task {idx}: {task['name']}")
        lines.append(f"Label order: {task['labels']}")
        lines.append("Raw count matrix:")
        lines.append(format_matrix_for_summary(task["counts"]))
        lines.append("")

    lines.append(
        "Task 2 reordering note: rows and columns were both reordered by index [1, 2, 0], resulting in label order Low damage -> Medium damage -> High damage."
    )

    txt_path.write_text("\n".join(lines), encoding="utf-8")

    print("Saved:")
    print(str(png_path))
    print(str(tif_path))
    print(str(pdf_path))
    print(str(png_path_alt))
    print(str(tif_path_alt))
    print(str(pdf_path_alt))
    print(str(xlsx_path))
    print(str(txt_path))


if __name__ == "__main__":
    main()
