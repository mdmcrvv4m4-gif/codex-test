#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Figure 10: Row-normalized confusion matrices (3 tasks).

This script intentionally uses only known confusion-matrix counts and does NOT
read S13_classification_reports_Z1_Z4.xlsx or generate any Figure 9 outputs.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt


# -----------------------------
# Output directory (requested)
# -----------------------------
OUTPUT_DIR = Path(r"E:\Barrel_SEM_Z1_Z4_New\07_figures_main")


# -----------------------------
# Known confusion-matrix counts
# -----------------------------
TASKS = [
    {
        "name": "Zone classification",
        "panel": "(a)",
        "labels": ["Z1", "Z2", "Z3", "Z4"],
        "counts": np.array(
            [
                [11, 5, 8, 8],
                [5, 12, 14, 1],
                [1, 11, 5, 15],
                [0, 3, 1, 28],
            ],
            dtype=int,
        ),
        "sheet_counts": "Task1_counts",
        "sheet_percent": "Task1_percent",
    },
    {
        "name": "Damage severity classification",
        "panel": "(b)",
        "labels": ["High damage", "Low damage", "Medium damage"],
        "counts": np.array(
            [
                [29, 0, 3],
                [8, 10, 14],
                [15, 1, 48],
            ],
            dtype=int,
        ),
        "sheet_counts": "Task2_counts",
        "sheet_percent": "Task2_percent",
    },
    {
        "name": "Failure mode classification",
        "panel": "(c)",
        "labels": ["Cracking-related", "Severe mixed", "Wear-dominated"],
        "counts": np.array(
            [
                [4, 8, 0],
                [0, 67, 3],
                [0, 1, 41],
            ],
            dtype=int,
        ),
        "sheet_counts": "Task3_counts",
        "sheet_percent": "Task3_percent",
    },
]


def row_normalize_percent(counts: np.ndarray) -> np.ndarray:
    """Row-normalize to percentages: count / row_sum * 100."""
    row_sums = counts.sum(axis=1, keepdims=True)
    if np.any(row_sums == 0):
        raise ValueError("Found a row with zero total; cannot row-normalize.")
    return counts / row_sums * 100.0


def format_matrix_for_summary(matrix: np.ndarray, decimals: int = 1) -> str:
    """Compact multi-line matrix formatting for text summary."""
    lines = []
    for row in matrix:
        if np.issubdtype(matrix.dtype, np.integer):
            row_text = ", ".join(str(int(v)) for v in row)
        else:
            row_text = ", ".join(f"{v:.{decimals}f}" for v in row)
        lines.append(f"[{row_text}]")
    return "[\n  " + "\n  ".join(lines) + "\n]"


def draw_task_confusion(ax, counts: np.ndarray, percents: np.ndarray, labels, title: str):
    """Draw one row-normalized confusion matrix subplot."""
    im = ax.imshow(percents, cmap="Blues", vmin=0, vmax=100, aspect="equal")

    ax.set_xticks(np.arange(len(labels)))
    ax.set_yticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_yticklabels(labels)
    ax.set_xlabel("Predicted label")
    ax.set_ylabel("True label")
    ax.set_title(title)

    # Grid lines between cells
    ax.set_xticks(np.arange(-0.5, len(labels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(labels), 1), minor=True)
    ax.grid(which="minor", color="white", linestyle="-", linewidth=1.2)
    ax.tick_params(which="minor", bottom=False, left=False)

    # Annotate each cell: percent (1 decimal) and count in parentheses
    for i in range(percents.shape[0]):
        for j in range(percents.shape[1]):
            p = percents[i, j]
            c = counts[i, j]
            text_color = "white" if p >= 50 else "black"
            ax.text(
                j,
                i,
                f"{p:.1f}%\n({c})",
                ha="center",
                va="center",
                color=text_color,
                fontsize=9,
            )

    return im


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Style: white background + Arial (fallback DejaVu Sans)
    mpl.rcParams["figure.facecolor"] = "white"
    mpl.rcParams["axes.facecolor"] = "white"
    mpl.rcParams["font.family"] = "sans-serif"
    mpl.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]

    computed = []
    for task in TASKS:
        counts = task["counts"]
        percents = row_normalize_percent(counts)
        computed.append({**task, "percents": percents})

    # 1x3 combined figure, no global title
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), constrained_layout=True)

    last_im = None
    for ax, task in zip(axes, computed):
        sub_title = f"{task['panel']} {task['name']}"
        last_im = draw_task_confusion(ax, task["counts"], task["percents"], task["labels"], sub_title)

    cbar = fig.colorbar(last_im, ax=axes, shrink=0.9, pad=0.02)
    cbar.set_label("Row-normalized percentage (%)")

    # Save figure files
    png_path = OUTPUT_DIR / "Figure_10_normalized_confusion_matrices.png"
    tif_path = OUTPUT_DIR / "Figure_10_normalized_confusion_matrices.tif"
    pdf_path = OUTPUT_DIR / "Figure_10_normalized_confusion_matrices.pdf"

    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    fig.savefig(tif_path, dpi=600, bbox_inches="tight")
    fig.savefig(pdf_path, dpi=600, bbox_inches="tight")
    plt.close(fig)

    # Save Excel: counts + percents sheets
    xlsx_path = OUTPUT_DIR / "Figure10_normalized_confusion_matrices.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for task in computed:
            labels = task["labels"]
            counts_df = pd.DataFrame(task["counts"], index=labels, columns=labels)
            percent_df = pd.DataFrame(task["percents"], index=labels, columns=labels)
            counts_df.to_excel(writer, sheet_name=task["sheet_counts"])
            percent_df.to_excel(writer, sheet_name=task["sheet_percent"])

    # Save text summary
    txt_path = OUTPUT_DIR / "Figure10_confusion_matrix_summary.txt"
    lines = []
    lines.append("Figure 10 confusion matrix summary")
    lines.append("=" * 40)
    lines.append("Data source: known confusion-matrix counts from previous model outputs")
    lines.append("")

    for idx, task in enumerate(computed, start=1):
        labels = task["labels"]
        counts = task["counts"]
        percents = task["percents"]
        recalls = np.diag(percents)

        lines.append(f"Task {idx}: {task['name']}")
        lines.append(f"Label order: {labels}")
        lines.append("Raw count matrix:")
        lines.append(format_matrix_for_summary(counts))
        lines.append("Row-normalized percentage matrix (%):")
        lines.append(format_matrix_for_summary(percents, decimals=1))
        lines.append("Per-class recall (diagonal, %):")
        for lbl, rec in zip(labels, recalls):
            lines.append(f"  - {lbl}: {rec:.1f}%")
        lines.append("")

    txt_path.write_text("\n".join(lines), encoding="utf-8")

    # Console output: Figure 10 only
    print("Saved:")
    print(str(png_path))
    print(str(tif_path))
    print(str(pdf_path))
    print(str(xlsx_path))
    print(str(txt_path))


if __name__ == "__main__":
    main()
