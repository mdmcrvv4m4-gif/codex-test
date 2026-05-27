import os
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

warnings.filterwarnings("ignore", category=UserWarning)


def resolve_project_root() -> Path:
    env_root = os.environ.get("BARREL_PROJECT_ROOT")
    if env_root:
        return Path(env_root)

    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[1]

    # If script is under .../10_code, prefer parent as project root
    if script_path.parent.name == "10_code":
        return script_path.parent.parent
    return repo_root


def pick_main_table(tables_dir: Path):
    s10 = tables_dir / "S10_ML_labeled_feature_table_Z1_Z4.xlsx"
    s7 = tables_dir / "S7_feature_table_with_semantic_DSI_Z1_Z4.xlsx"

    if s10.exists():
        return s10, "S10"
    if s7.exists():
        return s7, "S7"
    raise FileNotFoundError(f"Neither S10 nor S7 found in {tables_dir}")


def find_col(df: pd.DataFrame, candidates):
    lc_map = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lc_map:
            return lc_map[c.lower()]
    return None


def merge_if_needed(df: pd.DataFrame, tables_dir: Path):
    key = find_col(df, ["Patch_ID", "Image_ID"])
    if key is None:
        print("[WARN] No Patch_ID/Image_ID key found; skip S3/S6 merge.")
        return df

    required = {
        "gray": ["Mean", "StdDev", "Entropy", "Contrast", "Homogeneity", "Energy", "Correlation"],
        "semantic": [
            "crack_area_fraction",
            "wear_area_fraction",
            "severe_damage_area_fraction",
            "crack_length_density",
            "crack_network_density",
            "wear_mark_density",
            "DSI_semantic",
        ],
    }

    missing_gray = [c for c in required["gray"] if c not in df.columns]
    missing_sem = [c for c in required["semantic"] if c not in df.columns]

    if missing_gray:
        s3 = tables_dir / "S3_gray_glcm_features_Z1_Z4.xlsx"
        if s3.exists():
            s3df = pd.read_excel(s3)
            s3key = find_col(s3df, ["Patch_ID", "Image_ID"])
            if s3key:
                keep = [c for c in s3df.columns if c in missing_gray or c == s3key]
                if keep:
                    tmp = s3df[keep].rename(columns={s3key: key})
                    df = df.merge(tmp, on=key, how="left")
                    print(f"[INFO] merged S3 for missing gray/GLCM features: {len(missing_gray)}")

    if missing_sem:
        s6 = tables_dir / "S6_semantic_features_Z1_Z4.xlsx"
        if s6.exists():
            s6df = pd.read_excel(s6)
            s6key = find_col(s6df, ["Patch_ID", "Image_ID"])
            if s6key:
                keep = [c for c in s6df.columns if c in missing_sem or c == s6key]
                if keep:
                    tmp = s6df[keep].rename(columns={s6key: key})
                    df = df.merge(tmp, on=key, how="left")
                    print(f"[INFO] merged S6 for missing semantic features: {len(missing_sem)}")

    return df


def confidence_ellipse(ax, x, y, color):
    try:
        import matplotlib.transforms as transforms
        from matplotlib.patches import Ellipse

        cov = np.cov(x, y)
        if np.linalg.det(cov) <= 0:
            return
        pearson = cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1])
        ell_radius_x = np.sqrt(1 + pearson)
        ell_radius_y = np.sqrt(1 - pearson)

        ellipse = Ellipse((0, 0), width=2 * ell_radius_x, height=2 * ell_radius_y,
                          facecolor='none', edgecolor=color, linewidth=1.3, alpha=0.8)

        scale_x = np.sqrt(cov[0, 0]) * 2.4477
        scale_y = np.sqrt(cov[1, 1]) * 2.4477
        mean_x = np.mean(x)
        mean_y = np.mean(y)

        transf = transforms.Affine2D().rotate_deg(45).scale(scale_x, scale_y).translate(mean_x, mean_y)
        ellipse.set_transform(transf + ax.transData)
        ax.add_patch(ellipse)
    except Exception:
        return


def main():
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["figure.facecolor"] = "white"
    sns.set_theme(style="white")

    root = resolve_project_root()
    tables_dir = root / "05_tables"
    fig_dir = root / "07_figures_main"
    fig_dir.mkdir(parents=True, exist_ok=True)

    main_table_path, source_tag = pick_main_table(tables_dir)
    df = pd.read_excel(main_table_path)
    print(f"[INFO] Main table source: {source_tag} -> {main_table_path}")

    if source_tag == "S7":
        df = merge_if_needed(df, tables_dir)

    zone_col = find_col(df, ["Zone", "zone", "Barrel_zone", "region", "Zone_label"])
    if zone_col is None:
        raise ValueError("No zone label column found.")

    sev_col = find_col(df, ["damage_severity", "severity_label", "severity"])
    mode_col = find_col(df, ["failure_mode", "failure_mode_3class", "mode_label"])

    df[zone_col] = df[zone_col].astype(str).str.strip()
    df = df[df[zone_col].isin(["Z1", "Z2", "Z3", "Z4"])].copy()
    df = df[df[zone_col].notna()].copy()

    drop_cols = [
        "Patch_ID", "Image_ID", "file path", "patch path", "mask path", "overlay path", "status",
        zone_col,
    ]
    if sev_col:
        drop_cols.append(sev_col)
    if mode_col:
        drop_cols.append(mode_col)

    drop_lc = {c.lower() for c in drop_cols}
    feature_cols = [c for c in df.columns if c.lower() not in drop_lc]

    num_df = df[feature_cols].select_dtypes(include=[np.number]).copy()

    imputer = SimpleImputer(strategy="median")
    X = pd.DataFrame(imputer.fit_transform(num_df), columns=num_df.columns, index=num_df.index)

    print(f"[INFO] Final sample count: {len(df)}")
    print(f"[INFO] Numeric feature count: {X.shape[1]}")

    rep_features = [
        "Mean", "StdDev", "Entropy", "Contrast", "Homogeneity", "Energy", "Correlation",
        "crack_area_fraction", "wear_area_fraction", "severe_damage_area_fraction",
        "crack_length_density", "crack_network_density", "wear_mark_density", "DSI_semantic",
    ]
    selected = [c for c in rep_features if c in X.columns]
    if len(selected) > 16:
        selected = selected[:16]
    if len(selected) < 2:
        selected = list(X.columns[: min(16, X.shape[1])])

    corr = X[selected].corr(method="pearson")
    corr.to_excel(fig_dir / "Figure8_feature_correlation_matrix.xlsx")

    scaler = StandardScaler()
    Xz = scaler.fit_transform(X)

    pca = PCA(n_components=2, random_state=42)
    pcs = pca.fit_transform(Xz)

    pca_df = pd.DataFrame({
        "PC1": pcs[:, 0],
        "PC2": pcs[:, 1],
        "Zone": df[zone_col].values,
    }, index=df.index)

    patch_id_col = find_col(df, ["Patch_ID", "Image_ID"])
    if patch_id_col:
        pca_df.insert(0, "Patch_ID", df[patch_id_col].values)

    pca_df.to_excel(fig_dir / "Figure8_PCA_scores.xlsx", index=False)

    evr = pca.explained_variance_ratio_
    pd.DataFrame({
        "Component": ["PC1", "PC2"],
        "Explained_variance_ratio": evr,
        "Explained_variance_percent": evr * 100,
    }).to_excel(fig_dir / "Figure8_PCA_explained_variance.xlsx", index=False)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)

    sns.heatmap(
        corr,
        ax=axes[0],
        cmap="RdBu_r",
        vmin=-1,
        vmax=1,
        center=0,
        annot=True,
        fmt=".2f",
        square=True,
        cbar_kws={"shrink": 0.8, "label": "Pearson r"},
    )
    axes[0].set_title("(a) Feature correlation heatmap", fontsize=12)
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].tick_params(axis="y", rotation=0)

    palette = {"Z1": "#1f77b4", "Z2": "#ff7f0e", "Z3": "#2ca02c", "Z4": "#d62728"}
    ax = axes[1]
    for zone in ["Z1", "Z2", "Z3", "Z4"]:
        zdf = pca_df[pca_df["Zone"] == zone]
        if zdf.empty:
            continue
        ax.scatter(zdf["PC1"], zdf["PC2"], s=28, alpha=0.75, c=palette[zone], label=zone, edgecolors='none')
        cx, cy = zdf["PC1"].mean(), zdf["PC2"].mean()
        ax.scatter([cx], [cy], marker="X", s=140, c=palette[zone], edgecolors="black", linewidths=0.8)
        confidence_ellipse(ax, zdf["PC1"].values, zdf["PC2"].values, palette[zone])

    ax.set_xlabel(f"PC1 ({evr[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({evr[1]*100:.1f}%)")
    ax.set_title("(b) PCA of combined features by barrel zone", fontsize=12)
    ax.legend(title="Zone", frameon=True)

    for ext in ["png", "tif", "pdf"]:
        fig.savefig(fig_dir / f"Figure_8_feature_space_analysis.{ext}", dpi=600, bbox_inches="tight")
    plt.close(fig)

    try:
        import umap

        reducer = umap.UMAP(n_components=2, random_state=42)
        um = reducer.fit_transform(Xz)
        umap_df = pd.DataFrame({"UMAP1": um[:, 0], "UMAP2": um[:, 1], "Zone": df[zone_col].values})
        if patch_id_col:
            umap_df.insert(0, "Patch_ID", df[patch_id_col].values)

        umap_df.to_excel(fig_dir / "Figure8_UMAP_scores.xlsx", index=False)

        plt.figure(figsize=(7, 6), facecolor="white")
        for zone in ["Z1", "Z2", "Z3", "Z4"]:
            zdf = umap_df[umap_df["Zone"] == zone]
            if zdf.empty:
                continue
            plt.scatter(zdf["UMAP1"], zdf["UMAP2"], s=28, alpha=0.75, c=palette[zone], label=zone, edgecolors='none')
        plt.xlabel("UMAP1")
        plt.ylabel("UMAP2")
        plt.title("UMAP of combined features by barrel zone")
        plt.legend(title="Zone")
        plt.tight_layout()
        for ext in ["png", "tif", "pdf"]:
            plt.savefig(fig_dir / f"Figure_8_UMAP_by_zone.{ext}", dpi=600, bbox_inches="tight")
        plt.close()
        print("[INFO] UMAP generated.")
    except Exception:
        print("[INFO] umap-learn not available or failed; UMAP skipped.")

    print(f"[DONE] Outputs saved in: {fig_dir}")


if __name__ == "__main__":
    main()
