import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import kruskal, mannwhitneyu


ZONE_CANDIDATES = ["Zone", "zone", "Barrel_zone", "region", "Zone_label"]
DSI_CANDIDATES = ["DSI_semantic", "semantic_DSI", "Semantic_DSI", "dsi_semantic", "DSI", "mean_DSI"]
ZONE_ORDER = ["Z1", "Z2", "Z3", "Z4"]


def find_col(df, candidates):
    cols_lower = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c in df.columns:
            return c
    for c in candidates:
        if c.lower() in cols_lower:
            return cols_lower[c.lower()]
    return None


def benjamini_hochberg(pvals):
    pvals = np.asarray(pvals, dtype=float)
    n = len(pvals)
    if n == 0:
        return np.array([])
    order = np.argsort(pvals)
    ranked = pvals[order]
    adj = ranked * n / (np.arange(1, n + 1))
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    out = np.empty(n)
    out[order] = adj
    return out


def compact_letters(pmat, groups, alpha=0.05):
    means = [np.nanmean(g) for g in groups]
    order = np.argsort(means)[::-1]
    letters = [""] * len(groups)
    letter_sets = []
    alphabet = [chr(i) for i in range(97, 123)]

    for idx in order:
        placed = False
        for li, members in enumerate(letter_sets):
            ok = True
            for m in members:
                if pmat[min(idx, m), max(idx, m)] < alpha:
                    ok = False
                    break
            if ok:
                members.append(idx)
                letters[idx] += alphabet[li]
                placed = True
        if not placed:
            letter_sets.append([idx])
            letters[idx] += alphabet[len(letter_sets) - 1]

    return letters


def summarize(df_long):
    g = df_long.groupby("Zone")["DSI_semantic"]
    stats = g.agg(n="count", mean="mean", median="median", std="std", min="min", max="max")
    stats["sem"] = stats["std"] / np.sqrt(stats["n"])
    stats["q1"] = g.quantile(0.25)
    stats["q3"] = g.quantile(0.75)
    return stats.reset_index()


def build_long_from_patch(df):
    zc = find_col(df, ZONE_CANDIDATES)
    dc = find_col(df, DSI_CANDIDATES)
    if zc is None or dc is None:
        raise ValueError("Patch-level data missing Zone/DSI columns")

    patch_col = "Patch_ID" if "Patch_ID" in df.columns else None
    out = pd.DataFrame({
        "Patch_ID": df[patch_col] if patch_col else [f"patch_{i+1}" for i in range(len(df))],
        "Zone": df[zc].astype(str).str.strip(),
        "DSI_semantic": pd.to_numeric(df[dc], errors="coerce"),
    })
    out = out[out["Zone"].isin(ZONE_ORDER)].dropna(subset=["DSI_semantic"]).copy()
    return out


def detect_patch_level(df):
    zc = find_col(df, ZONE_CANDIDATES)
    dc = find_col(df, DSI_CANDIDATES)
    has_patch_id = any(c.lower() == "patch_id".lower() for c in df.columns)
    summary_like = {"mean", "std", "sem", "n", "median", "q1", "q3"}
    columns_lower = {c.lower() for c in df.columns}
    if zc and dc and has_patch_id:
        return True
    if zc and dc and not summary_like.intersection(columns_lower):
        return True
    return False


def main():
    repo_root = Path(__file__).resolve().parents[1]
    base = Path("E:/Barrel_SEM_Z1_Z4_New")
    if not base.exists():
        base = repo_root

    s8 = base / "05_tables" / "S8_DSI_by_zone_Z1_Z4.xlsx"
    s7 = base / "05_tables" / "S7_feature_table_with_semantic_DSI_Z1_Z4.xlsx"
    out_dir = base / "07_figures_main"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading S8: {s8}")
    df8 = pd.read_excel(s8)

    use_patch_s8 = detect_patch_level(df8)
    print(f"S8 detected as patch-level: {use_patch_s8}")

    source_for_tests = "S8"
    used_summary_mode = False

    if use_patch_s8:
        df_long = build_long_from_patch(df8)
    else:
        used_summary_mode = True
        print("S8 appears summary-level. Loading S7 patch-level for significance tests and long table.")
        df7 = pd.read_excel(s7)
        df_long = build_long_from_patch(df7)
        source_for_tests = "S7"

    if df_long.empty:
        raise ValueError("No valid patch-level data found for Z1-Z4.")

    stats_df = summarize(df_long)
    stats_df["Zone"] = pd.Categorical(stats_df["Zone"], categories=ZONE_ORDER, ordered=True)
    stats_df = stats_df.sort_values("Zone").reset_index(drop=True)

    groups = [df_long.loc[df_long["Zone"] == z, "DSI_semantic"].values for z in ZONE_ORDER]
    valid = [g for g in groups if len(g) > 0]
    if len(valid) < 2:
        raise ValueError("Not enough groups with data for statistical testing.")

    h_stat, p_kw = kruskal(*valid)

    pairs = []
    pvals = []
    pmat = np.ones((4, 4), dtype=float)
    for i in range(4):
        for j in range(i + 1, 4):
            gi = groups[i]
            gj = groups[j]
            if len(gi) == 0 or len(gj) == 0:
                p = np.nan
            else:
                _, p = mannwhitneyu(gi, gj, alternative="two-sided")
            pairs.append((ZONE_ORDER[i], ZONE_ORDER[j], p))
            pvals.append(1.0 if np.isnan(p) else p)

    p_adj = benjamini_hochberg(pvals)
    pair_rows = []
    k = 0
    for i in range(4):
        for j in range(i + 1, 4):
            padj = float(p_adj[k])
            pmat[i, j] = padj
            pmat[j, i] = padj
            pair_rows.append({
                "group1": ZONE_ORDER[i],
                "group2": ZONE_ORDER[j],
                "p_raw": pairs[k][2],
                "p_adj_BH": padj,
                "significant": bool(padj < 0.05),
            })
            k += 1

    letters = compact_letters(pmat, groups, alpha=0.05)
    stats_df["letter"] = letters

    fig, ax = plt.subplots(figsize=(6.2, 4.8), dpi=150)
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    x = np.arange(1, 5)

    if not used_summary_mode:
        data = [df_long.loc[df_long["Zone"] == z, "DSI_semantic"].values for z in ZONE_ORDER]
        bp = ax.boxplot(data, positions=x, widths=0.55, patch_artist=True, showfliers=False)
        for box in bp["boxes"]:
            box.set(facecolor="#DCEAF7", edgecolor="black", linewidth=1.0)
        for key in ["whiskers", "caps", "medians"]:
            for item in bp[key]:
                item.set(color="black", linewidth=1.0)

        rng = np.random.default_rng(42)
        for i, z in enumerate(ZONE_ORDER):
            y = df_long.loc[df_long["Zone"] == z, "DSI_semantic"].values
            jitter = rng.uniform(-0.14, 0.14, size=len(y))
            ax.scatter(np.full(len(y), x[i]) + jitter, y, s=18, alpha=0.55, color="#4C78A8", edgecolors="none")

        ax.scatter(x, stats_df["mean"].values, marker="D", s=40, color="#C00000", zorder=3)
    else:
        means = stats_df["mean"].values
        sems = stats_df["sem"].values
        ax.bar(x, means, width=0.58, color="#DCEAF7", edgecolor="black", linewidth=1.0)
        ax.errorbar(x, means, yerr=sems, fmt="none", ecolor="black", capsize=4, linewidth=1.0)
        ax.scatter(x, means, marker="D", s=40, color="#C00000", zorder=3)

    ymax = np.nanmax(df_long["DSI_semantic"].values)
    ymin = np.nanmin(df_long["DSI_semantic"].values)
    yr = ymax - ymin if ymax > ymin else 1.0

    for i, letter in enumerate(letters):
        zone_max = np.nanmax(df_long.loc[df_long["Zone"] == ZONE_ORDER[i], "DSI_semantic"].values)
        ax.text(x[i], zone_max + 0.06 * yr, letter, ha="center", va="bottom", fontsize=11, fontweight="bold")

    kw_text = "Kruskal-Wallis p < 0.001" if p_kw < 0.001 else f"Kruskal-Wallis p = {p_kw:.3f}"
    ax.text(0.02, 0.98, kw_text, transform=ax.transAxes, ha="left", va="top", fontsize=10)

    ax.set_xticks(x)
    ax.set_xticklabels(ZONE_ORDER, fontsize=11)
    ax.set_ylabel("Semantic damage severity index", fontsize=11)
    ax.tick_params(axis="y", labelsize=10)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_linewidth(1.0)
    ax.spines["bottom"].set_linewidth(1.0)

    fig.tight_layout()

    png_path = out_dir / "Figure_6_semantic_DSI_by_zone.png"
    tif_path = out_dir / "Figure_6_semantic_DSI_by_zone.tif"
    pdf_path = out_dir / "Figure_6_semantic_DSI_by_zone.pdf"
    fig.savefig(png_path, dpi=600)
    fig.savefig(tif_path, dpi=600)
    fig.savefig(pdf_path, dpi=600)
    plt.close(fig)

    long_out = df_long[["Patch_ID", "Zone", "DSI_semantic"]].copy()
    long_out.to_excel(out_dir / "Figure6_DSI_long_table.xlsx", index=False)
    stats_df.drop(columns=["letter"]).to_excel(out_dir / "Figure6_DSI_statistics.xlsx", index=False)
    pd.DataFrame(pair_rows).to_excel(out_dir / "Figure6_DSI_pairwise_tests.xlsx", index=False)

    note = ""
    if used_summary_mode:
        note = "Significance tests were computed from S7 patch-level data because S8 is summary-level."
    print("Done.")
    print(f"Statistical test source: {source_for_tests}")
    if note:
        print(note)
    print(f"Outputs saved to: {out_dir}")


if __name__ == "__main__":
    main()
