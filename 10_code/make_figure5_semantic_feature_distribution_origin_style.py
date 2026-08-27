"""Regenerate Figure 5: Zone-wise distributions of semantic damage features.

This script reads patch-level semantic damage features from S6 and creates a
2 x 3 Origin-style panel figure with boxplots overlaid by jittered scatter
points for zones Z1-Z4.
"""

from pathlib import Path
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import kruskal


WINDOWS_PROJECT_ROOT = Path(r"E:\Barrel_SEM_Z1_Z4_New")
ZONE_ORDER = ["Z1", "Z2", "Z3", "Z4"]

REQUIRED_COLUMNS = [
    "Patch_ID",
    "Image_ID",
    "Zone",
    "Crack_area_fraction",
    "Wear_area_fraction",
    "Severe_damage_area_fraction",
    "Crack_length_density",
    "Crack_network_density",
    "Wear_mark_density",
]

FEATURE_SPECS = [
    ("(a) Crack area fraction", "Crack_area_fraction", "5.64e-49"),
    ("(b) Wear area fraction", "Wear_area_fraction", "5.36e-19"),
    ("(c) Severe damage area fraction", "Severe_damage_area_fraction", "2.68e-64"),
    ("(d) Crack length density", "Crack_length_density", "6.15e-41"),
    ("(e) Crack network density", "Crack_network_density", "6.28e-40"),
    ("(f) Wear mark density", "Wear_mark_density", "1.45e-22"),
]


def resolve_project_root() -> Path:
    """Return the requested Windows project root, with a repo-local fallback.

    The fallback allows the same script to be linted or inspected on Linux/CI
    checkouts whose repository layout mirrors the Windows project directory.
    """
    if WINDOWS_PROJECT_ROOT.exists():
        return WINDOWS_PROJECT_ROOT
    return Path(__file__).resolve().parents[1]


def configure_matplotlib() -> None:
    """Configure fonts and vector output for an SCI/Origin-like appearance."""
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "axes.edgecolor": "black",
            "axes.linewidth": 0.8,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.major.size": 3.5,
            "ytick.major.size": 3.5,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
        }
    )


def validate_columns(df: pd.DataFrame) -> None:
    """Stop with a clear error message if any required column is missing."""
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        print("ERROR: The input Excel file is missing required columns:", file=sys.stderr)
        for col in missing:
            print(f"  - {col}", file=sys.stderr)
        print("Available columns:", file=sys.stderr)
        for col in df.columns:
            print(f"  - {col}", file=sys.stderr)
        raise SystemExit(1)


def zone_feature_values(df: pd.DataFrame, feature: str) -> list[np.ndarray]:
    """Return numeric, NaN-free patch-level values in fixed Z1-Z4 order."""
    values = []
    for zone in ZONE_ORDER:
        zone_values = pd.to_numeric(
            df.loc[df["Zone"] == zone, feature], errors="coerce"
        ).dropna()
        values.append(zone_values.to_numpy(dtype=float))
    return values


def draw_panel(ax: plt.Axes, values_by_zone: list[np.ndarray], title: str, feature: str, p_text: str, seed: int) -> None:
    """Draw one zone-wise boxplot plus jittered patch-level scatter panel."""
    positions = np.arange(1, len(ZONE_ORDER) + 1)

    box = ax.boxplot(
        values_by_zone,
        positions=positions,
        widths=0.50,
        patch_artist=True,
        showfliers=False,
        whis=1.5,
        boxprops={"facecolor": "#d9e3ef", "edgecolor": "#333333", "linewidth": 0.9},
        medianprops={"color": "#d00000", "linewidth": 1.0},
        whiskerprops={"color": "#333333", "linewidth": 0.8},
        capprops={"color": "#333333", "linewidth": 0.8},
    )
    for patch in box["boxes"]:
        patch.set_alpha(0.95)

    rng = np.random.default_rng(seed)
    for x_pos, vals in zip(positions, values_by_zone):
        if vals.size == 0:
            continue
        jittered_x = x_pos + rng.uniform(-0.12, 0.12, size=vals.size)
        ax.scatter(
            jittered_x,
            vals,
            s=15,
            marker="o",
            c="#1f77b4",
            alpha=0.72,
            edgecolors="none",
            rasterized=False,
            zorder=3,
        )

    ax.set_title(title, fontsize=11, pad=6)
    ax.set_xlabel("Zone", fontsize=10)
    ax.set_ylabel(feature, fontsize=10)
    ax.set_xticks(positions)
    ax.set_xticklabels(ZONE_ORDER, fontsize=9)
    ax.tick_params(axis="y", labelsize=9, direction="in", width=0.8, length=3.5)
    ax.tick_params(axis="x", labelsize=9, direction="in", width=0.8, length=3.5)
    ax.grid(False)

    for spine in ax.spines.values():
        spine.set_color("black")
        spine.set_linewidth(0.8)

    ax.text(
        0.98,
        0.97,
        f"Kruskal-Wallis p = {p_text}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8.5,
        color="black",
    )


def main() -> None:
    project_root = resolve_project_root()
    input_path = project_root / "05_tables" / "S6_semantic_features_Z1_Z4.xlsx"
    output_dir = project_root / "07_figures_main"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Input Excel file not found: {input_path}")

    df = pd.read_excel(input_path)
    validate_columns(df)
    df = df.copy()
    df["Zone"] = df["Zone"].astype(str).str.strip()
    df = df[df["Zone"].isin(ZONE_ORDER)]

    if df.empty:
        raise ValueError("No rows remain after filtering Zone to Z1, Z2, Z3, and Z4.")

    configure_matplotlib()

    fig, axes = plt.subplots(2, 3, figsize=(16, 8), dpi=600)
    axes = axes.ravel()

    for idx, (panel_title, feature, fixed_p) in enumerate(FEATURE_SPECS):
        values_by_zone = zone_feature_values(df, feature)
        valid_groups = [vals for vals in values_by_zone if vals.size > 0]
        if len(valid_groups) >= 2:
            _, recalculated_p = kruskal(*valid_groups)
            print(f"{feature}: recalculated Kruskal-Wallis p = {recalculated_p:.6e}")
        else:
            print(f"{feature}: recalculated Kruskal-Wallis p = NA (fewer than two non-empty groups)")

        draw_panel(
            axes[idx],
            values_by_zone,
            panel_title,
            feature,
            fixed_p,
            seed=202405 + idx,
        )

    fig.suptitle(
        "Figure 5. Zone-wise distributions of semantic damage features.",
        fontsize=15,
        y=0.985,
    )
    fig.tight_layout(rect=[0.02, 0.02, 0.995, 0.94], w_pad=2.0, h_pad=2.2)

    outputs = [
        output_dir / "Figure_5_semantic_feature_distribution_origin_style.png",
        output_dir / "Figure_5_semantic_feature_distribution_origin_style.tif",
        output_dir / "Figure_5_semantic_feature_distribution_origin_style.svg",
    ]

    fig.savefig(outputs[0], dpi=600, bbox_inches="tight")
    fig.savefig(outputs[1], dpi=600, bbox_inches="tight")
    fig.savefig(outputs[2], bbox_inches="tight")
    plt.close(fig)

    print("Saved output files:")
    for output in outputs:
        print(output.resolve())


if __name__ == "__main__":
    main()
