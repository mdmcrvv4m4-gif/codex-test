#!/usr/bin/env python3
"""Generate Figure 10: row-normalized confusion matrices for three ML tasks.

Priority:
1) Search for y_true/y_pred files in ../05_tables, ../07_figures_main, ../08_models.
2) If not found, fallback to hard-coded confusion count matrices.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TASKS = {
    "Task1": {
        "title": "(a) Zone classification",
        "labels": ["Z1", "Z2", "Z3", "Z4"],
        "counts": np.array(
            [[11, 5, 8, 8], [5, 12, 14, 1], [1, 11, 5, 15], [0, 3, 1, 28]],
            dtype=float,
        ),
    },
    "Task2": {
        "title": "(b) Damage severity classification",
        "labels": ["High damage", "Low damage", "Medium damage"],
        "counts": np.array([[29, 0, 3], [8, 10, 14], [15, 1, 48]], dtype=float),
    },
    "Task3": {
        "title": "(c) Failure mode classification",
        "labels": ["Cracking-related", "Severe mixed", "Wear-dominated"],
        "counts": np.array([[4, 8, 0], [0, 67, 3], [0, 1, 41]], dtype=float),
    },
}

LABEL_ALIASES = {
    "high_damage": "High damage",
    "low_damage": "Low damage",
    "medium_damage": "Medium damage",
    "cracking_related_damage": "Cracking-related",
    "severe_mixed_surface_damage": "Severe mixed",
    "wear_dominated_damage": "Wear-dominated",
}


def normalize_rows_to_percent(counts: np.ndarray) -> np.ndarray:
    row_sums = counts.sum(axis=1, keepdims=True)
    percent = np.divide(
        counts * 100.0,
        row_sums,
        out=np.zeros_like(counts, dtype=float),
        where=row_sums != 0,
    )
    return percent


def clean_label(label: str) -> str:
    s = str(label).strip()
    s_low = s.lower().replace("-", "_").replace(" ", "_")
    s_low = re.sub(r"_+", "_", s_low)
    if s_low in LABEL_ALIASES:
        return LABEL_ALIASES[s_low]
    if s.upper() in {"Z1", "Z2", "Z3", "Z4"}:
        return s.upper()
    return s.replace("_", " ").strip().title()


def find_candidate_files(search_dirs: List[Path]) -> List[Path]:
    patterns = [
        "*y_true*y_pred*",
        "*predictions*",
        "*test_predictions*",
        "*confusion_matrix_data*",
        "*ml_predictions*",
    ]
    exts = {".csv", ".xlsx", ".xls", ".parquet", ".json"}
    candidates = []
    for d in search_dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in exts:
                continue
            lower_name = p.name.lower()
            if any(re.fullmatch(pat.replace("*", ".*"), lower_name) for pat in patterns) or any(
                k in lower_name
                for k in ["y_true", "y_pred", "prediction", "confusion", "ml_predictions"]
            ):
                candidates.append(p)
    return sorted(set(candidates))


def load_table(path: Path) -> Optional[pd.DataFrame]:
    try:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        if path.suffix.lower() in {".xlsx", ".xls"}:
            return pd.read_excel(path)
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        if path.suffix.lower() == ".json":
            return pd.read_json(path)
    except Exception:
        return None
    return None


def detect_columns(df: pd.DataFrame) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    cols = {c.lower().strip(): c for c in df.columns}

    y_true_col = next((cols[k] for k in cols if k in {"y_true", "true", "actual", "label_true", "ground_truth"}), None)
    y_pred_col = next((cols[k] for k in cols if k in {"y_pred", "pred", "predicted", "label_pred", "prediction"}), None)
    task_col = next((cols[k] for k in cols if k in {"task", "task_name", "dataset", "target"}), None)

    return y_true_col, y_pred_col, task_col


def matrix_from_ytrue_ypred(df: pd.DataFrame, labels: List[str], y_true_col: str, y_pred_col: str) -> np.ndarray:
    label_to_idx = {clean_label(lbl): i for i, lbl in enumerate(labels)}
    mat = np.zeros((len(labels), len(labels)), dtype=float)

    for _, row in df[[y_true_col, y_pred_col]].dropna().iterrows():
        t = clean_label(row[y_true_col])
        p = clean_label(row[y_pred_col])
        if t in label_to_idx and p in label_to_idx:
            mat[label_to_idx[t], label_to_idx[p]] += 1
    return mat


def infer_task_key(task_name: str) -> Optional[str]:
    s = str(task_name).lower()
    if "zone" in s or "z1" in s:
        return "Task1"
    if "severity" in s or "high" in s or "medium" in s or "low" in s:
        return "Task2"
    if "failure" in s or "wear" in s or "cracking" in s or "mixed" in s:
        return "Task3"
    return None


def try_build_from_predictions(search_dirs: List[Path]) -> Tuple[Optional[Dict[str, np.ndarray]], str]:
    files = find_candidate_files(search_dirs)
    if not files:
        return None, "No prediction-like files found."

    task_mats = {}
    used_files = []
    for f in files:
        df = load_table(f)
        if df is None or df.empty:
            continue
        y_true_col, y_pred_col, task_col = detect_columns(df)
        if not y_true_col or not y_pred_col:
            continue

        if task_col:
            for task_val, sub in df.groupby(task_col):
                tk = infer_task_key(task_val)
                if tk and tk not in task_mats:
                    mat = matrix_from_ytrue_ypred(sub, TASKS[tk]["labels"], y_true_col, y_pred_col)
                    if mat.sum() > 0:
                        task_mats[tk] = mat
                        used_files.append(str(f))
        else:
            for tk in TASKS.keys():
                if tk in task_mats:
                    continue
                mat = matrix_from_ytrue_ypred(df, TASKS[tk]["labels"], y_true_col, y_pred_col)
                if mat.sum() > 0:
                    task_mats[tk] = mat
                    used_files.append(str(f))

    if len(task_mats) == 3:
        return task_mats, f"Built from y_true/y_pred files: {sorted(set(used_files))}"

    return None, "Could not fully reconstruct all 3 tasks from prediction files."


def export_excel(out_xlsx: Path, counts_map: Dict[str, np.ndarray], perc_map: Dict[str, np.ndarray]) -> None:
    with pd.ExcelWriter(out_xlsx) as writer:
        for i, tk in enumerate(["Task1", "Task2", "Task3"], 1):
            labels = TASKS[tk]["labels"]
            pd.DataFrame(counts_map[tk], index=labels, columns=labels).to_excel(writer, sheet_name=f"Task{i}_counts")
            pd.DataFrame(perc_map[tk], index=labels, columns=labels).to_excel(writer, sheet_name=f"Task{i}_percent")


def write_summary(path: Path, source_note: str, counts_map: Dict[str, np.ndarray], perc_map: Dict[str, np.ndarray]) -> None:
    lines = [
        "Figure 10 confusion matrix summary",
        "=" * 40,
        f"Data source: {source_note}",
        "",
    ]
    for i, tk in enumerate(["Task1", "Task2", "Task3"], 1):
        labels = TASKS[tk]["labels"]
        counts = counts_map[tk]
        perc = perc_map[tk]
        recall = np.diag(perc)

        lines.append(f"Task {i} ({TASKS[tk]['title']}):")
        lines.append(f"Label order: {labels}")
        lines.append("Raw count matrix:")
        lines.append(str(counts.astype(int).tolist()))
        lines.append("Row-normalized percentage matrix (%):")
        lines.append(str(np.round(perc, 1).tolist()))
        lines.append("Per-class recall (diagonal, %):")
        lines.append(str([round(float(x), 1) for x in recall]))
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def plot_figure(out_base: Path, counts_map: Dict[str, np.ndarray], perc_map: Dict[str, np.ndarray]) -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)

    im = None
    for ax, tk in zip(axes, ["Task1", "Task2", "Task3"]):
        labels = TASKS[tk]["labels"]
        counts = counts_map[tk]
        perc = perc_map[tk]

        im = ax.imshow(perc, cmap="Blues", vmin=0, vmax=100)
        ax.set_title(TASKS[tk]["title"], fontsize=11)
        ax.set_xticks(np.arange(len(labels)))
        ax.set_yticks(np.arange(len(labels)))
        ax.set_xticklabels(labels, rotation=35, ha="right")
        ax.set_yticklabels(labels)
        ax.set_xlabel("Predicted label")
        ax.set_ylabel("True label")

        for i in range(perc.shape[0]):
            for j in range(perc.shape[1]):
                val = perc[i, j]
                cnt = int(counts[i, j])
                txt_color = "white" if val >= 50 else "black"
                ax.text(j, i, f"{val:.1f}%\n({cnt})", ha="center", va="center", color=txt_color, fontsize=9)

    cbar = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02)
    cbar.set_label("Row-normalized percentage (%)")

    png = out_base.with_suffix(".png")
    tif = out_base.with_suffix(".tif")
    pdf = out_base.with_suffix(".pdf")
    fig.savefig(png, dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(tif, dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, dpi=600, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    search_dirs = [repo_root / "05_tables", repo_root / "07_figures_main", repo_root / "08_models"]
    out_dir = repo_root / "07_figures_main"
    out_dir.mkdir(parents=True, exist_ok=True)

    from_pred, note = try_build_from_predictions(search_dirs)
    if from_pred is not None:
        counts_map = from_pred
        source_note = note
    else:
        counts_map = {k: TASKS[k]["counts"].copy() for k in TASKS}
        source_note = f"fallback hard-coded confusion counts ({note})"

    perc_map = {k: normalize_rows_to_percent(v) for k, v in counts_map.items()}

    out_base = out_dir / "Figure_10_normalized_confusion_matrices"
    plot_figure(out_base, counts_map, perc_map)

    out_xlsx = out_dir / "Figure10_normalized_confusion_matrices.xlsx"
    export_excel(out_xlsx, counts_map, perc_map)

    summary_txt = out_dir / "Figure10_confusion_matrix_summary.txt"
    write_summary(summary_txt, source_note, counts_map, perc_map)

    outputs = [
        out_base.with_suffix(".png"),
        out_base.with_suffix(".tif"),
        out_base.with_suffix(".pdf"),
        out_xlsx,
        summary_txt,
    ]
    print("Generated files:")
    for p in outputs:
        print(str(p))


if __name__ == "__main__":
    main()
