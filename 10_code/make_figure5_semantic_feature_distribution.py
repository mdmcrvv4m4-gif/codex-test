import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import kruskal


logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')


def normalize_col(name: str) -> str:
    return str(name).strip().lower()


def find_column(df: pd.DataFrame, candidates):
    norm_map = {normalize_col(c): c for c in df.columns}
    for c in candidates:
        if normalize_col(c) in norm_map:
            return norm_map[normalize_col(c)]
    return None


def find_feature_columns(df: pd.DataFrame, preferred_features):
    norm_map = {normalize_col(c): c for c in df.columns}
    found = []
    missing = []
    for feat in preferred_features:
        col = norm_map.get(normalize_col(feat))
        if col is not None:
            found.append(col)
        else:
            missing.append(feat)
    return found, missing


def supplement_features(df: pd.DataFrame, selected, n_target=6):
    keywords = ["fraction", "density", "area", "length", "network", "wear", "crack", "severe"]
    selected_set = set(selected)
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

    scored = []
    for c in numeric_cols:
        if c in selected_set:
            continue
        lc = normalize_col(c)
        score = sum(1 for k in keywords if k in lc)
        if score > 0:
            scored.append((score, c))

    scored.sort(key=lambda x: (-x[0], x[1]))
    for _, c in scored:
        selected.append(c)
        if len(selected) >= n_target:
            break
    return selected[:n_target]


def pretty_feature_name(feature):
    return feature.replace("_", " ").strip().title()


def main():
    root = Path(__file__).resolve().parents[1]
    table_dir = root / "05_tables"
    output_dir = root / "07_figures_main"
    output_dir.mkdir(parents=True, exist_ok=True)

    s6_path = table_dir / "S6_semantic_features_Z1_Z4.xlsx"
    s7_path = table_dir / "S7_feature_table_with_semantic_DSI_Z1_Z4.xlsx"

    preferred_features = [
        "crack_area_fraction",
        "wear_area_fraction",
        "severe_damage_area_fraction",
        "crack_length_density",
        "crack_network_density",
        "wear_mark_density",
    ]

    if s6_path.exists():
        data_path = s6_path
        df = pd.read_excel(s6_path)
        logging.info(f"Loaded S6 table: {s6_path}")
    elif s7_path.exists():
        data_path = s7_path
        df = pd.read_excel(s7_path)
        logging.warning("S6 not found; fallback to S7.")
    else:
        raise FileNotFoundError(f"Neither S6 nor S7 exists under {table_dir}")

    zone_col = find_column(df, ["Zone", "zone", "Barrel_zone", "region", "Zone_label"])
    if zone_col is None:
        if data_path == s6_path and s7_path.exists():
            logging.warning("Zone column not found in S6; trying S7.")
            df = pd.read_excel(s7_path)
            zone_col = find_column(df, ["Zone", "zone", "Barrel_zone", "region", "Zone_label"])
        if zone_col is None:
            raise ValueError("No zone column found in S6/S7.")

    df[zone_col] = df[zone_col].astype(str).str.strip()
    df = df[df[zone_col].isin(["Z1", "Z2", "Z3", "Z4"])].copy()
    if df.empty:
        raise ValueError("No rows for Z1-Z4 after filtering.")

    found_feats, missing_feats = find_feature_columns(df, preferred_features)
    for feat in missing_feats:
        logging.warning(f"Preferred feature missing and skipped: {feat}")

    if len(found_feats) < 6:
        found_feats = supplement_features(df, found_feats, 6)
        logging.info(f"Supplemented features to 6: {found_feats}")

    if len(found_feats) == 0:
        raise ValueError("No usable feature columns found.")

    found_feats = found_feats[:6]

    patch_col = find_column(df, ["Patch_ID", "patch_id", "PatchID", "patchid", "id", "ID"])
    if patch_col is None:
        df["Patch_ID"] = [f"patch_{i+1}" for i in range(len(df))]
        patch_col = "Patch_ID"

    records = []
    stats_rows = []

    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(2, 3, figsize=(16, 9), dpi=600, facecolor="white")
    axes = axes.flatten()
    zone_order = ["Z1", "Z2", "Z3", "Z4"]

    title_overrides = {
        "crack_area_fraction": "Crack area fraction",
        "wear_area_fraction": "Wear area fraction",
        "severe_damage_area_fraction": "Severe damage area fraction",
        "crack_length_density": "Crack length density",
        "crack_network_density": "Crack network density",
        "wear_mark_density": "Wear mark density",
    }

    letters = list("abcdef")

    for i, feature in enumerate(found_feats):
        ax = axes[i]
        values_by_zone = []

        for z in zone_order:
            vals = pd.to_numeric(df.loc[df[zone_col] == z, feature], errors="coerce").dropna()
            values_by_zone.append(vals.values)

            for idx, v in df.loc[df[zone_col] == z, [patch_col, feature]].dropna().iterrows():
                records.append({"Patch_ID": v[patch_col], "Zone": z, "feature": feature, "value": float(v[feature])})

        # Boxplot
        bp = ax.boxplot(values_by_zone, positions=np.arange(1, 5), widths=0.5, patch_artist=True, showfliers=False)
        for patch in bp['boxes']:
            patch.set(facecolor="#dce6f2", edgecolor="#4d4d4d", linewidth=1.0)
        for median in bp['medians']:
            median.set(color="#c00000", linewidth=1.2)
        for whisker in bp['whiskers']:
            whisker.set(color="#666666", linewidth=0.9)
        for cap in bp['caps']:
            cap.set(color="#666666", linewidth=0.9)

        # Jitter points
        rng = np.random.default_rng(42 + i)
        for x, vals in enumerate(values_by_zone, start=1):
            if len(vals) == 0:
                continue
            xj = x + rng.uniform(-0.12, 0.12, size=len(vals))
            ax.scatter(xj, vals, s=16, alpha=0.75, color="#1f77b4", edgecolors="none")

        # Kruskal-Wallis
        valid_groups = [g for g in values_by_zone if len(g) > 0]
        if len(valid_groups) >= 2:
            h_stat, p_val = kruskal(*valid_groups)
        else:
            h_stat, p_val = np.nan, np.nan

        ax.text(0.98, 0.97, f"Kruskal-Wallis p = {p_val:.3g}" if pd.notna(p_val) else "Kruskal-Wallis p = NA",
                transform=ax.transAxes, ha="right", va="top", fontsize=9)

        fname_lc = normalize_col(feature)
        display_name = title_overrides.get(fname_lc, pretty_feature_name(feature))
        ax.set_title(f"({letters[i]}) {display_name}", fontsize=11)
        ax.set_xticks([1, 2, 3, 4])
        ax.set_xticklabels(zone_order)
        ax.set_xlabel("Zone")
        ax.set_ylabel(feature)
        ax.grid(axis="y", linestyle="--", alpha=0.3)

        row = {"feature": feature, "kruskal_H": h_stat, "kruskal_p": p_val}
        for z, vals in zip(zone_order, values_by_zone):
            row[f"n_{z}"] = int(len(vals))
            row[f"median_{z}"] = float(np.nanmedian(vals)) if len(vals) else np.nan
            row[f"mean_{z}"] = float(np.nanmean(vals)) if len(vals) else np.nan
            row[f"std_{z}"] = float(np.nanstd(vals, ddof=1)) if len(vals) > 1 else np.nan
        stats_rows.append(row)

    for j in range(len(found_feats), 6):
        axes[j].axis("off")

    fig.suptitle("Figure 5. Zone-wise distributions of semantic damage features.", fontsize=14, y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.97])

    out_png = output_dir / "Figure_5_semantic_feature_distribution.png"
    out_tif = output_dir / "Figure_5_semantic_feature_distribution.tif"
    out_pdf = output_dir / "Figure_5_semantic_feature_distribution.pdf"

    fig.savefig(out_png, dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(out_tif, dpi=600, bbox_inches="tight", facecolor="white")
    fig.savefig(out_pdf, dpi=600, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    long_df = pd.DataFrame(records, columns=["Patch_ID", "Zone", "feature", "value"])
    stats_df = pd.DataFrame(stats_rows)

    long_path = output_dir / "Figure5_semantic_feature_long_table.xlsx"
    stats_path = output_dir / "Figure5_semantic_feature_statistics.xlsx"

    long_df.to_excel(long_path, index=False)
    stats_df.to_excel(stats_path, index=False)

    logging.info(f"Saved figure files to: {output_dir}")
    logging.info(f"Saved statistics: {stats_path}")
    logging.info(f"Saved long table: {long_path}")


if __name__ == "__main__":
    main()
