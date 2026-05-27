import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import spearmanr

ZONE_CANDIDATES = ["Zone", "zone", "Barrel_zone", "region", "Zone_label"]
TARGET_ZONES = ["Z1", "Z2", "Z3", "Z4"]

SCHEMES = [
    ("Primary DSI", ["semantic", "mean"], ["semantic", "std"]),
    ("Equal-weight DSI", ["equal", "mean"], ["equal", "std"]),
    ("Crack-enhanced DSI", ["crack", "enhanced", "mean"], ["crack", "enhanced", "std"]),
    ("Wear-enhanced DSI", ["wear", "enhanced", "mean"], ["wear", "enhanced", "std"]),
]

FORBIDDEN_TOKENS = {
    "image", "count", "patch", "rank", "std", "sem", "n", "min", "max"
}
FORBIDDEN_EXACT = {
    "image count", "patch count", "rank semantic", "rank equal", "rank crack enhanced", "rank wear enhanced",
    "image_count", "patch_count", "rank_semantic", "rank_equal", "rank_crack_enhanced", "rank_wear_enhanced",
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def find_zone_col(df: pd.DataFrame):
    lower = {c.lower(): c for c in df.columns}
    for c in ZONE_CANDIDATES:
        if c in df.columns:
            return c
    for c in ZONE_CANDIDATES:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def detect_long(df: pd.DataFrame, zone_col: str) -> bool:
    low = {c.lower(): c for c in df.columns}
    has_scheme = any(k in low for k in ["scheme", "dsi_scheme", "weight_scheme", "scenario"])
    has_value = any(k in low for k in ["mean_dsi", "dsi", "value", "dsi_mean"])
    return zone_col is not None and has_scheme and has_value


def match_col(columns, required_tokens, disallow_tokens=None):
    disallow_tokens = disallow_tokens or set()
    candidates = []
    for c in columns:
        nc = norm(c)
        tokens = set(nc.split())
        if all(tok in tokens for tok in required_tokens):
            if any(tok in tokens for tok in disallow_tokens):
                continue
            if nc in FORBIDDEN_EXACT:
                continue
            candidates.append(c)
    if not candidates:
        return None
    # Prefer exact-like names
    candidates = sorted(candidates, key=lambda x: len(norm(x)))
    return candidates[0]


def build_long(df: pd.DataFrame) -> pd.DataFrame:
    zone_col = find_zone_col(df)
    if zone_col is None:
        raise ValueError(f"Cannot find zone column from {ZONE_CANDIDATES}")

    # Long format path
    if detect_long(df, zone_col):
        low = {c.lower(): c for c in df.columns}
        scheme_col = next(low[k] for k in low if k in {"scheme", "dsi_scheme", "weight_scheme", "scenario"})
        value_col = next(low[k] for k in low if k in {"mean_dsi", "dsi", "value", "dsi_mean"})

        mapping = {
            "primary dsi": "Primary DSI",
            "equal weight dsi": "Equal-weight DSI",
            "equal-weight dsi": "Equal-weight DSI",
            "crack enhanced dsi": "Crack-enhanced DSI",
            "crack-enhanced dsi": "Crack-enhanced DSI",
            "wear enhanced dsi": "Wear-enhanced DSI",
            "wear-enhanced dsi": "Wear-enhanced DSI",
        }

        long_df = pd.DataFrame({
            "Zone": df[zone_col].astype(str).str.strip(),
            "DSI_scheme": df[scheme_col].astype(str).map(lambda x: mapping.get(norm(x), x.replace("_", " "))),
            "Mean_DSI": pd.to_numeric(df[value_col], errors="coerce"),
        })
        long_df = long_df[long_df["DSI_scheme"].isin([s[0] for s in SCHEMES])]
        return long_df

    # Wide format strict extraction: only 4 target mean columns (+ optional std)
    cols = list(df.columns)
    scheme_data = {}
    for scheme_name, mean_tokens, std_tokens in SCHEMES:
        mean_col = match_col(cols, mean_tokens, disallow_tokens={"std", "sem", "count", "rank", "min", "max", "n"})
        std_col = match_col(cols, std_tokens, disallow_tokens={"mean", "sem", "count", "rank", "min", "max", "n"})
        scheme_data[scheme_name] = (mean_col, std_col)

    rows = []
    for _, r in df.iterrows():
        zone = str(r[zone_col]).strip()
        if zone not in TARGET_ZONES:
            continue
        for scheme_name, (mcol, scol) in scheme_data.items():
            if mcol is None:
                continue
            mean_val = pd.to_numeric(r[mcol], errors="coerce")
            std_val = pd.to_numeric(r[scol], errors="coerce") if scol else np.nan
            if pd.notna(mean_val):
                rows.append({"Zone": zone, "DSI_scheme": scheme_name, "Mean_DSI": mean_val, "Std_DSI": std_val})

    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError("No valid mean DSI values found using strict 4-scheme matching.")
    return out


def main():
    repo_root = Path(__file__).resolve().parents[1]
    base = Path("E:/Barrel_SEM_Z1_Z4_New")
    if not base.exists():
        base = repo_root

    in_file = base / "05_tables" / "S9_DSI_sensitivity_Z1_Z4.xlsx"
    out_dir = base / "07_figures_main"
    out_dir.mkdir(parents=True, exist_ok=True)

    df_raw = pd.read_excel(in_file)
    long_df = build_long(df_raw)

    long_df["Zone"] = long_df["Zone"].astype(str).str.strip()
    long_df = long_df[long_df["Zone"].isin(TARGET_ZONES)].copy()
    long_df["Mean_DSI"] = pd.to_numeric(long_df["Mean_DSI"], errors="coerce")
    if "Std_DSI" not in long_df.columns:
        long_df["Std_DSI"] = np.nan
    long_df["Std_DSI"] = pd.to_numeric(long_df["Std_DSI"], errors="coerce")
    long_df = long_df.dropna(subset=["Mean_DSI"])

    scheme_order = [s[0] for s in SCHEMES]
    pivot_mean = long_df.pivot_table(index="Zone", columns="DSI_scheme", values="Mean_DSI", aggfunc="mean").reindex(TARGET_ZONES).reindex(columns=scheme_order)
    pivot_std = long_df.pivot_table(index="Zone", columns="DSI_scheme", values="Std_DSI", aggfunc="mean").reindex(TARGET_ZONES).reindex(columns=scheme_order)

    stats_rows = []
    zone_numeric = np.arange(1, 5)
    for scheme in scheme_order:
        vals = pivot_mean[scheme]
        rank_order = " < ".join(vals.dropna().sort_values().index.tolist())
        monotonic = bool(vals.notna().all() and (vals.values[0] < vals.values[1] < vals.values[2] < vals.values[3]))
        if vals.notna().all():
            r, p = spearmanr(zone_numeric, vals.values)
        else:
            r, p = (np.nan, np.nan)
        stats_rows.append({
            "scheme": scheme,
            "DSI_Z1": vals.get("Z1", np.nan),
            "DSI_Z2": vals.get("Z2", np.nan),
            "DSI_Z3": vals.get("Z3", np.nan),
            "DSI_Z4": vals.get("Z4", np.nan),
            "rank_order": rank_order,
            "monotonic_Z1_to_Z4": monotonic,
            "spearman_r": r,
            "spearman_p": p,
        })
    stats_df = pd.DataFrame(stats_rows)

    zone_var = pivot_mean.apply(lambda row: pd.Series({
        "mean_across_schemes": row.mean(skipna=True),
        "std_across_schemes": row.std(skipna=True, ddof=1),
        "min_across_schemes": row.min(skipna=True),
        "max_across_schemes": row.max(skipna=True),
        "CV_across_schemes": row.std(skipna=True, ddof=1) / row.mean(skipna=True) if row.mean(skipna=True) != 0 else np.nan,
    }), axis=1).reset_index().rename(columns={"index": "Zone"})

    long_plot = pivot_mean.reset_index().melt(id_vars="Zone", var_name="DSI_scheme", value_name="Mean_DSI").dropna()

    plt.rcParams["font.family"] = ["Arial", "DejaVu Sans"]
    fig, ax = plt.subplots(figsize=(8.2, 5.2), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    x = np.arange(len(TARGET_ZONES))
    n = len(scheme_order)
    width = 0.18
    colors = ["#4C78A8", "#F58518", "#54A24B", "#B279A2"]

    y_upper_candidates = []
    for i, scheme in enumerate(scheme_order):
        y = pivot_mean[scheme].values
        e = pivot_std[scheme].values if scheme in pivot_std.columns else np.array([np.nan] * len(y))
        pos = x + (i - (n - 1) / 2) * width
        bars = ax.bar(pos, y, width=width, color=colors[i], label=scheme, edgecolor="#333333", linewidth=0.6)
        if np.isfinite(e).any():
            ax.errorbar(pos, y, yerr=e, fmt="none", ecolor="#333333", elinewidth=0.8, capsize=3)
            y_upper_candidates.extend(list(np.array(y) + np.nan_to_num(e, nan=0.0)))
        else:
            y_upper_candidates.extend(list(y))

        label_offset = max(0.002, np.nanmax(pivot_mean.values) * 0.012)
        for b, val in zip(bars, y):
            if pd.notna(val):
                ax.text(b.get_x() + b.get_width() / 2, val + label_offset, f"{val:.3f}", ha="center", va="bottom", fontsize=8)

    ymax_base = np.nanmax(y_upper_candidates) if len(y_upper_candidates) else np.nanmax(pivot_mean.values)
    has_std = np.isfinite(pivot_std.values).any()
    ymax = ymax_base * (1.15 if has_std else 1.20)
    ax.set_ylim(0, ymax)

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

    stats_df.to_excel(out_dir / "Figure7_DSI_sensitivity_statistics.xlsx", index=False)
    zone_var.to_excel(out_dir / "Figure7_DSI_zone_variability.xlsx", index=False)
    long_plot.to_excel(out_dir / "Figure7_DSI_sensitivity_long_table.xlsx", index=False)

    print("Done")
    print(png)
    print(tif)
    print(pdf)


if __name__ == "__main__":
    main()
