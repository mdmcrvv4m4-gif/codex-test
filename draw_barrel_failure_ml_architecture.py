import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Ellipse, FancyArrowPatch
from matplotlib import rcParams
from sklearn.decomposition import PCA
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score


FIG_W, FIG_H = 16, 10  # 16:10 layout
RED = '#c00000'
BORDER = '#cfcfcf'
TITLE_FS = 12
SMALL_FS = 8


def set_font():
    available = {f.name for f in plt.matplotlib.font_manager.fontManager.ttflist}
    rcParams['font.family'] = 'Times New Roman' if 'Times New Roman' in available else 'DejaVu Serif'


def load_real_feature_data():
    paths = [
        '05_tables/S5_gray_glcm_features_4x4_Z1_Z5.xlsx',
        'S5_gray_glcm_features_4x4_Z1_Z5.xlsx',
        '/mnt/data/S5_gray_glcm_features_4x4_Z1_Z5.xlsx',
    ]
    primary_features = [
        'Mean', 'Median', 'StdDev', 'Skewness', 'Kurtosis', 'Entropy', 'Contrast',
        'Dissimilarity', 'Homogeneity', 'Energy', 'ASM', 'Correlation', 'Total_defect_area_fraction'
    ]
    morphology_features = [
        'Crack_area_fraction', 'Crack_density', 'Mean_crack_length', 'Groove_orientation',
        'Groove_orientation_consistency', 'Pit_area_fraction', 'Spalling_area_fraction',
        'Severe_damage_area_fraction'
    ]
    label_candidates = [
        'Failure_Mode', 'Damage_Mode', 'Failure mode', 'Damage mode', 'Label', 'Class',
        'Failure_Label', 'Damage_Label', 'Mode'
    ]

    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            df = pd.read_excel(p)
        except Exception as exc:
            print(f'Warning: Failed to read {p}: {exc}')
            continue

        use_cols = [c for c in primary_features if c in df.columns]
        use_cols += [c for c in morphology_features if c in df.columns and c not in use_cols]
        if not use_cols:
            print(f'Warning: No required feature columns in {p}.')
            continue

        X_df = df[use_cols].copy()
        for c in X_df.columns:
            X_df[c] = pd.to_numeric(X_df[c], errors='coerce')

        X_df = X_df.dropna(axis=1, how='all')
        for c in X_df.columns:
            med = X_df[c].median()
            if np.isfinite(med):
                X_df[c] = X_df[c].fillna(med)
        X_df = X_df.dropna(axis=1, how='any')
        X_df = X_df.loc[:, np.isfinite(X_df.to_numpy()).all(axis=0)]

        if X_df.shape[1] == 0 or X_df.shape[0] < 3:
            print(f'Warning: Usable feature matrix is empty/too small in {p}.')
            continue

        valid_idx = X_df.index
        y = None
        label_name = None
        temp_group_name = None

        for lc in label_candidates:
            if lc in df.columns:
                y_ser = df.loc[valid_idx, lc].astype(str).fillna('Unknown')
                if y_ser.nunique() >= 2:
                    y = y_ser.to_numpy()
                    label_name = lc
                    break

        if y is None:
            for temp_col in ['Zone', 'Subset']:
                if temp_col in df.columns:
                    temp_ser = df.loc[valid_idx, temp_col].astype(str).fillna('Unknown')
                    if temp_ser.nunique() >= 2:
                        y = temp_ser.to_numpy()
                        temp_group_name = temp_col
                        break

        feature_names = list(X_df.columns)
        bundle = {
            'df': df.loc[valid_idx].copy(),
            'X': X_df.to_numpy(dtype=float),
            'y': y,
            'feature_names': feature_names,
            'label_name': label_name,
            'temp_group_name': temp_group_name,
            'data_source': p,
            'using_real_features': True,
            'using_real_labels': label_name is not None,
        }

        print(f'Real data loaded: {p}')
        print(f'Using features: {", ".join(feature_names)}')
        if label_name is not None:
            print(f'Real label column found: {label_name}')
        elif temp_group_name is not None:
            print(f'No real failure label. Temporary grouping for PCA display: {temp_group_name}')
            # This grouping is not the final failure mode label and cannot represent true failure mode classification.
        else:
            print('No label/grouping column found in real data.')
        print(f'Samples: {bundle["X"].shape[0]}')
        print(f'Feature count: {bundle["X"].shape[1]}')

        if y is None:
            print('Warning: No real failure label found. PCA uses real features, but ML evaluation uses demo labels.')

        return bundle

    X_demo, y_demo = make_blobs(n_samples=120, centers=3, n_features=13, cluster_std=1.7, random_state=7)
    feature_names = [
        'Mean', 'Median', 'StdDev', 'Skewness', 'Kurtosis', 'Entropy', 'Contrast',
        'Dissimilarity', 'Homogeneity', 'Energy', 'ASM', 'Correlation', 'Total_defect_area_fraction'
    ]
    print('Warning: Real feature data not found/readable. Using demo data.')
    print(f'Using features: {", ".join(feature_names)}')
    print('Real label column found: Demo_Label')
    print(f'Samples: {X_demo.shape[0]}')
    print(f'Feature count: {X_demo.shape[1]}')
    return {
        'df': None,
        'X': X_demo,
        'y': y_demo.astype(str),
        'feature_names': feature_names,
        'label_name': 'Demo_Label',
        'temp_group_name': None,
        'data_source': 'simulated',
        'using_real_features': False,
        'using_real_labels': False,
    }


def style_panel(ax, title):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    ax.add_patch(FancyBboxPatch((0.02, 0.08), 0.96, 0.88, boxstyle='round,pad=0.012,rounding_size=0.03',
                                linewidth=1.2, edgecolor=BORDER, facecolor='white'))
    ax.text(0.5, 0.99, title, ha='center', va='top', fontsize=TITLE_FS, fontweight='bold', color='black')


# (unchanged drawing funcs omitted brevity in source? keep explicit)
def draw_barrel_sampling(ax):
    style_panel(ax, 'Failed barrel sampling')
    ax.add_patch(Rectangle((0.12, 0.45), 0.76, 0.12, facecolor='#f2f2f2', edgecolor='black', lw=1.0))
    ax.add_patch(Ellipse((0.12, 0.51), 0.08, 0.12, facecolor='#e0e0e0', edgecolor='black', lw=1.0))
    ax.add_patch(Ellipse((0.88, 0.51), 0.08, 0.12, facecolor='#fafafa', edgecolor='black', lw=1.0))
    for x, label in [(0.18, 'Breech'), (0.50, 'Middle'), (0.82, 'Muzzle')]:
        ax.plot([x, x], [0.40, 0.62], '--', color=RED, lw=1.8)
        ax.text(x, 0.36, label, ha='center', va='top', fontsize=SMALL_FS)
    ax.text(0.18, 0.72, 'Macro photos', fontsize=SMALL_FS)
    ax.text(0.64, 0.72, 'SEM sampling', fontsize=SMALL_FS)


def draw_sem_observation(ax):
    style_panel(ax, 'Surface damage observation')
    rng = np.random.default_rng(42)
    positions = [(0.08, 0.57), (0.39, 0.57), (0.70, 0.57), (0.08, 0.20), (0.39, 0.20), (0.70, 0.20)]
    for i, (x, y) in enumerate(positions):
        w, h = 0.22, 0.28
        arr = np.clip(rng.normal(0.55, 0.15, (30, 30)), 0, 1)
        ax.imshow(arr, extent=(x, x+w, y, y+h), cmap='gray', vmin=0, vmax=1, zorder=1)
        ax.add_patch(Rectangle((x, y), w, h, facecolor='none', edgecolor='black', lw=0.8, zorder=2))
        if i in (0, 3):
            ax.plot([x+0.03, x+w-0.02], [y+0.04, y+h-0.05], color='black', lw=1.1)
        elif i in (1, 4):
            for yy in np.linspace(y+0.04, y+h-0.04, 4):
                ax.plot([x+0.03, x+w-0.03], [yy, yy+0.02], color='dimgray', lw=1.0)
        else:
            for _ in range(4):
                cx, cy = rng.uniform(x+0.04, x+w-0.04), rng.uniform(y+0.05, y+h-0.05)
                ax.add_patch(Ellipse((cx, cy), 0.04, 0.025, facecolor='none', edgecolor='black', lw=0.8))
    ax.text(0.04, 0.10, 'thermal fatigue cracks | directional wear grooves | erosion pits | coating/substrate spalling', fontsize=7.5)


def draw_dataset_assembling(ax):
    style_panel(ax, 'Dataset assembling')
    ax.add_patch(Rectangle((0.08, 0.30), 0.22, 0.40, facecolor='#d9d9d9', edgecolor='black'))
    ax.text(0.19, 0.72, 'SEM image', ha='center', fontsize=SMALL_FS)
    ax.annotate('', xy=(0.44, 0.50), xytext=(0.31, 0.50), arrowprops=dict(arrowstyle='->', color=RED, lw=2))
    ax.add_patch(Rectangle((0.46, 0.26), 0.24, 0.48, facecolor='#f7f7f7', edgecolor='black'))
    for i in range(1, 4):
        ax.plot([0.46, 0.70], [0.26+i*0.12, 0.26+i*0.12], color='gray', lw=0.8)
        ax.plot([0.46+i*0.06, 0.46+i*0.06], [0.26, 0.74], color='gray', lw=0.8)
    ax.text(0.58, 0.76, '4×4 patches', ha='center', fontsize=SMALL_FS)
    ax.add_patch(Rectangle((0.75, 0.26), 0.20, 0.48, facecolor='white', edgecolor='black'))
    for i, f in enumerate(['Image_ID', 'Patch_ID', 'Zone', 'Failure label']):
        y = 0.66 - i*0.11
        ax.text(0.77, y, f, fontsize=SMALL_FS)
        ax.plot([0.75, 0.95], [y-0.04, y-0.04], color='#d0d0d0', lw=0.8)


def draw_feature_extraction(ax, bundle):
    style_panel(ax, 'Feature extraction')
    names = bundle['feature_names']
    group_counts = [sum('Entropy' not in n and 'Contrast' not in n and 'Correlation' not in n and 'Homogeneity' not in n and 'Energy' not in n and 'ASM' not in n and 'Dissimilarity' not in n for n in names),
                    sum(any(k in n for k in ['Entropy', 'Contrast', 'Correlation', 'Homogeneity', 'Energy', 'ASM', 'Dissimilarity']) for n in names),
                    sum(any(k in n for k in ['defect', 'Crack', 'Groove', 'Pit', 'Spalling', 'Severe']) for n in names)]
    x = np.arange(3)
    ax.bar(0.10 + x*0.10, [max(1, v) for v in group_counts], width=0.07, color=['#999999', '#7f7f7f', '#4d4d4d'])
    for i, c in enumerate(['Gray', 'GLCM', 'Morph.']):
        ax.text(0.10 + i*0.10, 0.13, c, fontsize=7, ha='center', transform=ax.transAxes)
    ax.text(0.08, 0.73, 'Grayscale statistics', fontsize=SMALL_FS)
    ax.text(0.08, 0.67, 'GLCM texture features', fontsize=SMALL_FS)
    ax.text(0.08, 0.61, 'Defect morphology features', fontsize=SMALL_FS)
    ax.add_patch(Rectangle((0.45, 0.24), 0.48, 0.56, facecolor='white', edgecolor='black', lw=0.9))
    show = names[:6] + (['...'] if len(names) > 6 else [])
    ax.text(0.47, 0.70, f'N={bundle["X"].shape[0]} samples', fontsize=7.5)
    ax.text(0.47, 0.56, f'p={bundle["X"].shape[1]} features', fontsize=7.5)
    ax.text(0.47, 0.42, ' / '.join(show), fontsize=7.0)


def draw_pca(ax, bundle):
    style_panel(ax, 'PCA dimensionality reduction')
    X = StandardScaler().fit_transform(bundle['X'])
    pca = PCA(n_components=min(3, X.shape[1]), random_state=7)
    Z = pca.fit_transform(X)

    if bundle['y'] is not None:
        groups = bundle['y']
    else:
        groups = KMeans(n_clusters=3, random_state=42, n_init=10).fit_predict(Z[:, :2]).astype(str)

    uniq = pd.unique(groups)
    colors = plt.cm.Set1(np.linspace(0, 1, len(uniq)))
    for c, u in zip(colors, uniq):
        mask = groups == u
        pts = Z[mask, :2]
        x = 0.12 + (pts[:, 0] - Z[:, 0].min()) / (np.ptp(Z[:, 0]) + 1e-9) * 0.75
        y = 0.22 + (pts[:, 1] - Z[:, 1].min()) / (np.ptp(Z[:, 1]) + 1e-9) * 0.58
        ax.scatter(x, y, s=12, color=c, alpha=0.8, label=str(u))

    ax.text(0.12, 0.18, 'PC1', fontsize=SMALL_FS)
    ax.text(0.04, 0.24, 'PC2', fontsize=SMALL_FS, rotation=90)
    ax.text(0.74, 0.80, f'Expl.Var={pca.explained_variance_ratio_[:2].sum():.2f}', fontsize=7)
    ax.legend(loc='lower left', fontsize=6.2, frameon=False, ncol=1)


def draw_clustering(ax, bundle):
    style_panel(ax, 'Clustering analysis')
    X = StandardScaler().fit_transform(bundle['X'])
    Z = PCA(n_components=2, random_state=7).fit_transform(X)
    km = KMeans(n_clusters=3, random_state=42, n_init=10).fit(Z)
    labels = km.labels_
    colors = ['#f46d43', '#74add1', '#66bd63']
    xn = (Z[:, 0]-Z[:, 0].min())/(np.ptp(Z[:, 0])+1e-9)
    yn = (Z[:, 1]-Z[:, 1].min())/(np.ptp(Z[:, 1])+1e-9)
    for k, c in enumerate(colors):
        mask = labels == k
        ax.scatter(0.08 + xn[mask]*0.50, 0.20 + yn[mask]*0.60, s=14, c=c)
        cx, cy = 0.08 + xn[mask].mean()*0.50, 0.20 + yn[mask].mean()*0.60
        sx = max(0.10, xn[mask].std()*0.45)
        sy = max(0.08, yn[mask].std()*0.35)
        ax.add_patch(Ellipse((cx, cy), sx, sy, fill=False, edgecolor='black', lw=1.0))
        ax.text(cx, cy+0.08, f'Cluster {k+1}', ha='center', fontsize=7)

    feat_idx = np.linspace(0, bundle['X'].shape[1]-1, min(3, bundle['X'].shape[1]), dtype=int)
    means = []
    for k in range(3):
        means.append(np.mean(bundle['X'][labels == k][:, feat_idx], axis=0))
    heat = np.array(means)
    if np.isfinite(heat).all():
        heat = (heat - heat.min()) / (np.ptp(heat) + 1e-9)
    ax.imshow(heat, extent=(0.68, 0.94, 0.28, 0.70), cmap='YlGnBu', vmin=0, vmax=1)
    ax.add_patch(Rectangle((0.68, 0.28), 0.26, 0.42, fill=False, edgecolor='black', lw=0.8))
    ax.text(0.81, 0.73, 'Cluster feature mean', fontsize=7, ha='center')


def draw_ml_training(ax):
    style_panel(ax, 'ML model training')
    models = ['Random\nForest', 'SVM', 'XGBoost', 'KNN', 'Neural\nNetwork']
    xs = [0.12, 0.30, 0.48, 0.66, 0.84]
    for x, m in zip(xs, models):
        ax.add_patch(FancyBboxPatch((x-0.07, 0.50), 0.14, 0.18, boxstyle='round,pad=0.01,rounding_size=0.02', facecolor='#f7f7f7', edgecolor='black', lw=0.9))
        ax.text(x, 0.59, m, ha='center', va='center', fontsize=7.5)
    ax.annotate('', xy=(0.80, 0.38), xytext=(0.20, 0.38), arrowprops=dict(arrowstyle='->', color=RED, lw=2))
    ax.text(0.50, 0.40, 'training', color=RED, ha='center', fontsize=SMALL_FS)
    ax.text(0.10, 0.24, 'train/test split', fontsize=SMALL_FS)
    ax.text(0.42, 0.24, 'cross-validation', fontsize=SMALL_FS)
    ax.text(0.74, 0.24, 'model selection', fontsize=SMALL_FS, ha='center')


def draw_prediction_evaluation(ax, bundle):
    title = 'Prediction evaluation' if bundle['using_real_labels'] else 'Prediction evaluation (Demo)'
    style_panel(ax, title)
    classes = None
    if bundle['using_real_labels']:
        X = StandardScaler().fit_transform(bundle['X'])
        y = np.array(bundle['y']).astype(str)
        uniq, counts = np.unique(y, return_counts=True)
        strat = y if np.all(counts >= 2) and len(uniq) > 1 else None
        Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, random_state=42, stratify=strat)
        clf = RandomForestClassifier(n_estimators=300, random_state=42)
        clf.fit(Xtr, ytr)
        yp = clf.predict(Xte)
        classes = np.unique(np.concatenate([yte, yp]))
        cm = confusion_matrix(yte, yp, labels=classes)
        acc = accuracy_score(yte, yp)
        prec = precision_score(yte, yp, average='macro', zero_division=0)
        rec = recall_score(yte, yp, average='macro', zero_division=0)
        f1 = f1_score(yte, yp, average='macro', zero_division=0)
    else:
        cm = np.array([[34, 3, 1], [4, 29, 2], [2, 3, 31]])
        classes = np.array(['Crack', 'Wear', 'Severe'])
        acc, prec, rec, f1 = 0.90, 0.89, 0.90, 0.89

    ax.imshow(cm, extent=(0.08, 0.55, 0.22, 0.78), cmap='Blues')
    n = cm.shape[0]
    for i in range(n):
        for j in range(n):
            x = 0.08 + (j + 0.5) * (0.47 / n)
            y = 0.22 + (n - i - 0.5) * (0.56 / n)
            ax.text(x, y, str(cm[i, j]), ha='center', va='center', fontsize=8)
    short = [str(c)[:8] for c in classes]
    for j, c in enumerate(short):
        ax.text(0.08 + (j + 0.5) * (0.47 / n), 0.18, c, ha='center', fontsize=7)
        ax.text(0.04, 0.22 + (n - j - 0.5) * (0.56 / n), c, va='center', fontsize=7)
    ax.text(0.57, 0.68, f'Accuracy: {acc:.2f}', fontsize=SMALL_FS)
    ax.text(0.57, 0.58, f'Precision: {prec:.2f}', fontsize=SMALL_FS)
    ax.text(0.57, 0.48, f'Recall: {rec:.2f}', fontsize=SMALL_FS)
    ax.text(0.57, 0.38, f'F1-score: {f1:.2f}', fontsize=SMALL_FS)


def draw_explainability_decision(ax, bundle):
    title = 'Explainability & maintenance decision' if bundle['using_real_labels'] else 'Explainability & maintenance decision (Demo)'
    style_panel(ax, title)

    if bundle['using_real_labels']:
        X = StandardScaler().fit_transform(bundle['X'])
        y = np.array(bundle['y']).astype(str)
        clf = RandomForestClassifier(n_estimators=300, random_state=42)
        clf.fit(X, y)
        importances = clf.feature_importances_
        idx = np.argsort(importances)[-6:][::-1]
        feats = [bundle['feature_names'][i] for i in idx]
        vals = importances[idx]
    else:
        feats = ['Defect area fraction', 'Entropy', 'Contrast', 'StdDev', 'Crack density', 'Groove orientation']
        vals = np.array([0.28, 0.22, 0.18, 0.14, 0.10, 0.08])

    y = np.arange(len(feats))
    vn = vals / (vals.max() + 1e-9)
    ax.barh(0.18 + y*0.08, vn * 0.28, height=0.05, color='#8da0cb')
    for i, f in enumerate(feats):
        ax.text(0.02, 0.185 + i*0.08, f[:28], fontsize=6.8, va='center')
    ax.text(0.36, 0.75, 'SHAP-like / RF importance', fontsize=7.5)
    ax.add_patch(Rectangle((0.58, 0.22), 0.36, 0.58, facecolor='#fbfbfb', edgecolor='black', lw=0.9))
    for i, d in enumerate(['Continue monitoring', 'Preventive maintenance', 'Repair recommendation', 'Scrap / replacement']):
        ax.text(0.61, 0.70 - i*0.13, f'• {d}', fontsize=SMALL_FS)


def add_global_arrows(fig, axes):
    chain = [axes[0], axes[1], axes[2], axes[3], axes[4], axes[5], axes[6], axes[7], axes[8]]
    for i in range(len(chain)-1):
        a, b = chain[i].get_position(), chain[i+1].get_position()
        x1, y1 = a.x1, (a.y0+a.y1)/2
        x2, y2 = b.x0, (b.y0+b.y1)/2
        if abs(y1-y2) > 0.1:
            x1, y1 = (a.x0+a.x1)/2, a.y0
            x2, y2 = (b.x0+b.x1)/2, b.y1
        fig.add_artist(FancyArrowPatch((x1, y1), (x2, y2), transform=fig.transFigure, arrowstyle='-|>', mutation_scale=16, lw=2.4, color=RED))

    a, b = axes[8].get_position(), axes[3].get_position()
    start = (a.x0 + 0.90*(a.x1-a.x0), a.y0 + 0.15*(a.y1-a.y0))
    end = (b.x0 + 0.05*(b.x1-b.x0), b.y0 + 0.85*(b.y1-b.y0))
    fig.add_artist(FancyArrowPatch(start, end, transform=fig.transFigure, arrowstyle='-|>',
                                   connectionstyle='arc3,rad=-0.35', mutation_scale=16, lw=2.4, color=RED))


def main():
    set_font()
    bundle = load_real_feature_data()

    fig, axs = plt.subplots(3, 3, figsize=(FIG_W, FIG_H), facecolor='white')
    plt.subplots_adjust(left=0.03, right=0.97, top=0.95, bottom=0.11, wspace=0.14, hspace=0.20)

    draw_barrel_sampling(axs[0, 0])
    draw_sem_observation(axs[0, 1])
    draw_dataset_assembling(axs[0, 2])
    draw_feature_extraction(axs[1, 0], bundle)
    draw_pca(axs[1, 1], bundle)
    draw_clustering(axs[1, 2], bundle)
    draw_ml_training(axs[2, 0])
    draw_prediction_evaluation(axs[2, 1], bundle)
    draw_explainability_decision(axs[2, 2], bundle)

    axes_list = [axs[0, 0], axs[0, 1], axs[0, 2], axs[1, 0], axs[1, 1], axs[1, 2], axs[2, 0], axs[2, 1], axs[2, 2]]
    add_global_arrows(fig, axes_list)

    fig.text(0.5, 0.045, 'Fig. 1. Architecture summary of the proposed barrel failure mode identification and machine-learning-assisted assessment framework.', ha='center', va='center', fontsize=11)

    outbase = 'Fig1_barrel_failure_ml_architecture'
    fig.savefig(f'{outbase}.png', dpi=600, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{outbase}.pdf', dpi=600, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{outbase}.svg', dpi=600, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('Figure saved as Fig1_barrel_failure_ml_architecture.png/pdf/svg')


if __name__ == '__main__':
    main()
