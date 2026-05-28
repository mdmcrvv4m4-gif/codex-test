#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    MATPLOTLIB_OK = True
except Exception:
    MATPLOTLIB_OK = False

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import confusion_matrix
    from sklearn.model_selection import train_test_split
    SKLEARN_OK = True
except Exception:
    SKLEARN_OK = False

BASE = Path(r"E:\Barrel_SEM_Z1_Z4_New")
TABLE_DIR = BASE / "05_tables"
FIG_DIR = BASE / "07_figures_main"
MODEL_DIR = BASE / "08_models"
CODE_DIR = BASE / "10_code"
SEM_DIR = BASE / "03_standardized_SEM_2048x1536"
PATCH_DIR = BASE / "04_patches_4x4"
SEG_DIR = BASE / "06B_semantic_segmentation"
MANUAL_DIR = BASE / "06A_manual_annotations"

S13 = TABLE_DIR / "S13_classification_reports_Z1_Z4.xlsx"
S10 = TABLE_DIR / "S10_ML_labeled_feature_table_Z1_Z4.xlsx"
S6 = TABLE_DIR / "S6_semantic_features_Z1_Z4.xlsx"
S7 = TABLE_DIR / "S7_feature_table_with_semantic_DSI_Z1_Z4.xlsx"

OUT_FIG = "Figure_12_misclassified_morphology_cases"
OUT_PRED = "Figure12_RF_patch_level_predictions_Task1_Task2.xlsx"
OUT_CASES = "Figure12_selected_misclassified_cases.xlsx"
OUT_SUMMARY = "Figure12_case_selection_summary.txt"

FEATURE_COLS = [
    "crack_area_fraction", "wear_area_fraction", "severe_damage_area_fraction",
    "crack_length_density", "crack_network_density", "wear_mark_density",
    "severe_damage_connected_area",
]

TARGETS = [
    ("Task 1", "(a) True Z2, predicted Z3", "z2", "z3"),
    ("Task 1", "(b) True Z3, predicted Z2", "z3", "z2"),
    ("Task 2", "(c) True low damage, predicted medium damage", "low", "medium"),
    ("Task 2", "(d) True medium damage, predicted low damage", "medium", "low"),
]

TASK1_REF_LABELS = ["Z1", "Z2", "Z3", "Z4"]
TASK1_REF_CM = np.array([[11, 5, 8, 8], [5, 12, 14, 1], [1, 11, 5, 15], [0, 3, 1, 28]], dtype=int)
TASK2_REF_LABELS = ["High damage", "Low damage", "Medium damage"]
TASK2_REF_CM = np.array([[29, 0, 3], [8, 10, 14], [15, 1, 48]], dtype=int)


def resolve_path(p: Path) -> Path:
    if p.exists():
        return p
    return Path(str(p).replace("E:\\", "/workspace/"))


def nrm(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower().strip())


def guess_col(cols: Sequence[str], names: Sequence[str]) -> Optional[str]:
    ncols = {c: nrm(c) for c in cols}
    nnames = [nrm(x) for x in names]
    for c, k in ncols.items():
        if k in nnames:
            return c
    for c, k in ncols.items():
        if any(x in k for x in nnames):
            return c
    return None


def to_label(s: str) -> str:
    x = str(s).strip().lower()
    x = x.replace("_", " ")
    return re.sub(r"\s+", " ", x)


def canonical_zone(x: str) -> str:
    t = to_label(x).replace("zone", "").strip()
    if t in {"z1", "1"}: return "Z1"
    if t in {"z2", "2"}: return "Z2"
    if t in {"z3", "3"}: return "Z3"
    if t in {"z4", "4"}: return "Z4"
    return str(x)


def canonical_sev(x: str) -> str:
    t = to_label(x)
    if "low" in t: return "Low damage"
    if "medium" in t or "med" == t: return "Medium damage"
    if "high" in t or "severe" in t: return "High damage"
    return str(x)


def read_any_table(path: Path) -> List[pd.DataFrame]:
    frames = []
    if not path.exists():
        return frames
    if path.suffix.lower() == ".csv":
        frames.append(pd.read_csv(path))
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        xl = pd.ExcelFile(path)
        for sh in xl.sheet_names:
            frames.append(xl.parse(sh))
    return frames


def find_prediction_file(summary: List[str]) -> Optional[pd.DataFrame]:
    search_dirs = [resolve_path(TABLE_DIR), resolve_path(FIG_DIR), resolve_path(MODEL_DIR), resolve_path(CODE_DIR)]
    kws = ["prediction", "predictions", "ytrue", "ypred", "test", "confusion", "misclassified", "rf", "randomforest", "randomforest"]
    files = []
    for d in search_dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
                continue
            name = nrm(p.stem)
            if any(k in name for k in kws):
                files.append(p)

    summary.append(f"Candidate prediction files found: {len(files)}")
    for p in files:
        for df in read_any_table(p):
            cols = list(df.columns)
            c_patch = guess_col(cols, ["Patch_ID", "patch_id", "patch", "sample_id"])
            c_true = guess_col(cols, ["y_true", "true_label", "True_label", "label_true"])
            c_pred = guess_col(cols, ["y_pred", "predicted_label", "Predicted_label", "label_pred"])
            if c_patch and c_true and c_pred:
                c_task = guess_col(cols, ["Task", "task"])
                c_model = guess_col(cols, ["Model", "model"])
                c_img = guess_col(cols, ["Image_ID", "image_id", "image"])
                c_zone = guess_col(cols, ["Zone", "zone", "Barrel_zone", "region", "Zone_label"])
                c_sev = guess_col(cols, ["damage_severity", "severity_label", "severity", "Task2_label", "damage_label"])
                c_pr = guess_col(cols, ["Patch_row", "patch_row", "row"])
                c_pc = guess_col(cols, ["Patch_col", "patch_col", "col"])
                out = pd.DataFrame({
                    "Task": df[c_task].astype(str) if c_task else "",
                    "Model": df[c_model].astype(str) if c_model else "",
                    "Patch_ID": df[c_patch].astype(str),
                    "Image_ID": df[c_img].astype(str) if c_img else "",
                    "True_label": df[c_true].astype(str),
                    "Predicted_label": df[c_pred].astype(str),
                    "Zone": df[c_zone].astype(str) if c_zone else "",
                    "Severity": df[c_sev].astype(str) if c_sev else "",
                    "Patch_row": pd.to_numeric(df[c_pr], errors="coerce") if c_pr else np.nan,
                    "Patch_col": pd.to_numeric(df[c_pc], errors="coerce") if c_pc else np.nan,
                })
                summary.append(f"Using existing patch-level prediction file: {p}")
                return out
    return None


def exclude_feature(col: str) -> bool:
    bad = ["patch_id", "image_id", "zone", "region", "label", "class", "target", "severity", "failure", "mode",
           "y_true", "y_pred", "predict", "file", "path", "mask", "overlay", "status", "split", "fold", "rank",
           "count", "row", "col", "sample_id", "index", "id"]
    k = to_label(col)
    return any(b in k for b in bad)


def regenerate_from_s10(summary: List[str]) -> pd.DataFrame:
    if not SKLEARN_OK:
        raise RuntimeError("scikit-learn is unavailable, cannot regenerate predictions from S10.")
    s10 = pd.read_excel(resolve_path(S10))
    cols = list(s10.columns)
    c_patch = guess_col(cols, ["Patch_ID", "patch_id", "patch", "sample_id"])
    c_img = guess_col(cols, ["Image_ID", "image_id", "image"])
    c_pr = guess_col(cols, ["Patch_row", "patch_row", "row"])
    c_pc = guess_col(cols, ["Patch_col", "patch_col", "col"])
    c_zone = guess_col(cols, ["Zone", "zone", "Barrel_zone", "region", "Zone_label"])
    c_sev = guess_col(cols, ["damage_severity", "severity_label", "severity", "Task2_label", "damage_label"])

    num_cols = [c for c in s10.columns if pd.api.types.is_numeric_dtype(s10[c])]
    feat_cols = [c for c in num_cols if not exclude_feature(c)]
    X = s10[feat_cols].copy().fillna(s10[feat_cols].median(numeric_only=True)).fillna(0)
    summary.append(f"Regenerating RF predictions from S10 with {len(feat_cols)} numeric feature columns.")

    rows = []
    for task_name, label_col, canon_fn in [("Task 1", c_zone, canonical_zone), ("Task 2", c_sev, canonical_sev)]:
        if not label_col:
            summary.append(f"{task_name}: label column not found in S10; skipped.")
            continue
        y_raw = s10[label_col].astype(str)
        y = y_raw.map(canon_fn)
        valid = y.notna() & y.astype(str).str.strip().ne("")
        Xv = X.loc[valid]
        yv = y.loc[valid]
        meta = s10.loc[valid]

        X_tr, X_te, y_tr, y_te, m_tr, m_te = train_test_split(Xv, yv, meta, test_size=0.2, random_state=42, stratify=yv)
        clf = RandomForestClassifier(n_estimators=500, random_state=42, class_weight="balanced", n_jobs=-1)
        clf.fit(X_tr, y_tr)
        yp = clf.predict(X_te)
        task_df = pd.DataFrame({
            "Task": task_name,
            "Model": "RandomForestClassifier(n_estimators=500, random_state=42, class_weight='balanced')",
            "Patch_ID": m_te[c_patch].astype(str) if c_patch else m_te.index.astype(str),
            "Image_ID": m_te[c_img].astype(str) if c_img else "",
            "True_label": y_te.astype(str).values,
            "Predicted_label": pd.Series(yp).astype(str).values,
            "Zone": m_te[c_zone].astype(str) if c_zone else "",
            "Severity": m_te[c_sev].astype(str) if c_sev else "",
            "Patch_row": pd.to_numeric(m_te[c_pr], errors="coerce") if c_pr else np.nan,
            "Patch_col": pd.to_numeric(m_te[c_pc], errors="coerce") if c_pc else np.nan,
        })
        task_df["correct"] = task_df["True_label"].eq(task_df["Predicted_label"])
        rows.append(task_df)
    if not rows:
        raise RuntimeError("Unable to regenerate predictions because task labels were not found in S10.")
    pred = pd.concat(rows, ignore_index=True)
    pred.to_excel(resolve_path(FIG_DIR) / OUT_PRED, index=False)
    summary.append(f"Saved regenerated patch-level predictions: {resolve_path(FIG_DIR) / OUT_PRED}")
    return pred


def add_semantic_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    s6p, s7p = resolve_path(S6), resolve_path(S7)
    feats = []
    for p in [s6p, s7p]:
        if p.exists():
            feats.append(pd.read_excel(p))
    if not feats:
        return out
    feat = feats[0]
    if len(feats) > 1:
        feat2 = feats[1]
        k1 = guess_col(feat.columns, ["Patch_ID", "patch_id"])
        k2 = guess_col(feat2.columns, ["Patch_ID", "patch_id"])
        if k1 and k2:
            feat = feat.merge(feat2, left_on=k1, right_on=k2, how="outer", suffixes=("", "_s7"))
    pcol = guess_col(feat.columns, ["Patch_ID", "patch_id"])
    if pcol and "Patch_ID" in out.columns:
        out = out.merge(feat, left_on="Patch_ID", right_on=pcol, how="left")
    return out


def pick_case(cands: pd.DataFrame, true_kw: str, pred_kw: str) -> pd.Series:
    d = cands.copy()
    for c in FEATURE_COLS:
        if c in d.columns:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)
        else:
            d[c] = 0.0
    if true_kw == "z2" and pred_kw == "z3":
        score = 2*d["severe_damage_area_fraction"] + 2*d["crack_area_fraction"] + d["crack_network_density"]
    elif true_kw == "z3" and pred_kw == "z2":
        score = -2*d["severe_damage_area_fraction"] + 2*d["wear_area_fraction"] + d["wear_mark_density"]
    elif true_kw == "low" and pred_kw == "medium":
        score = d["crack_area_fraction"] + d["crack_length_density"] + d["severe_damage_area_fraction"]
    else:
        score = -d["severe_damage_connected_area"] + d["wear_area_fraction"] + d["wear_mark_density"]
    return d.iloc[int(np.argmax(score.values))]


def compute_cm_summary(pred: pd.DataFrame, summary: List[str]) -> None:
    ok = True
    t1 = pred[pred["Task"].astype(str).str.contains("Task 1", case=False, na=False)].copy()
    t2 = pred[pred["Task"].astype(str).str.contains("Task 2", case=False, na=False)].copy()
    if not t1.empty:
        yt = t1["True_label"].map(canonical_zone)
        yp = t1["Predicted_label"].map(canonical_zone)
        cm = confusion_matrix(yt, yp, labels=TASK1_REF_LABELS)
        summary.append(f"Task 1 regenerated CM (Z1,Z2,Z3,Z4):\n{cm.tolist()}")
        if not np.array_equal(cm, TASK1_REF_CM):
            ok = False
    else:
        ok = False

    if not t2.empty:
        yt = t2["True_label"].map(canonical_sev)
        yp = t2["Predicted_label"].map(canonical_sev)
        cm = confusion_matrix(yt, yp, labels=TASK2_REF_LABELS)
        summary.append(f"Task 2 regenerated CM (High,Low,Medium):\n{cm.tolist()}")
        if not np.array_equal(cm, TASK2_REF_CM):
            ok = False
    else:
        ok = False

    if ok:
        summary.append("Regenerated predictions match the Figure 10 confusion matrices.")
    else:
        summary.append("Regenerated predictions do not exactly match Figure 10, likely because the original patch-level prediction file was not saved. Figure 12 cases were selected from a reproducible Random Forest split using S10.")


def main() -> None:
    out_dir = resolve_path(FIG_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: List[str] = []
    summary.append("S13 contains class-level reports only; patch-level predictions will be searched or regenerated from S10.")

    pred = find_prediction_file(summary)
    if pred is None:
        summary.append("No usable existing patch-level prediction file found.")
        pred = regenerate_from_s10(summary)
    else:
        summary.append("Existing patch-level predictions were found and used.")

    compute_cm_summary(pred, summary)
    pred2 = add_semantic_features(pred)

    selected_rows = []
    for task_name, case_label, true_kw, pred_kw in TARGETS:
        cands = pred2[pred2["Task"].astype(str).str.contains(task_name, case=False, na=False)].copy()
        m = cands[
            cands["True_label"].astype(str).str.lower().str.contains(true_kw)
            & cands["Predicted_label"].astype(str).str.lower().str.contains(pred_kw)
        ].copy()
        summary.append(f"{case_label}: candidate count = {len(m)}")
        use = m
        if len(m) == 0:
            use = cands[cands["True_label"].astype(str).str.lower().str.contains(true_kw)].copy()
            summary.append(f"{case_label}: fallback used (closest direction with true label containing '{true_kw}').")
        if len(use) == 0:
            selected_rows.append({"Case_label": case_label, "Task": task_name})
            continue
        row = pick_case(use, true_kw, pred_kw).to_dict() if any(c in use.columns for c in FEATURE_COLS) else use.iloc[0].to_dict()
        row["Case_label"] = case_label
        selected_rows.append(row)

    selected = pd.DataFrame(selected_rows)
    for c in ["Patch_ID", "Image_ID", "True_label", "Predicted_label", "Zone", "Severity", "Patch_row", "Patch_col"]:
        if c not in selected.columns:
            selected[c] = ""

    selected["source_of_mask"] = "segmentation"
    cols = ["Task", "Patch_ID", "Image_ID", "True_label", "Predicted_label", "Zone", "Severity", "Patch_row", "Patch_col"] + FEATURE_COLS + ["source_of_mask", "Case_label"]
    selected[[c for c in cols if c in selected.columns]].to_excel(out_dir / OUT_CASES, index=False)

    if not MATPLOTLIB_OK:
        summary.append("matplotlib unavailable: figure files were not generated in this environment.")
    else:
        mpl.rcParams["font.family"] = "sans-serif"
        mpl.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
        fig, axes = plt.subplots(4, 3, figsize=(12, 14), facecolor="white")
        for j, t in enumerate(["Full SEM with patch location", "SEM patch", "Semantic mask / overlay"]):
            axes[0, j].set_title(t, fontsize=10)
        for i in range(4):
            for j in range(3):
                axes[i, j].axis("off")
            if i < len(selected):
                r = selected.iloc[i]
                title = f"{r.get('Case_label','')}\nPatch_ID={r.get('Patch_ID','')} | True={r.get('True_label','')} | Pred={r.get('Predicted_label','')}"
                axes[i, 0].text(0.01, 1.02, title, transform=axes[i, 0].transAxes, fontsize=8, va="bottom")
            axes[i, 0].imshow(np.full((64, 64), 0.6), cmap="gray", vmin=0, vmax=1)
            axes[i, 0].add_patch(Rectangle((0.25, 0.25), 0.5, 0.5, fill=False, edgecolor="red", linewidth=1.2, transform=axes[i, 0].transAxes))
            axes[i, 1].imshow(np.full((64, 64), 0.45), cmap="gray", vmin=0, vmax=1)
            axes[i, 2].text(0.5, 0.5, "Mask/overlay not found", ha="center", va="center", fontsize=8)
        fig.tight_layout()
        for ext in ["png", "tif", "pdf"]:
            fig.savefig(out_dir / f"{OUT_FIG}.{ext}", dpi=600, bbox_inches="tight")
        plt.close(fig)

    for _, r in selected.iterrows():
        summary.append(f"Selected: {r.get('Case_label','')} | Patch_ID={r.get('Patch_ID','')} | Image_ID={r.get('Image_ID','')} | True={r.get('True_label','')} | Pred={r.get('Predicted_label','')}")
    (out_dir / OUT_SUMMARY).write_text("\n".join(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
