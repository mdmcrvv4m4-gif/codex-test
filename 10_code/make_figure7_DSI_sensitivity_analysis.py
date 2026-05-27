import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

ZONE_CANDIDATES = ["Zone", "zone", "Barrel_zone", "region", "Zone_label"]
TARGET_ZONES = ["Z1", "Z2", "Z3", "Z4"]
SCHEME_PREFERRED = [
    "Primary DSI",
    "Equal-weight DSI",
    "Crack-enhanced DSI",
    "Wear-enhanced DSI",
]
SCHEME_ALIAS = {
    "primary dsi": "Primary DSI",
    "primary_dsi": "Primary DSI",
    "equal-weight dsi": "Equal-weight DSI",
    "equal weight dsi": "Equal-weight DSI",
    "equal_weight_dsi": "Equal-weight DSI",
    "crack-enhanced dsi": "Crack-enhanced DSI",
    "crack enhanced dsi": "Crack-enhanced DSI",
    "crack_enhanced_dsi": "Crack-enhanced DSI",
    "wear-enhanced dsi": "Wear-enhanced DSI",
    "wear enhanced dsi": "Wear-enhanced DSI",
    "wear_enhanced_dsi": "Wear-enhanced DSI",
}


def _normalize_token(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip()).lower().replace("-", " ")


def normalize_scheme_name(raw: str) -> str:
    txt = str(raw).strip()
    key = txt.lower().strip()
    key = key.replace("-", " ")
    key = re.sub(r"\s+", " ", key)
    key_underscore = key.replace(" ", "_")
    if key in SCHEME_ALIAS:
        return SCHEME_ALIAS[key]
    if key_underscore in SCHEME_ALIAS:
        return SCHEME_ALIAS[key_underscore]
    return txt.replace("_", " ").strip()


def find_col(df: pd.DataFrame, candidates):
    lower_map = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c in df.columns:
            return c
    for c in candidates:
        if c.lower() in lower_map:
            return lower_map[c.lower()]
    return None


def detect_long_format(df: pd.DataFrame):
    zone_col = find_col(df, ZONE_CANDIDATES)
    if zone_col is None:
        return False
    low = {c.lower(): c for c in df.columns}
    scheme_col = next((low[k] for k in low if k in {"scheme", "dsi_scheme", "weight_scheme", "scenario"}), None)
    value_col = next((low[k] for k in low if k in {"mean_dsi", "dsi", "value", "dsi_mean"}), None)
    return scheme_col is not None and value_col is not None


def to_long_table(df: pd.DataFrame) -> pd.DataFrame:
    zone_col = find_col(df, ZONE_CANDIDATES)
    if zone_col is None:
        raise ValueError(f"Cannot find zone column. Expected one of: {ZONE_CANDIDATES}")

    if detect_long_format(df):
        low = {c.lower(): c for c in df.columns}
        scheme_col = next(low[k] for k in low if k in {"scheme", "dsi_scheme", "weight_scheme", "scenario"})
        value_col = next(low[k] for k in low if k in {"mean_dsi", "dsi", "value", "dsi_mean"})
        out = pd.DataFrame(
            {
                "Zone": df[zone_col].astype(str).str.strip(),
                "DSI_scheme": df[scheme_col].astype(str).map(normalize_scheme_name),
                "Mean_DSI": pd.to_numeric(df[value_col], errors="coerce"),
            }
        )
        return out

    wide_cols = [c for c in df.columns if c != zone_col]
    wide_numeric = [c for c in wide_cols if pd.api.types.is_numeric_dtype(df[c]) or df[c].dtype == object]
    long_df = df.melt(id_vars=[zone_col], value_vars=wide_numeric, var_name="DSI_scheme", value_name="Mean_DSI")
    long_df = long_df.rename(columns={zone_col: "Zone"})
    long_df["Zone"] = long_df["Zone"].astype(str).str.strip()
    long_df["DSI_scheme"] = long_df["DSI_scheme"].astype(str).map(normalize_scheme_name)
    long_df["Mean_DSI"] = pd.to_numeric(long_df["Mean_DSI"], errors="coerce")
    return long_df


def main():
    repo_root = Path(__file__).resolve().parents[1]
    base = Path("E:/Barrel_SEM_Z1_Z4_New")
    if not base.exists():
        base = repo_root

    in_file = base / "05_tables" / "S9_DSI_sensitivity_Z1_Z4.xlsx"
    out_dir = base / "07_figures_main"
    out_dir.mkdir(parents=True, exist_ok=True)

    df_raw = pd.read_excel(in_file)
    long_df = to_long_table(df_raw)
    long_df = long_df.dropna(subset=["Mean_DSI"]).copy()
    long_df = long_df[long_df["Zone"].isin(TARGET_ZONES)].copy()

    if long_df.empty:
        raise ValueError("No valid rows found for zones Z1-Z4.")

    preferred_present = [s for s in SCHEME_PREFERRED if s in set(long_df["DSI_scheme"])]
    if preferred_present:
        long_df = long_df[long_df["DSI_scheme"].isin(preferred_present)].copy()
        scheme_order = preferred_present
    else:
        scheme_order = sorted(long_df["DSI_scheme"].dropna().unique().tolist())

    pivot = (
        long_df.pivot_table(index="Zone", columns="DSI_scheme", values="Mean_DSI", aggfunc="mean")
        .reindex(TARGET_ZONES)
        .reindex(columns=scheme_order)
    )

    stats_rows = []
    zone_numeric = np.arange(1, len(TARGET_ZONES) + 1)
    for scheme in scheme_order:
        vals = pivot[scheme]
        valid = vals.dropna()
        rank_order = " < ".join(valid.sort_values().index.tolist()) if not valid.empty else ""
        monotonic = bool((vals.values[0] < vals.values[1] < vals.values[2] < vals.values[3])) if vals.notna().all() else False
        if vals.notna().all():
            r, p = spearmanr(zone_numeric, vals.values)
        else:
            r, p = (np.nan, np.nan)
        stats_rows.append(
            {
                "scheme": scheme,
                "DSI_Z1": vals.get("Z1", np.nan),
                "DSI_Z2": vals.get("Z2", np.nan),
                "DSI_Z3": vals.get("Z3", np.nan),
                "DSI_Z4": vals.get("Z4", np.nan),
                "rank_order": rank_order,
                "monotonic_Z1_to_Z4": monotonic,
                "spearman_r": r,
                "spearman_p": p,
            }
        )

    stats_df = pd.DataFrame(stats_rows)

    zone_var = (
        pivot.apply(
            lambda row: pd.Series(
                {
                    "mean_across_schemes": row.mean(skipna=True),
                    "std_across_schemes": row.std(skipna=True, ddof=1),
                    "min_across_schemes": row.min(skipna=True),
                    "max_across_schemes": row.max(skipna=True),
                    "CV_across_schemes": (row.std(skipna=True, ddof=1) / row.mean(skipna=True)) if row.mean(skipna=True) != 0 else np.nan,
                }
            ),
            axis=1,
        )
        .reset_index()
        .rename(columns={"index": "Zone"})
    )

    long_plot = (
        pivot.reset_index()
        .melt(id_vars="Zone", var_name="DSI_scheme", value_name="Mean_DSI")
        .dropna(subset=["Mean_DSI"])
        .copy()
    )

    plt.rcParams["font.family"] = ["Arial", "DejaVu Sans"]
    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    x = np.arange(len(TARGET_ZONES))
    n = len(scheme_order)
    width = 0.18 if n >= 4 else 0.22
    colors = ["#4C78A8", "#F58518", "#54A24B", "#B279A2", "#9D755D", "#BAB0AC"]

    for i, scheme in enumerate(scheme_order):
        y = pivot[scheme].values
        pos = x + (i - (n - 1) / 2) * width
        bars = ax.bar(pos, y, width=width, label=scheme, color=colors[i % len(colors)], edgecolor="#333333", linewidth=0.6)
        for b, val in zip(bars, y):
            if pd.notna(val):
                ax.text(b.get_x() + b.get_width() / 2, val + max(0.002, np.nanmax(pivot.values) * 0.012), f"{val:.3f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(TARGET_ZONES)
    ax.set_xlabel("Zone")
    ax.set_ylabel("Mean semantic DSI")
    ax.grid(axis="y", linestyle="--", alpha=0.35, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.legend(loc="upper left", fontsize=8, frameon=True, edgecolor="#CCCCCC")
    fig.tight_layout()

    png = out_dir / "Figure_7_DSI_sensitivity_analysis.png"
    tif = out_dir / "Figure_7_DSI_sensitivity_analysis.tif"
    pdf = out_dir / "Figure_7_DSI_sensitivity_analysis.pdf"
    fig.savefig(png, dpi=600, facecolor="white")
    fig.savefig(tif, dpi=600, facecolor="white")
    fig.savefig(pdf, dpi=600, facecolor="white")
    plt.close(fig)

    stats_path = out_dir / "Figure7_DSI_sensitivity_statistics.xlsx"
    zone_var_path = out_dir / "Figure7_DSI_zone_variability.xlsx"
    long_table_path = out_dir / "Figure7_DSI_sensitivity_long_table.xlsx"

    stats_df.to_excel(stats_path, index=False)
    zone_var.to_excel(zone_var_path, index=False)
    long_plot.to_excel(long_table_path, index=False)

    print("Done.")
    print(f"Figure PNG: {png}")
    print(f"Figure TIF: {tif}")
    print(f"Figure PDF: {pdf}")
    print(f"Stats table: {stats_path}")
    print(f"Zone variability: {zone_var_path}")
    print(f"Long table: {long_table_path}")


if __name__ == "__main__":
    main()
