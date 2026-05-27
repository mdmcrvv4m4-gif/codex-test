import os
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

warnings.filterwarnings("ignore", category=UserWarning)


def resolve_project_root() -> Path:
    env_root = os.environ.get("BARREL_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    script_path = Path(__file__).resolve()
    if script_path.parent.name == "10_code":
        return script_path.parent.parent
    return script_path.parents[1]


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


def normalize_name(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def find_by_fuzzy(df_cols, target):
    t = normalize_name(target)
    for c in df_cols:
        if normalize_name(c) == t:
            return c
    return None


def merge_if_needed(df: pd.DataFrame, tables_dir: Path):
    key = find_col(df, ["Patch_ID", "Image_ID"])
    if key is None:
        print("[WARN] No Patch_ID/Image_ID key found; skip S3/S6 merge.")
        return df

    req_gray = ["Mean", "StdDev", "Entropy", "Contrast", "Homogeneity", "Energy", "Correlation"]
    req_sem = [
        "crack_area_fraction", "wear_area_fraction", "severe_damage_area_fraction",
        "crack_length_density", "crack_network_density", "wear_mark_density",
        "severe_damage_connected_area", "DSI_semantic",
    ]

    missing_gray = [c for c in req_gray if find_by_fuzzy(df.columns, c) is None]
    missing_sem = [c for c in req_sem if find_by_fuzzy(df.columns, c) is None]

    if missing_gray:
        s3 = tables_dir / "S3_gray_glcm_features_Z1_Z4.xlsx"
        if s3.exists():
            s3df = pd.read_excel(s3)
            s3key = find_col(s3df, ["Patch_ID", "Image_ID"])
            if s3key:
                keep = [s3key] + [c for c in s3df.columns if any(normalize_name(c) == normalize_name(m) for m in missing_gray)]
                tmp = s3df[keep].rename(columns={s3key: key})
                df = df.merge(tmp, on=key, how="left")
                print(f"[INFO] merged S3 for missing gray/GLCM features: {len(missing_gray)}")

    if missing_sem:
        s6 = tables_dir / "S6_semantic_features_Z1_Z4.xlsx"
        if s6.exists():
            s6df = pd.read_excel(s6)
            s6key = find_col(s6df, ["Patch_ID", "Image_ID"])
            if s6key:
                keep = [s6key] + [c for c in s6df.columns if any(normalize_name(c) == normalize_name(m) for m in missing_sem)]
                tmp = s6df[keep].rename(columns={s6key: key})
                df = df.merge(tmp, on=key, how="left")
                print(f"[INFO] merged S6 for missing semantic features: {len(missing_sem)}")

    return df


def confidence_ellipse(ax, x, y, color, lw=1.0, alpha=0.3):
    try:
        import matplotlib.transforms as transforms
        from matplotlib.patches import Ellipse
        cov = np.cov(x, y)
        if np.linalg.det(cov) <= 0:
            return
        eigvals, eigvecs = np.linalg.eigh(cov)
        if np.any(eigvals <= 0):
            return
        if np.max(eigvals) > 40 * max(1e-6, np.min(eigvals)):
            return
        pearson = cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1])
        ell_radius_x = np.sqrt(1 + pearson)
        ell_radius_y = np.sqrt(1 - pearson)
        ellipse = Ellipse((0, 0), width=2 * ell_radius_x, height=2 * ell_radius_y,
                          facecolor="none", edgecolor=color, linewidth=lw, alpha=alpha)
        scale_x = np.sqrt(cov[0, 0]) * 2.4477
        scale_y = np.sqrt(cov[1, 1]) * 2.4477
        mean_x, mean_y = np.mean(x), np.mean(y)
        transf = transforms.Affine2D().rotate_deg(45).scale(scale_x, scale_y).translate(mean_x, mean_y)
        ellipse.set_transform(transf + ax.transData)
        ax.add_patch(ellipse)
    except Exception:
        return


def select_heatmap_features(X: pd.DataFrame):
    pri = [
        "Mean", "StdDev", "Entropy", "Contrast", "Homogeneity", "Energy", "Correlation",
        "crack_area_fraction", "wear_area_fraction", "severe_damage_area_fraction",
        "crack_length_density", "crack_network_density", "wear_mark_density",
        "severe_damage_connected_area", "DSI_semantic",
    ]
    chosen = []
    for p in pri:
        m = find_by_fuzzy(X.columns, p)
        if m and m not in chosen:
            chosen.append(m)

    gray_keys = ["mean", "stddev", "entropy", "contrast", "homogeneity", "energy", "correlation"]
    sem_keys = ["crackareafraction", "wearareafraction", "severedamageareafraction", "cracklengthdensity", "cracknetworkdensity", "wearmarkdensity", "severedamageconnectedarea"]
    gray = [c for c in chosen if normalize_name(c) in gray_keys]
    sem = [c for c in chosen if normalize_name(c) in sem_keys]
    dsi = [c for c in chosen if "dsi" in normalize_name(c)]

    if len(gray) < 5:
        for c in X.columns:
            n = normalize_name(c)
            if any(k in n for k in gray_keys) and c not in chosen:
                chosen.append(c)
                gray.append(c)
            if len(gray) >= 5:
                break
    if len(sem) < 4:
        for c in X.columns:
            n = normalize_name(c)
            if any(k in n for k in sem_keys) and c not in chosen:
                chosen.append(c)
                sem.append(c)
            if len(sem) >= 4:
                break
    if len(dsi) < 1:
        for c in X.columns:
            if "dsi" in normalize_name(c) and c not in chosen:
                chosen.append(c)
                break

    if len(chosen) > 16:
        dsi_col = next((c for c in chosen if "dsi" in normalize_name(c)), None)
        if dsi_col:
            corr_to_dsi = X[chosen].corr().get(dsi_col)
            ordered = corr_to_dsi.abs().sort_values(ascending=False).index.tolist()
            chosen = ordered[:16]
        else:
            chosen = chosen[:16]
    return chosen


def main():
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["figure.facecolor"] = "white"

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

    exclude_keywords = {
        "patch_id", "image_id", "zone", "region", "label", "class", "target", "severity", "failure", "mode",
        "prediction", "predicted", "true", "y_true", "y_pred", "file", "path", "mask", "overlay", "status",
        "rank", "count", "group", "split", "fold"
    }
    protected = {zone_col.lower()}
    if sev_col:
        protected.add(sev_col.lower())
    if mode_col:
        protected.add(mode_col.lower())

    num_all = df.select_dtypes(include=[np.number]).copy()
    pca_cols = []
    excluded_cols = []
    for c in num_all.columns:
        cl = c.lower()
        if cl in protected or any(k in cl for k in exclude_keywords):
            excluded_cols.append(c)
            continue
        pca_cols.append(c)

    X = num_all[pca_cols].copy()
    X = X.dropna(axis=1, how="all")
    imputer = SimpleImputer(strategy="median")
    X = pd.DataFrame(imputer.fit_transform(X), columns=X.columns, index=X.index)

    heat_features = select_heatmap_features(X)
    corr = X[heat_features].corr(method="pearson")
    corr.to_excel(fig_dir / "Figure8_feature_correlation_matrix.xlsx")

    scaler = StandardScaler()
    Xz = scaler.fit_transform(X)

    pca = PCA(n_components=2, random_state=42)
    pcs = pca.fit_transform(Xz)
    evr = pca.explained_variance_ratio_

    pca_df = pd.DataFrame({"PC1": pcs[:, 0], "PC2": pcs[:, 1], "Zone": df[zone_col].values}, index=df.index)
    patch_id_col = find_col(df, ["Patch_ID", "Image_ID"])
    if patch_id_col:
        pca_df.insert(0, "Patch_ID", df[patch_id_col].values)
    pca_df.to_excel(fig_dir / "Figure8_PCA_scores.xlsx", index=False)

    pd.DataFrame({
        "Component": ["PC1", "PC2"],
        "Explained_variance_ratio": evr,
        "Explained_variance_percent": evr * 100,
    }).to_excel(fig_dir / "Figure8_PCA_explained_variance.xlsx", index=False)

    centroids = pca_df.groupby("Zone", as_index=False)[["PC1", "PC2"]].mean()
    centroids.to_excel(fig_dir / "Figure8_PCA_zone_centroids.xlsx", index=False)

    sil = np.nan
    if pca_df["Zone"].nunique() >= 2:
        sil = silhouette_score(Xz, pca_df["Zone"].values)

    short_map = {
        "crack_area_fraction": "Crack area",
        "wear_area_fraction": "Wear area",
        "severe_damage_area_fraction": "Severe damage area",
        "crack_length_density": "Crack length density",
        "crack_network_density": "Crack network density",
        "wear_mark_density": "Wear mark density",
        "severe_damage_connected_area": "Severe damage conn. area",
        "dsi_semantic": "Semantic DSI",
    }
    display_names = []
    for c in heat_features:
        n = normalize_name(c)
        mapped = None
        for k, v in short_map.items():
            if normalize_name(k) == n:
                mapped = v
                break
        display_names.append(mapped if mapped else c)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    im = axes[0].imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1, aspect="equal")
    cbar = fig.colorbar(im, ax=axes[0], fraction=0.046, pad=0.04)
    cbar.set_label("Pearson r")
    axes[0].set_xticks(np.arange(len(display_names)))
    axes[0].set_yticks(np.arange(len(display_names)))
    axes[0].set_xticklabels(display_names, rotation=45, ha="right")
    axes[0].set_yticklabels(display_names)
    for i in range(corr.shape[0]):
        for j in range(corr.shape[1]):
            v = corr.values[i, j]
            axes[0].text(j, i, f"{v:.2f}", ha="center", va="center", color=("white" if abs(v) > 0.5 else "black"), fontsize=8)
    axes[0].set_title("(a) Feature correlation heatmap", fontsize=12)

    palette = {"Z1": "#1f77b4", "Z2": "#ff7f0e", "Z3": "#2ca02c", "Z4": "#d62728"}
    ax = axes[1]
    for zone in ["Z1", "Z2", "Z3", "Z4"]:
        zdf = pca_df[pca_df["Zone"] == zone]
        if zdf.empty:
            continue
        ax.scatter(zdf["PC1"], zdf["PC2"], s=28, alpha=0.72, c=palette[zone], label=zone, edgecolors="none")
        cx, cy = zdf["PC1"].mean(), zdf["PC2"].mean()
        ax.scatter([cx], [cy], marker="X", s=140, c=palette[zone], edgecolors="black", linewidths=1.1)
        confidence_ellipse(ax, zdf["PC1"].values, zdf["PC2"].values, palette[zone], lw=1.0, alpha=0.3)
    ax.set_xlabel(f"PC1 ({evr[0]*100:.1f}%)")
    ax.set_ylabel(f"PC2 ({evr[1]*100:.1f}%)")
    ax.set_title("(b) PCA of combined features by barrel zone", fontsize=12)
    ax.legend(title="Zone", loc="upper right", frameon=True)

    for ext in ["png", "tif", "pdf"]:
        fig.savefig(fig_dir / f"Figure_8_feature_space_analysis.{ext}", dpi=600, bbox_inches="tight")
    plt.close(fig)

    summary = [
        f"Data table used: {main_table_path}",
        f"Sample count (Z1-Z4): {len(df)}",
        f"PCA input feature count: {X.shape[1]}",
        f"Heatmap features ({len(heat_features)}): {', '.join(heat_features)}",
        f"PC1 explained variance: {evr[0]:.6f} ({evr[0]*100:.2f}%)",
        f"PC2 explained variance: {evr[1]:.6f} ({evr[1]*100:.2f}%)",
        f"PC1+PC2 cumulative explained variance: {(evr[0]+evr[1]):.6f} ({(evr[0]+evr[1])*100:.2f}%)",
        f"Silhouette score (Zone on standardized full feature space): {sil:.6f}",
        f"Excluded label-like columns from PCA: Yes. Excluded columns: {', '.join(excluded_cols) if excluded_cols else 'None'}",
    ]
    with open(fig_dir / "Figure8_feature_space_summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")

    print(f"[INFO] Final sample count: {len(df)}")
    print(f"[INFO] PCA input feature count: {X.shape[1]}")
    print(f"[INFO] Outputs saved in: {fig_dir}")


if __name__ == "__main__":
    main()
