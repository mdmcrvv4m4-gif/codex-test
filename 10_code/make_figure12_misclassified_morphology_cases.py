#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from PIL import Image

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

BASE = Path(r"E:\Barrel_SEM_Z1_Z4_New")
TABLE_DIR = BASE / "05_tables"
FIG_DIR = BASE / "07_figures_main"
MODEL_DIR = BASE / "08_models"
CODE_DIR = BASE / "10_code"
SEM_DIR = BASE / "03_standardized_SEM_2048x1536"
PATCH_DIR = BASE / "04_patches_4x4"
SEG_DIR = BASE / "06B_semantic_segmentation"
MANUAL_DIR = BASE / "06A_manual_annotations"

S10 = TABLE_DIR / "S10_ML_labeled_feature_table_Z1_Z4.xlsx"
S6 = TABLE_DIR / "S6_semantic_features_Z1_Z4.xlsx"
S7 = TABLE_DIR / "S7_feature_table_with_semantic_DSI_Z1_Z4.xlsx"

IMG_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
GOOD_MASK_KWS = ["overlay", "mask", "label", "annotation", "annotated", "semantic", "segmentation", "pred", "prediction"]
BAD_MASK_PATH_KWS = ["images_for_annotation", "image_for_annotation", "raw", "original", "source"]
FEATURE_COLS = ["crack_area_fraction", "wear_area_fraction", "severe_damage_area_fraction", "crack_length_density", "crack_network_density", "wear_mark_density", "severe_damage_connected_area"]
TARGETS = [
    ("Task 1", "(a) True Z2, predicted Z3", "z2", "z3"),
    ("Task 1", "(b) True Z3, predicted Z2", "z3", "z2"),
    ("Task 2", "(c) True low damage, predicted medium damage", "low", "medium"),
    ("Task 2", "(d) True medium damage, predicted low damage", "medium", "low"),
]


def resolve_path(p: Path) -> Path:
    return p if p.exists() else Path(str(p).replace("E:\\", "/workspace/"))


def nrm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def nrm_sep(s: str) -> str:
    return re.sub(r"[_\-\s]+", "", str(s).lower())


def guess_col(cols: Sequence[str], cands: Sequence[str]) -> Optional[str]:
    m = {c: nrm(c) for c in cols}
    cc = [nrm(x) for x in cands]
    for c, k in m.items():
        if k in cc:
            return c
    for c, k in m.items():
        if any(x in k for x in cc):
            return c
    return None


def parse_patch_tokens(text: str) -> Dict[str, Optional[str]]:
    t = str(text)
    low = t.lower()
    zone = None
    img_no = None
    patch_no = None
    mz = re.search(r"\bz\s*([1-4])\b", low)
    if mz:
        zone = f"z{mz.group(1)}"
    mi = re.search(r"(?:img|image)\s*[_\- ]*0*(\d+)", low)
    if mi:
        img_no = str(int(mi.group(1)))
    mp = re.search(r"(?:patch|p)\s*[_\- ]*0*(\d+)", low)
    if mp:
        patch_no = str(int(mp.group(1)))
    return {"zone": zone, "img_no": img_no, "patch_no": patch_no}


def scan_images(root: Path) -> List[Path]:
    root = resolve_path(root)
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS]


def is_true_mask_overlay(path: Path) -> bool:
    low = str(path).lower().replace("\\", "/")
    if any(k in low for k in BAD_MASK_PATH_KWS):
        return False
    return any(k in low for k in GOOD_MASK_KWS)


def best_match(paths: List[Path], patch_id: str, image_id: str = "", need_overlay=False, strict_triplet=False, only_true_mask=False) -> Optional[Path]:
    if not paths:
        return None
    pid = nrm_sep(patch_id)
    iid = nrm_sep(image_id)
    tok = parse_patch_tokens(patch_id + " " + image_id)
    zone, img_no, patch_no = tok["zone"], tok["img_no"], tok["patch_no"]

    scored = []
    for p in paths:
        if only_true_mask and not is_true_mask_overlay(p):
            continue
        name = p.stem
        ns = nrm_sep(name)
        has_zone = bool(zone and zone in ns)
        has_img = bool(img_no and re.search(rf"(?:img|image)?0*{img_no}(?!\d)", ns))
        has_patch = bool(patch_no and re.search(rf"(?:patch|p)?0*{patch_no}(?!\d)", ns))
        if strict_triplet and not (has_zone and has_img and has_patch):
            continue
        score = 0
        if pid and pid in ns:
            score += 100
        if iid and iid in ns:
            score += 80
        if zone and zone in ns:
            score += 20
        if img_no and re.search(rf"(?:img|image)?0*{img_no}(?!\d)", ns):
            score += 20
        if patch_no and re.search(rf"(?:patch|p)?0*{patch_no}(?!\d)", ns):
            score += 25
        lower = name.lower()
        if "overlay" in lower:
            score += 10
        if any(k in lower for k in ["semantic", "segmentation", "pred"]):
            score += 5
        if "mask" in lower:
            score += 3
        if need_overlay and "overlay" in lower:
            score += 20
        if score > 0:
            scored.append((score, p))
    if not scored:
        return None
    scored.sort(key=lambda x: (-x[0], len(str(x[1]))))
    return scored[0][1]


def find_case_images(case: Dict, sem_files, patch_files, manual_files, seg_files) -> Dict:
    patch_id = str(case.get("Patch_ID", ""))
    image_id = str(case.get("Image_ID", ""))

    full = best_match(sem_files, patch_id, image_id, strict_triplet=False)
    patch = best_match(patch_files, patch_id, image_id, strict_triplet=True)
    if patch is None:
        patch = best_match(patch_files, patch_id, image_id, strict_triplet=False)

    seg = best_match(seg_files, patch_id, image_id, need_overlay=True, strict_triplet=True, only_true_mask=True)
    manual = best_match(manual_files, patch_id, image_id, need_overlay=True, strict_triplet=True, only_true_mask=True)
    mask = seg if seg else manual

    return {"full": full, "patch": patch, "mask": mask, "mask_match_ok": bool(mask), "mask_is_true_overlay_or_mask": bool(mask and is_true_mask_overlay(mask))}


def load_predictions_or_regenerate() -> pd.DataFrame:
    s10 = pd.read_excel(resolve_path(S10))
    cols = list(s10.columns)
    c_patch = guess_col(cols, ["Patch_ID", "patch_id", "patch", "sample_id"])
    c_img = guess_col(cols, ["Image_ID", "image_id", "image"])
    c_pr = guess_col(cols, ["Patch_row", "patch_row", "row"])
    c_pc = guess_col(cols, ["Patch_col", "patch_col", "col"])
    c_zone = guess_col(cols, ["Zone", "zone", "Barrel_zone", "region", "Zone_label"])
    c_sev = guess_col(cols, ["damage_severity", "severity_label", "severity", "Task2_label", "damage_label"])

    num_cols = [c for c in s10.columns if pd.api.types.is_numeric_dtype(s10[c])]
    bad_keys = ["patch", "image", "zone", "region", "label", "class", "target", "severity", "failure", "mode", "y_true", "y_pred", "pred", "file", "path", "mask", "overlay", "split", "fold", "row", "col", "sample", "id", "index"]
    feat_cols = [c for c in num_cols if not any(k in c.lower() for k in bad_keys)]
    X = s10[feat_cols].fillna(s10[feat_cols].median(numeric_only=True)).fillna(0)

    out = []
    for task, ycol in [("Task 1", c_zone), ("Task 2", c_sev)]:
        y = s10[ycol].astype(str)
        valid = y.str.strip().ne("")
        Xv, yv, mv = X.loc[valid], y.loc[valid], s10.loc[valid]
        Xtr, Xte, ytr, yte, mtr, mte = train_test_split(Xv, yv, mv, test_size=0.2, random_state=42, stratify=yv)
        clf = RandomForestClassifier(n_estimators=500, random_state=42, class_weight="balanced", n_jobs=-1)
        clf.fit(Xtr, ytr)
        yp = clf.predict(Xte)
        d = pd.DataFrame({
            "Task": task,
            "Model": "RandomForest",
            "Patch_ID": mte[c_patch].astype(str) if c_patch else mte.index.astype(str),
            "Image_ID": mte[c_img].astype(str) if c_img else "",
            "True_label": yte.values,
            "Predicted_label": yp,
            "Zone": mte[c_zone].astype(str) if c_zone else "",
            "Severity": mte[c_sev].astype(str) if c_sev else "",
            "Patch_row": pd.to_numeric(mte[c_pr], errors="coerce") if c_pr else np.nan,
            "Patch_col": pd.to_numeric(mte[c_pc], errors="coerce") if c_pc else np.nan,
        })
        d["correct"] = d["True_label"] == d["Predicted_label"]
        out.append(d)
    pred = pd.concat(out, ignore_index=True)
    pred.to_excel(resolve_path(FIG_DIR) / "Figure12_RF_patch_level_predictions_Task1_Task2.xlsx", index=False)
    return pred


def choose_cases(pred: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for task, case_label, tkw, pkw in TARGETS:
        d = pred[pred["Task"].str.contains(task, case=False, na=False)].copy()
        m = d[d["True_label"].str.lower().str.contains(tkw) & d["Predicted_label"].str.lower().str.contains(pkw)]
        sel = m.iloc[0] if len(m) else (d.iloc[0] if len(d) else pd.Series(dtype=object))
        rec = sel.to_dict() if len(sel) else {}
        rec["Case_label"] = case_label
        rows.append(rec)
    out = pd.DataFrame(rows)
    for c in ["Task", "Patch_ID", "Image_ID", "True_label", "Predicted_label", "Zone", "Severity", "Patch_row", "Patch_col"]:
        if c not in out.columns:
            out[c] = ""
    return out


def patch_row_col(case: Dict) -> Tuple[Optional[int], Optional[int]]:
    pr = case.get("Patch_row", np.nan)
    pc = case.get("Patch_col", np.nan)
    if pd.notna(pr) and pd.notna(pc):
        return int(pr), int(pc)
    tok = parse_patch_tokens(str(case.get("Patch_ID", "")))
    p = tok.get("patch_no")
    if p is not None:
        idx = int(p) - 1
        return idx // 4, idx % 4
    return None, None


def read_gray(image_path: Path) -> np.ndarray:
    return np.array(Image.open(image_path).convert("L"))


def draw_or_text(ax, image_path: Optional[Path], missing_text: str, force_gray: bool = False):
    ax.axis("off")
    if image_path and Path(image_path).exists():
        if force_gray:
            ax.imshow(read_gray(Path(image_path)), cmap="gray")
        else:
            ax.imshow(np.array(Image.open(image_path)))
    else:
        ax.text(0.5, 0.5, missing_text, ha="center", va="center", fontsize=9)


def main():
    out_dir = resolve_path(FIG_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = ["S13 contains class-level reports only; patch-level predictions will be searched or regenerated from S10."]

    pred = load_predictions_or_regenerate()
    cases = choose_cases(pred)

    sem_files = scan_images(SEM_DIR)
    patch_files = scan_images(PATCH_DIR)
    seg_files = scan_images(SEG_DIR)
    manual_files = scan_images(MANUAL_DIR)

    diagnosis = []
    for dname, files in [("03_standardized_SEM_2048x1536", sem_files), ("04_patches_4x4", patch_files), ("06B_semantic_segmentation", seg_files), ("06A_manual_annotations", manual_files)]:
        diagnosis.append(f"{dname}: {len(files)} images")
        diagnosis.append("First 50 files:")
        diagnosis.extend([str(p) for p in files[:50]])
        diagnosis.append("")

    matches = []
    for _, r in cases.iterrows():
        c = r.to_dict()
        m = find_case_images(c, sem_files, patch_files, manual_files, seg_files)
        tok = parse_patch_tokens(f"{c.get('Patch_ID','')} {c.get('Image_ID','')}")
        c.update({
            "case_zone": tok.get("zone", ""),
            "case_img_no": tok.get("img_no", ""),
            "case_patch_no": tok.get("patch_no", ""),
            "full_sem_path": str(m["full"]) if m["full"] else "",
            "patch_path": str(m["patch"]) if m["patch"] else "",
            "mask_overlay_path": str(m["mask"]) if m["mask"] else "",
            "mask_match_ok": bool(m["mask_match_ok"]),
            "mask_is_true_overlay_or_mask": bool(m["mask_is_true_overlay_or_mask"]),
        })
        matches.append(c)
        diagnosis.append(f"Case: {c.get('Case_label')} | Patch_ID={c.get('Patch_ID')} | Image_ID={c.get('Image_ID')} | Patch_row={c.get('Patch_row')} | Patch_col={c.get('Patch_col')}")
        diagnosis.append(f"  full SEM: {c['full_sem_path'] or 'NOT FOUND'}")
        diagnosis.append(f"  patch: {c['patch_path'] or 'NOT FOUND'}")
        diagnosis.append(f"  mask/overlay: {c['mask_overlay_path'] or 'NOT FOUND'}")
        if not c['full_sem_path']: diagnosis.append("  reason: full SEM match failed")
        if not c['patch_path']: diagnosis.append("  reason: patch match failed")
        if not c['mask_overlay_path']: diagnosis.append("  reason: mask/overlay match failed")

    matched_df = pd.DataFrame(matches)
    matched_df["mask_source"] = np.where(matched_df["mask_overlay_path"].str.contains("06A_manual_annotations", na=False), "manual", np.where(matched_df["mask_overlay_path"].str.contains("06B_semantic_segmentation", na=False), "segmentation", "none"))
    keep_cols = ["Patch_ID", "Image_ID", "case_zone", "case_img_no", "case_patch_no", "full_sem_path", "patch_path", "mask_overlay_path", "mask_source", "mask_match_ok", "mask_is_true_overlay_or_mask", "Case_label", "True_label", "Predicted_label", "Patch_row", "Patch_col"]
    for c in keep_cols:
        if c not in matched_df.columns:
            matched_df[c] = ""
    matched_df[keep_cols].to_excel(out_dir / "Figure12_selected_misclassified_cases.xlsx", index=False)

    mpl.rcParams["font.family"] = "sans-serif"
    mpl.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
    fig, axes = plt.subplots(4, 3, figsize=(12, 14), facecolor="white")
    fig.subplots_adjust(top=0.92, hspace=0.35, wspace=0.15)
    for j, t in enumerate(["Full SEM with patch location", "SEM patch", "Semantic mask / overlay"]):
        axes[0, j].set_title(t, fontsize=10)

    for i in range(4):
        for j in range(3):
            axes[i, j].axis("off")
        if i < len(matched_df):
            c = matched_df.iloc[i].to_dict()
            axes[i, 0].text(0.01, 0.98, c.get("Case_label", ""), transform=axes[i, 0].transAxes, fontsize=9, va="top")
            axes[i, 0].text(0.01, -0.06, f"Patch_ID={c.get('Patch_ID','')} | True={c.get('True_label','')} | Pred={c.get('Predicted_label','')}", transform=axes[i, 0].transAxes, fontsize=7, va="top")
            full = Path(c["full_sem_path"]) if c.get("full_sem_path") else None
            patch = Path(c["patch_path"]) if c.get("patch_path") else None
            mask = Path(c["mask_overlay_path"]) if c.get("mask_overlay_path") else None

            if full and full.exists():
                img = read_gray(full)
                axes[i, 0].imshow(img, cmap="gray")
                pr, pc = patch_row_col(c)
                if pr is not None and pc is not None:
                    h, w = img.shape[0], img.shape[1]
                    pw, ph = w / 4.0, h / 4.0
                    axes[i, 0].add_patch(Rectangle((pc*pw, pr*ph), pw, ph, fill=False, edgecolor="red", linewidth=1.2))
                else:
                    summary.append(f"{c.get('Case_label')}: cannot compute accurate red-box location (missing patch row/col).")
            else:
                draw_or_text(axes[i, 0], None, "Full SEM not found")

            draw_or_text(axes[i, 1], patch, "Patch image not found", force_gray=True)
            if c.get("mask_is_true_overlay_or_mask", False):
                draw_or_text(axes[i, 2], mask, "Mask/overlay not found")
            else:
                draw_or_text(axes[i, 2], None, "Mask/overlay not found")
                summary.append(f"{c.get('Case_label')}: No strict semantic mask/overlay was found for this case.")

    fig.tight_layout()
    for ext in ["png", "tif", "pdf"]:
        fig.savefig(out_dir / f"Figure_12_misclassified_morphology_cases.{ext}", dpi=600, bbox_inches="tight")
    plt.close(fig)

    (out_dir / "Figure12_image_matching_diagnosis.txt").write_text("\n".join(diagnosis), encoding="utf-8")

    success = []
    fail = []
    for _, c in matched_df.iterrows():
        ok = bool(c.get("full_sem_path")) and bool(c.get("patch_path"))
        (success if ok else fail).append(c.get("Case_label", ""))
        summary.append(f"Selected case {c.get('Case_label')}: full={c.get('full_sem_path','')} | patch={c.get('patch_path','')} | mask={c.get('mask_overlay_path','')}")
        summary.append(f"  patch shown as grayscale SEM: True")
        summary.append(f"  mask_match_ok={c.get('mask_match_ok', False)} | mask_is_true_overlay_or_mask={c.get('mask_is_true_overlay_or_mask', False)}")
    summary.append("Excluded images_for_annotation/raw/original/source from strict mask/overlay usage.")

    summary.append(f"Matched cases: {success}")
    summary.append(f"Missing cases: {fail}")
    (out_dir / "Figure12_case_selection_summary.txt").write_text("\n".join(summary), encoding="utf-8")

    print("Selected 4 cases:")
    for _, c in matched_df.iterrows():
        print(c.get("Case_label", ""))
        print("  full SEM:", c.get("full_sem_path", ""))
        print("  patch:", c.get("patch_path", ""))
        print("  mask/overlay:", c.get("mask_overlay_path", ""))
        print("  mask_match_ok:", c.get("mask_match_ok", ""))
        print("  mask_is_true_overlay_or_mask:", c.get("mask_is_true_overlay_or_mask", ""))
    print("Matched cases:", success)
    print("Missing cases:", fail)


if __name__ == "__main__":
    main()
