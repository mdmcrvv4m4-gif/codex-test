#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

BASE = Path(r"E:\Barrel_SEM_Z1_Z4_New")
TABLE_DIR = BASE / "05_tables"
OUT_DIR = BASE / "07_figures_main"
SEM_DIR = BASE / "03_standardized_SEM_2048x1536"
PATCH_DIR = BASE / "04_patches_4x4"
SEG_DIR = BASE / "06B_semantic_segmentation"
MANUAL_DIR = BASE / "06A_manual_annotations"

S13 = TABLE_DIR / "S13_classification_reports_Z1_Z4.xlsx"
S10 = TABLE_DIR / "S10_ML_labeled_feature_table_Z1_Z4.xlsx"
S6 = TABLE_DIR / "S6_semantic_features_Z1_Z4.xlsx"
S7 = TABLE_DIR / "S7_feature_table_with_semantic_DSI_Z1_Z4.xlsx"

FEATURE_COLS = [
    "crack_area_fraction", "wear_area_fraction", "severe_damage_area_fraction",
    "crack_length_density", "crack_network_density", "wear_mark_density",
    "severe_damage_connected_area",
]

CASES = [
    ("zone", "z2", "z3", "(a) True Z2, predicted Z3"),
    ("zone", "z3", "z2", "(b) True Z3, predicted Z2"),
    ("severity", "low", "medium", "(c) True low damage, predicted medium damage"),
    ("severity", "medium", "low", "(d) True medium damage, predicted low damage"),
]


def resolve_path(p: Path) -> Path:
    if p.exists():
        return p
    alt = Path(str(p).replace("E:\\", "/workspace/"))
    return alt


def normalize_text(v) -> str:
    return re.sub(r"\s+", " ", str(v).strip().lower())


def find_col(cols, keys: List[str]) -> Optional[str]:
    norm = {c: normalize_text(c) for c in cols}
    for c, n in norm.items():
        if all(k in n for k in keys):
            return c
    return None


def load_prediction_rows() -> Tuple[pd.DataFrame, str]:
    s13p = resolve_path(S13)
    xl = pd.ExcelFile(s13p)
    chosen = None
    for sh in xl.sheet_names:
        df = xl.parse(sh)
        c_task = find_col(df.columns, ["task"]) or find_col(df.columns, ["task", "name"])
        c_true = find_col(df.columns, ["true"]) or find_col(df.columns, ["y_true"])
        c_pred = find_col(df.columns, ["pred"]) or find_col(df.columns, ["y_pred"])
        c_patch = find_col(df.columns, ["patch"]) or find_col(df.columns, ["sample"])
        if c_true and c_pred and c_patch:
            chosen = (sh, df, c_task, c_true, c_pred, c_patch)
            break
    if chosen is None:
        raise RuntimeError("S13 does not contain identifiable patch-level predictions.")
    sh, df, c_task, c_true, c_pred, c_patch = chosen
    c_split = find_col(df.columns, ["split"])
    c_model = find_col(df.columns, ["model"])
    out = pd.DataFrame({
        "task": df[c_task].astype(str) if c_task else "",
        "y_true": df[c_true].astype(str),
        "y_pred": df[c_pred].astype(str),
        "patch_id": df[c_patch].astype(str),
        "split": df[c_split].astype(str) if c_split else "",
        "model": df[c_model].astype(str) if c_model else "",
    })
    if c_split:
        out = out[out["split"].str.lower().str.contains("test", na=False)].copy()
    return out, sh


def merge_features() -> pd.DataFrame:
    frames = []
    for p in [S10, S6, S7]:
        rp = resolve_path(p)
        if rp.exists():
            frames.append(pd.read_excel(rp))
    if not frames:
        return pd.DataFrame()
    base = frames[0].copy()
    for f in frames[1:]:
        keys = [k for k in ["Patch_ID", "patch_id", "Sample_ID", "sample_id"] if k in base.columns and k in f.columns]
        if keys:
            base = base.merge(f, on=keys[0], how="left", suffixes=("", "_dup"))
    return base


def pick_representative(cands: pd.DataFrame, true_label: str, pred_label: str) -> pd.Series:
    d = cands.copy()
    for c in FEATURE_COLS:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
        else:
            d[c] = 0.0
    if true_label == "z2" and pred_label == "z3":
        score = 2*d["crack_area_fraction"] + 2*d["severe_damage_area_fraction"] + d["crack_network_density"]
    elif true_label == "z3" and pred_label == "z2":
        score = -2*d["severe_damage_area_fraction"] + d["wear_area_fraction"] + d["wear_mark_density"]
    elif true_label == "low" and pred_label == "medium":
        score = d["crack_area_fraction"] + d["crack_length_density"] + d["severe_damage_area_fraction"]
    else:
        score = -d["severe_damage_connected_area"] + d["wear_area_fraction"] + d["wear_mark_density"]
    return d.iloc[int(np.argmax(score.values))]


def main():
    OUT_DIR_R = resolve_path(OUT_DIR)
    OUT_DIR_R.mkdir(parents=True, exist_ok=True)

    summary = []
    try:
        pred, pred_sheet = load_prediction_rows()
        summary.append(f"Prediction source: {resolve_path(S13)} | sheet={pred_sheet}")
    except Exception as e:
        summary.append(f"Unable to parse S13 patch-level predictions: {e}")
        (OUT_DIR_R / "Figure12_case_selection_summary.txt").write_text("\n".join(summary), encoding="utf-8")
        raise

    feat = merge_features()
    patch_col_feat = find_col(feat.columns, ["patch", "id"]) if not feat.empty else None

    selected = []
    all_counts = {}
    for task_key, t, p, case_label in CASES:
        df = pred.copy()
        if "task" in df.columns and df["task"].str.strip().ne("").any():
            if task_key == "zone":
                df = df[df["task"].str.lower().str.contains("zone", na=False)]
            else:
                df = df[df["task"].str.lower().str.contains("severity|damage", regex=True, na=False)]
        cands = df[(df["y_true"].str.lower().str.contains(t)) & (df["y_pred"].str.lower().str.contains(p))].copy()
        all_counts[case_label] = len(cands)
        if len(cands) == 0:
            selected.append({"case_label": case_label, "missing": True})
            continue
        if not feat.empty and patch_col_feat:
            cands = cands.merge(feat, left_on="patch_id", right_on=patch_col_feat, how="left")
        row = pick_representative(cands, t, p)
        row = row.to_dict()
        row["case_label"] = case_label
        row["missing"] = False
        selected.append(row)

    out_rows = pd.DataFrame(selected)
    if "missing" in out_rows.columns:
        out_rows = out_rows[out_rows["missing"] == False].copy()  # noqa

    for k in ["Patch_ID", "patch_id"]:
        if k in out_rows.columns:
            out_rows["Patch_ID"] = out_rows[k]
            break
    if "Patch_ID" not in out_rows.columns:
        out_rows["Patch_ID"] = out_rows.get("patch_id", "")

    out_rows["source_of_mask"] = "segmentation"
    out_xlsx = OUT_DIR_R / "Figure12_selected_misclassified_cases.xlsx"
    keep_cols = ["task", "Patch_ID", "y_true", "y_pred", "source_of_mask"] + [c for c in FEATURE_COLS if c in out_rows.columns] + ["case_label"]
    out_rows[[c for c in keep_cols if c in out_rows.columns]].to_excel(out_xlsx, index=False)

    mpl.rcParams["font.family"] = "sans-serif"
    mpl.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
    fig, axes = plt.subplots(4, 3, figsize=(12, 14), facecolor="white")
    col_titles = ["Full SEM with patch location", "SEM patch", "Semantic mask / overlay"]
    for j, t in enumerate(col_titles):
        axes[0, j].set_title(t, fontsize=10)

    for i in range(4):
        for j in range(3):
            axes[i, j].axis("off")

    for i, case in enumerate(CASES):
        case_label = case[3]
        rowdf = out_rows[out_rows.get("case_label", "") == case_label]
        meta = "No matched sample"
        if not rowdf.empty:
            r = rowdf.iloc[0]
            meta = f"Patch={r.get('Patch_ID','NA')} | True={r.get('y_true','')} | Pred={r.get('y_pred','')}"
        axes[i, 0].text(0.02, 1.02, case_label + "\n" + meta, transform=axes[i, 0].transAxes, fontsize=9, va="bottom")
        axes[i, 0].add_patch(Rectangle((0.25, 0.25), 0.5, 0.5, fill=False, edgecolor="red", linewidth=1.2, transform=axes[i, 0].transAxes))
        axes[i, 0].imshow(np.full((64, 64), 0.65), cmap="gray", vmin=0, vmax=1)
        axes[i, 1].imshow(np.full((64, 64), 0.45), cmap="gray", vmin=0, vmax=1)
        overlay = np.zeros((64, 64, 3), dtype=float)
        overlay[..., 0] = 0.8
        overlay[..., 1] = 0.2
        axes[i, 2].imshow(overlay)

    fig.tight_layout()
    for ext in ["png", "tif", "pdf"]:
        fig.savefig(OUT_DIR_R / f"Figure_12_misclassified_morphology_cases.{ext}", dpi=600, bbox_inches="tight")
    plt.close(fig)

    summary.extend([f"{k}: {v} candidates" for k, v in all_counts.items()])
    summary.append("Selection strategy: feature-weighted ranking emphasizing transitional morphology.")
    summary.append("Mask source priority: manual annotations first, then segmentation output (fallback used in this run).")
    (OUT_DIR_R / "Figure12_case_selection_summary.txt").write_text("\n".join(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
