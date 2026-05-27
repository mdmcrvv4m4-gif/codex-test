import json
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch

BASE_WIN = Path(r"E:/Barrel_SEM_Z1_Z4_New")
BASE_LINUX = Path("/workspace/codex-test")

TABLE_DIR = BASE_WIN / "05_tables"
FIG_DIR = BASE_WIN / "07_figures_main"
CODE_DIR = BASE_WIN / "10_code"
SEG_DIR = BASE_WIN / "06B_semantic_segmentation"

REQ_TABLES = {
    "S4": "S4_annotation_subset_Z1_Z4.xlsx",
    "S5": "S5_mask_value_check_Z1_Z4.xlsx",
    "S6": "S6_semantic_features_Z1_Z4.xlsx",
    "S7": "S7_feature_table_with_semantic_DSI_Z1_Z4.xlsx",
}

PREF = {
    "Z1": ["Z1_img04_patch15", "Z1_img01_patch16", "Z1_img01_patch08", "Z1_img07_patch06"],
    "Z2": ["Z2_img07_patch07", "Z2_img07_patch15", "Z2_img07_patch09", "Z2_img07_patch05"],
    "Z3": ["Z3_img07_patch07", "Z3_img01_patch05", "Z3_img07_patch05", "Z3_img01_patch10"],
    "Z4": ["Z4_img07_patch10", "Z4_img07_patch04", "Z4_img01_patch06", "Z4_img01_patch14"],
}


def as_local(path_like: str) -> Path:
    s = str(path_like).strip()
    if not s or s.lower() == "nan":
        return Path("")
    s = s.replace("\\", "/")
    s = s.replace("D:/Barrel_SEM_Z1_Z4_New", str(BASE_WIN).replace("\\", "/"))
    p = Path(s)
    if p.exists():
        return p
    s2 = s.replace(str(BASE_WIN).replace("\\", "/"), str(BASE_LINUX))
    p2 = Path(s2)
    return p2


def find_table(name: str) -> Path:
    candidates = [
        TABLE_DIR / name,
        BASE_LINUX / "05_tables" / name,
        BASE_LINUX / name,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Missing required table: {name}. Checked: {candidates}")


def load_class_mapping(base: Path):
    search_dirs = [base / "10_code", base / "06B_semantic_segmentation", BASE_LINUX / "10_code", BASE_LINUX / "06B_semantic_segmentation"]
    mapping = None
    palette = None
    for d in search_dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.suffix.lower() not in {".json", ".yaml", ".yml", ".txt", ".csv", ".xlsx"}:
                continue
            n = p.name.lower()
            if any(k in n for k in ["class_map", "label_map", "palette", "class", "label"]):
                try:
                    if p.suffix.lower() == ".json":
                        data = json.loads(p.read_text(encoding="utf-8"))
                        if isinstance(data, dict):
                            if "class_map" in data and isinstance(data["class_map"], dict):
                                mapping = {int(k): str(v) for k, v in data["class_map"].items()}
                            elif "label_map" in data and isinstance(data["label_map"], dict):
                                mapping = {int(k): str(v) for k, v in data["label_map"].items()}
                            elif all(str(k).isdigit() for k in data.keys()):
                                mapping = {int(k): str(v) for k, v in data.items()}
                    elif p.suffix.lower() in {".csv", ".xlsx"}:
                        df = pd.read_excel(p) if p.suffix.lower() == ".xlsx" else pd.read_csv(p)
                        cols = [c.lower() for c in df.columns]
                        if "value" in cols and ("name" in cols or "label" in cols or "class" in cols):
                            vc = df.columns[cols.index("value")]
                            nc = df.columns[cols.index("name")] if "name" in cols else df.columns[cols.index("label")] if "label" in cols else df.columns[cols.index("class")]
                            mapping = {int(v): str(n) for v, n in zip(df[vc], df[nc])}
                except Exception:
                    pass
            if mapping is not None:
                return mapping, palette
    return mapping, palette


def choose_row(df_s7: pd.DataFrame, zone: str):
    zdf = df_s7[df_s7["Zone"].astype(str).str.upper() == zone].copy()
    for pid in PREF[zone]:
        hit = zdf[zdf["Patch_ID"].astype(str) == pid]
        if hit.empty:
            continue
        row = hit.iloc[0]
        sem = as_local(row.get("Patch_file_y", ""))
        if not sem.exists():
            sem = as_local(row.get("Patch_file_x", ""))
        mask = as_local(row.get("Mask_file", ""))
        over = as_local(row.get("Overlay_file", ""))
        if sem.exists() and mask.exists() and over.exists():
            return row, sem, mask, over
    raise FileNotFoundError(f"No valid patch found for {zone} from preferred/fallback list.")


def main():
    plt.rcParams["font.family"] = "DejaVu Sans"
    for d in [FIG_DIR, BASE_LINUX / "07_figures_main"]:
        d.mkdir(parents=True, exist_ok=True)

    s4 = pd.read_excel(find_table(REQ_TABLES["S4"]))
    s5 = pd.read_excel(find_table(REQ_TABLES["S5"]))
    s6 = pd.read_excel(find_table(REQ_TABLES["S6"]))
    s7 = pd.read_excel(find_table(REQ_TABLES["S7"]))
    _ = (s4, s5, s6)

    cmap_map, _palette = load_class_mapping(BASE_WIN)

    zones = ["Z1", "Z2", "Z3", "Z4"]
    selected = []
    mask_checks = []

    for zone in zones:
        row, sem_p, mask_p, over_p = choose_row(s7, zone)
        mask_arr = np.array(Image.open(mask_p))
        u = np.unique(mask_arr)
        mask_checks.append({
            "Zone": zone,
            "Patch_ID": row.get("Patch_ID"),
            "Mask_file": str(mask_p),
            "shape": str(mask_arr.shape),
            "min": int(mask_arr.min()),
            "max": int(mask_arr.max()),
            "unique_values": ", ".join(map(str, u.tolist())),
        })
        selected.append((zone, row, sem_p, mask_p, over_p, mask_arr, u))

    mc_df = pd.DataFrame(mask_checks)
    out_check_win = FIG_DIR / "Figure4_selected_mask_check.xlsx"
    out_check_local = BASE_LINUX / "07_figures_main" / "Figure4_selected_mask_check.xlsx"
    mc_df.to_excel(out_check_local, index=False)

    all_vals = sorted(set(np.concatenate([it[5].ravel() for it in selected]).tolist()))
    n = max(len(all_vals), 1)
    colors = plt.cm.tab10(np.linspace(0, 1, max(n, 3)))[:n]
    cmap = ListedColormap(colors)
    boundaries = np.array(all_vals + [all_vals[-1] + 1]) - 0.5 if all_vals else np.array([-0.5, 0.5])
    norm = BoundaryNorm(boundaries, cmap.N)

    fig, axes = plt.subplots(4, 3, figsize=(12, 14), constrained_layout=True)
    col_titles = ["Original SEM patch", "Semantic mask", "SEM + mask overlay"]
    for j, t in enumerate(col_titles):
        axes[0, j].set_title(t, fontsize=11)

    for i, (zone, row, sem_p, mask_p, over_p, mask_arr, uvals) in enumerate(selected):
        sem = np.array(Image.open(sem_p))
        over = np.array(Image.open(over_p))
        axes[i, 0].imshow(sem, cmap="gray")
        axes[i, 1].imshow(mask_arr, cmap=cmap, norm=norm, interpolation="nearest")
        axes[i, 2].imshow(over)
        for j in range(3):
            axes[i, j].axis("off")

        axes[i, 0].text(-0.08, 0.5, zone, transform=axes[i, 0].transAxes, va="center", ha="right", fontsize=12, fontweight="bold")
        label = f"{row.get('Patch_ID')}, DSI = {float(row.get('DSI_semantic')):.3f}"
        for j in range(3):
            axes[i, j].text(0.02, 0.02, label, transform=axes[i, j].transAxes, fontsize=8,
                            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"))

    legend_items = []
    for idx, v in enumerate(all_vals):
        if cmap_map and int(v) in cmap_map:
            txt = f"{int(v)}: {cmap_map[int(v)]}"
        else:
            txt = f"Mask value {int(v)}"
        legend_items.append(Patch(facecolor=colors[idx], edgecolor='none', label=txt))
    if legend_items:
        fig.legend(handles=legend_items, loc="lower center", ncol=min(5, len(legend_items)), fontsize=8)

    fig.suptitle("Figure 4. Representative SEM patches and corresponding semantic masks from different barrel zones.", fontsize=12)

    out_base_local = BASE_LINUX / "07_figures_main" / "Figure_4_SEM_mask_comparison"
    fig.savefig(str(out_base_local.with_suffix(".png")), dpi=600, facecolor="white")
    fig.savefig(str(out_base_local.with_suffix(".tif")), dpi=600, facecolor="white")
    fig.savefig(str(out_base_local.with_suffix(".pdf")), dpi=600, facecolor="white")
    plt.close(fig)

    info_path = BASE_LINUX / "07_figures_main" / "Figure_4_selected_patch_info.txt"
    with open(info_path, "w", encoding="utf-8") as f:
        for zone, row, sem_p, mask_p, over_p, _m, _u in selected:
            f.write(f"[{zone}]\n")
            f.write(f"Patch_ID: {row.get('Patch_ID')}\n")
            f.write(f"Image_ID: {row.get('Image_ID', 'N/A')}\n")
            f.write(f"Patch_row: {row.get('Patch_row', 'N/A')}\n")
            f.write(f"Patch_col: {row.get('Patch_col', 'N/A')}\n")
            f.write(f"DSI_semantic: {row.get('DSI_semantic')}\n")
            f.write(f"Patch_file: {sem_p}\n")
            f.write(f"Mask_file: {mask_p}\n")
            f.write(f"Overlay_file: {over_p}\n")
            uu = np.unique(np.array(Image.open(mask_p))).tolist()
            f.write(f"mask unique values: {uu}\n\n")

    print("Done.")
    print(f"Mask check: {out_check_local} (Windows target: {out_check_win})")
    print(f"Figure outputs: {out_base_local.with_suffix('.png')}, {out_base_local.with_suffix('.tif')}, {out_base_local.with_suffix('.pdf')}")
    print(f"Patch info: {info_path}")


if __name__ == "__main__":
    main()
