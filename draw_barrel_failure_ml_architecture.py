import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.patches import FancyBboxPatch, Rectangle, Ellipse, FancyArrowPatch
from matplotlib import rcParams
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp')
FIG_W, FIG_H = 17, 10
RED = '#c00000'
LIGHT_RED = '#d95f5f'
BORDER = '#d0d0d0'
TITLE_FS = 11.5
TEXT_FS = 7.6


def set_font():
    available = {f.name for f in plt.matplotlib.font_manager.fontManager.ttflist}
    rcParams['font.family'] = 'Times New Roman' if 'Times New Roman' in available else 'DejaVu Serif'


def find_project_root():
    cwd = Path.cwd().resolve()
    if cwd.name == '10_code' and (cwd.parent / '05_tables').exists():
        return cwd.parent
    if (cwd / '05_tables').exists() and (cwd / '07_figures_main').exists():
        return cwd
    for p in [cwd] + list(cwd.parents):
        if (p / '05_tables').exists() and (p / '07_figures_main').exists():
            return p
    return cwd


def find_files(root, subfolders, extensions):
    files = []
    for sub in subfolders:
        folder = root / sub
        if not folder.exists():
            continue
        for ext in extensions:
            files.extend(sorted(folder.rglob(f'*{ext}')))
    return files


def select_representative_images(folder, n=4):
    folder = Path(folder)
    if not folder.exists():
        return []
    imgs = []
    for ext in IMAGE_EXTS:
        imgs.extend(sorted(folder.rglob(f'*{ext}')))
    if not imgs:
        return []
    if len(imgs) <= n:
        return imgs
    idx = np.linspace(0, len(imgs)-1, n, dtype=int)
    return [imgs[i] for i in idx]


def read_image_safely(path):
    try:
        arr = mpimg.imread(path)
        if arr.ndim == 2:
            arr = np.stack([arr, arr, arr], axis=-1)
        if arr.shape[0] > 2500 or arr.shape[1] > 2500:
            step0 = max(1, arr.shape[0] // 1400)
            step1 = max(1, arr.shape[1] // 1400)
            arr = arr[::step0, ::step1]
        return arr
    except Exception:
        return None


def insert_image_grid(ax, image_paths, area, ncols=2, nrows=2, title=None):
    x0, y0, w, h = area
    if title:
        ax.text(x0, y0 + h + 0.01, title, fontsize=TEXT_FS, va='bottom')
    if not image_paths:
        return False
    pad = 0.008
    cw = (w - pad * (ncols + 1)) / ncols
    ch = (h - pad * (nrows + 1)) / nrows
    k = 0
    for r in range(nrows):
        for c in range(ncols):
            if k >= len(image_paths):
                break
            img = read_image_safely(image_paths[k])
            if img is None:
                k += 1
                continue
            xi = x0 + pad + c * (cw + pad)
            yi = y0 + h - (r + 1) * (ch + pad)
            ia = ax.inset_axes([xi, yi, cw, ch])
            ia.imshow(img, cmap='gray' if img.ndim == 2 else None)
            ia.set_xticks([]); ia.set_yticks([])
            for sp in ia.spines.values():
                sp.set_linewidth(0.5); sp.set_edgecolor('#666666')
            k += 1
    return True


def find_first_matching_file(root, keywords, extensions):
    candidates = []
    for ext in extensions:
        candidates.extend(root.rglob(f'*{ext}'))
    keywords = [k.lower() for k in keywords]
    for p in sorted(candidates):
        name = p.name.lower()
        if all(k in name for k in keywords):
            return p
    return None


def load_real_feature_data(project_root):
    table_root = project_root / '05_tables'
    preferred = [
        table_root / 'S5_gray_glcm_features_4x4_Z1_Z5.xlsx',
        table_root / 'S5_gray_glcm_features_4x4_Z1_Z4.xlsx',
    ]
    fuzzy = []
    if table_root.exists():
        for p in table_root.rglob('*.xlsx'):
            n = p.name.lower()
            if any(k in n for k in ['gray', 'glcm', 'feature', 'features', 'patch']):
                fuzzy.append(p)
    any_xlsx = sorted(project_root.rglob('*.xlsx'))
    candidates = preferred + [p for p in fuzzy if p not in preferred] + [p for p in any_xlsx if p not in preferred and p not in fuzzy]

    base_cols = ['Mean', 'Median', 'StdDev', 'Skewness', 'Kurtosis', 'Entropy', 'Contrast', 'Dissimilarity',
                 'Homogeneity', 'Energy', 'ASM', 'Correlation', 'Total_defect_area_fraction']
    morph_cols = ['Crack_area_fraction', 'Crack_density', 'Mean_crack_length', 'Groove_orientation',
                  'Groove_orientation_consistency', 'Pit_area_fraction', 'Spalling_area_fraction', 'Severe_damage_area_fraction']
    label_candidates = ['Failure_Mode', 'Damage_Mode', 'Failure mode', 'Damage mode', 'Label', 'Class',
                        'Failure_Label', 'Damage_Label', 'Mode']

    bundle = {
        'df': None, 'X': None, 'y': None, 'feature_names': [], 'label_name': None,
        'data_source': 'simulated', 'using_real_features': False, 'using_real_labels': False,
        'pca_scores': None, 'pca_model': None, 'cluster_labels': None, 'trained_model': None, 'metrics': None
    }

    for p in candidates:
        try:
            df = pd.read_excel(p)
        except ImportError:
            print('Excel reader dependency missing. Please run: pip install openpyxl')
            continue
        except Exception:
            continue

        fcols = [c for c in base_cols if c in df.columns] + [c for c in morph_cols if c in df.columns]
        if not fcols:
            continue
        Xdf = df[fcols].copy()
        for c in Xdf.columns:
            Xdf[c] = pd.to_numeric(Xdf[c], errors='coerce')
        Xdf = Xdf.dropna(axis=1, how='all')
        for c in Xdf.columns:
            med = Xdf[c].median()
            if np.isfinite(med):
                Xdf[c] = Xdf[c].fillna(med)
        Xdf = Xdf.dropna(axis=1, how='any')
        if Xdf.empty:
            continue

        y, lname = None, None
        for lc in label_candidates:
            if lc in df.columns:
                s = df.loc[Xdf.index, lc]
                s = s.astype(str)
                if s.nunique() >= 2:
                    y = s.values
                    lname = lc
                    break

        bundle.update({
            'df': df.loc[Xdf.index].copy(),
            'X': Xdf.values.astype(float),
            'y': y,
            'feature_names': list(Xdf.columns),
            'label_name': lname,
            'data_source': str(p),
            'using_real_features': True,
            'using_real_labels': lname is not None,
        })
        break

    if not bundle['using_real_features']:
        rng = np.random.default_rng(42)
        X = rng.normal(0, 1, (180, 13))
        y = np.repeat(['Crack-dominated', 'Wear-dominated', 'Severe damage'], 60)
        bundle.update({
            'X': X, 'y': y, 'using_real_features': False, 'using_real_labels': False,
            'feature_names': base_cols, 'label_name': None, 'data_source': 'simulated'
        })

    print(f'Project root: {project_root}')
    print(f'Feature data source: {bundle["data_source"]}')
    print(f'Samples: {bundle["X"].shape[0]}')
    print(f'Features: {bundle["X"].shape[1]}')
    print(f'Feature columns: {", ".join(bundle["feature_names"])}')
    print(f'Label column: {bundle["label_name"] if bundle["label_name"] else "None"}')
    print(f'Using real features: {bundle["using_real_features"]}')
    print(f'Using real labels: {bundle["using_real_labels"]}')
    if not bundle['using_real_labels']:
        print('Warning: No real failure label found. PCA uses real features, but ML evaluation uses demo labels.')

    return bundle


def style_panel(ax, title, idx):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    ax.add_patch(FancyBboxPatch((0.02, 0.04), 0.96, 0.92, boxstyle='round,pad=0.012,rounding_size=0.025',
                                linewidth=1.2, edgecolor=BORDER, facecolor='white'))
    ax.text(0.5, 0.945, title, ha='center', va='top', fontsize=TITLE_FS, fontweight='bold')
    ax.text(0.05, 0.945, str(idx), ha='left', va='top', fontsize=11, fontweight='bold', color='#444444')


def draw_barrel_sampling(ax, root):
    style_panel(ax, 'Failed barrel sampling', 1)
    imgs = select_representative_images(root / '01_raw_macro_photos', n=2)
    ok = insert_image_grid(ax, imgs, area=(0.06, 0.38, 0.88, 0.48), ncols=2, nrows=1)
    if not ok:
        ax.add_patch(Rectangle((0.12, 0.50), 0.76, 0.10, facecolor='#f2f2f2', edgecolor='black', lw=0.8))
    ax.add_patch(Rectangle((0.10, 0.18), 0.80, 0.10, facecolor='#f7f7f7', edgecolor='black', lw=0.8))
    for x, t in [(0.18, 'Breech'), (0.50, 'Middle'), (0.82, 'Muzzle')]:
        ax.plot([x, x], [0.16, 0.30], ls='--', lw=1.5, color=RED)
        ax.text(x, 0.13, t, ha='center', fontsize=TEXT_FS)
    ax.text(0.06, 0.31, 'Macro photos', fontsize=TEXT_FS)
    ax.text(0.56, 0.31, 'SEM sampling locations', fontsize=TEXT_FS)


def draw_sem_observation(ax, root):
    style_panel(ax, 'Surface damage observation', 2)
    imgs = find_files(root, ['02_raw_SEM_images', '03_standardized_SEM_2048x1536', '06A_manual_annotations/images_for_annotation', '06B_semantic_segmentation'], IMAGE_EXTS)
    imgs = imgs[:6] if len(imgs) >= 6 else imgs[:4]
    n = len(imgs)
    if n >= 4:
        r, c = (2, 3) if n >= 6 else (2, 2)
        insert_image_grid(ax, imgs[:r*c], area=(0.05, 0.24, 0.90, 0.62), ncols=c, nrows=r)
    else:
        ax.text(0.08, 0.55, 'No SEM files found; using simplified fallback.', fontsize=TEXT_FS)
        for i, y in enumerate([0.62, 0.46, 0.30]):
            ax.plot([0.08, 0.92], [y, y-0.03*i], color='gray', lw=0.9)
    ax.text(0.05, 0.17, 'Thermal fatigue cracks; Directional wear grooves;', fontsize=TEXT_FS)
    ax.text(0.05, 0.11, 'Erosion pits; Spalling / severe damage', fontsize=TEXT_FS)


def draw_dataset_assembling(ax, root, bundle):
    style_panel(ax, 'Dataset assembling', 3)
    patches = select_representative_images(root / '04_patches_4x4', n=4)
    if patches:
        insert_image_grid(ax, patches, area=(0.05, 0.44, 0.44, 0.42), ncols=2, nrows=2)
    ax.annotate('', xy=(0.60, 0.62), xytext=(0.50, 0.62), arrowprops=dict(arrowstyle='->', lw=1.8, color=RED))
    ax.text(0.52, 0.66, '4×4 patches', fontsize=TEXT_FS)

    df = bundle['df'] if bundle['df'] is not None else pd.DataFrame()
    n_img = df['Image_ID'].nunique() if 'Image_ID' in df.columns else 'NA'
    n_patch = df['Patch_ID'].nunique() if 'Patch_ID' in df.columns else bundle['X'].shape[0]
    n_zone = df['Zone'].nunique() if 'Zone' in df.columns else 'NA'
    label_text = bundle['label_name'] if bundle['label_name'] else 'to be annotated'
    rows = [
        f'Image_ID: {n_img}', f'Patch_ID: {n_patch}', f'Zone: {n_zone}', 'Subset: Z1-Z4/Z5',
        f'Feature vector: p={bundle["X"].shape[1]}', f'Damage label: {label_text}'
    ]
    ax.add_patch(Rectangle((0.58, 0.26), 0.36, 0.56, facecolor='white', edgecolor='#808080', lw=0.8))
    for i, t in enumerate(rows):
        ax.text(0.60, 0.76 - i*0.09, t, fontsize=TEXT_FS)


def draw_feature_extraction(ax, bundle):
    style_panel(ax, 'Feature extraction', 4)
    names = bundle['feature_names']
    gray = sum(n in ['Mean', 'Median', 'StdDev', 'Skewness', 'Kurtosis'] for n in names)
    glcm = sum(n in ['Entropy', 'Contrast', 'Dissimilarity', 'Homogeneity', 'Energy', 'ASM', 'Correlation'] for n in names)
    morph = len(names) - gray - glcm
    bar_ax = ax.inset_axes([0.07, 0.50, 0.40, 0.32])
    bar_ax.bar(['Gray', 'GLCM', 'Morph'], [gray, glcm, max(0, morph)], color=['#9e9e9e', '#757575', '#4e79a7'])
    bar_ax.tick_params(labelsize=7)
    bar_ax.set_title('Feature categories', fontsize=7.4)

    h_ax = ax.inset_axes([0.53, 0.50, 0.40, 0.32])
    col = 'Entropy' if 'Entropy' in names else names[0]
    vals = bundle['X'][:, names.index(col)]
    h_ax.hist(vals, bins=12, color='#9ecae1', edgecolor='white')
    h_ax.set_title(f'{col} distribution', fontsize=7.4)
    h_ax.tick_params(labelsize=7)

    ax.text(0.08, 0.34, f'N = {bundle["X"].shape[0]} patches', fontsize=TEXT_FS)
    ax.text(0.08, 0.27, f'p = {bundle["X"].shape[1]} features', fontsize=TEXT_FS)
    ax.text(0.08, 0.20, 'Grayscale + GLCM + defect morphology', fontsize=TEXT_FS)


def prepare_pca_and_cluster(bundle):
    Xs = StandardScaler().fit_transform(bundle['X'])
    pca = PCA(n_components=2, random_state=42)
    scores = pca.fit_transform(Xs)
    bundle['pca_scores'] = scores
    bundle['pca_model'] = pca
    bundle['cluster_labels'] = KMeans(n_clusters=3, n_init=10, random_state=42).fit_predict(scores)


def draw_pca(ax, bundle):
    style_panel(ax, 'PCA dimensionality reduction', 5)
    scores = bundle['pca_scores']
    if bundle['using_real_labels']:
        groups = np.array(bundle['y'])
        note = f'colored by {bundle["label_name"]}'
    else:
        groups = bundle['cluster_labels'].astype(str)
        note = 'colored by KMeans clusters'
    uniq = np.unique(groups)
    cmap = plt.cm.tab10(np.linspace(0, 1, len(uniq)))
    p_ax = ax.inset_axes([0.10, 0.20, 0.80, 0.62])
    for c, g in zip(cmap, uniq):
        m = groups == g
        p_ax.scatter(scores[m, 0], scores[m, 1], s=12, color=c, label=str(g), alpha=0.82)
    p_ax.set_xlabel('PC1', fontsize=7); p_ax.set_ylabel('PC2', fontsize=7)
    p_ax.tick_params(labelsize=6.8)
    p_ax.legend(fontsize=6.2, loc='best', frameon=False)
    ev = bundle['pca_model'].explained_variance_ratio_[:2].sum() * 100
    ax.text(0.10, 0.10, f'Explained variance = {ev:.1f}% ({note})', fontsize=TEXT_FS)


def draw_clustering(ax, bundle):
    style_panel(ax, 'Clustering analysis', 6)
    s = bundle['pca_scores']
    labs = bundle['cluster_labels']
    c_ax = ax.inset_axes([0.06, 0.22, 0.54, 0.62])
    for k, col in zip([0, 1, 2], ['#d73027', '#4575b4', '#66a61e']):
        m = labs == k
        c_ax.scatter(s[m, 0], s[m, 1], s=12, color=col, alpha=0.82)
        if np.any(m):
            cx, cy = s[m, 0].mean(), s[m, 1].mean()
            rx = max(0.2, s[m, 0].std() * 2.2)
            ry = max(0.2, s[m, 1].std() * 2.0)
            c_ax.add_patch(Ellipse((cx, cy), rx, ry, fill=False, ec='black', lw=0.9))
    c_ax.set_xlabel('PC1', fontsize=7); c_ax.set_ylabel('PC2', fontsize=7); c_ax.tick_params(labelsize=6.8)

    vari = np.var(bundle['X'], axis=0)
    top_idx = np.argsort(vari)[-min(5, len(vari)):]
    mat = np.vstack([bundle['X'][labs == k][:, top_idx].mean(axis=0) if np.any(labs == k) else np.zeros(len(top_idx)) for k in [0, 1, 2]])
    mat = (mat - mat.min()) / (np.ptp(mat) + 1e-9)
    h_ax = ax.inset_axes([0.64, 0.30, 0.30, 0.50])
    h_ax.imshow(mat, cmap='YlGnBu', vmin=0, vmax=1, aspect='auto')
    h_ax.set_xticks(range(mat.shape[1])); h_ax.set_yticks([0, 1, 2])
    h_ax.set_xticklabels([bundle['feature_names'][i][:6] for i in top_idx], fontsize=6, rotation=30, ha='right')
    h_ax.set_yticklabels(['C1', 'C2', 'C3'], fontsize=6)


def draw_ml_training(ax):
    style_panel(ax, 'ML model training', 7)
    nodes = [(0.10, 'Input\nfeatures'), (0.32, 'Train/test\nsplit'), (0.56, 'Candidate\nclassifiers'), (0.82, 'Selected\nmodel')]
    for x, t in nodes:
        ax.add_patch(FancyBboxPatch((x-0.09, 0.48), 0.18, 0.20, boxstyle='round,pad=0.01,rounding_size=0.02',
                                    facecolor='#f9f9f9', edgecolor='#666666', lw=0.8))
        ax.text(x, 0.58, t, ha='center', va='center', fontsize=TEXT_FS)
    for i in range(len(nodes)-1):
        ax.annotate('', xy=(nodes[i+1][0]-0.10, 0.58), xytext=(nodes[i][0]+0.10, 0.58),
                    arrowprops=dict(arrowstyle='->', lw=1.6, color=RED))
    ax.text(0.46, 0.32, 'Random Forest | SVM | Gradient Boosting | KNN | MLP', ha='center', fontsize=TEXT_FS)
    ax.text(0.46, 0.24, 'Cross-validation for model selection', ha='center', fontsize=TEXT_FS)


def draw_prediction_evaluation(ax, bundle):
    title = 'Prediction evaluation' if bundle['using_real_labels'] else 'Prediction evaluation (demo, no real label)'
    style_panel(ax, title, 8)
    Xs = StandardScaler().fit_transform(bundle['X'])
    y = np.array(bundle['y']) if bundle['using_real_labels'] else bundle['cluster_labels'].astype(str)
    uniq, counts = np.unique(y, return_counts=True)
    use_real_eval = bundle['using_real_labels'] and np.all(counts >= 2) and len(uniq) >= 2

    if use_real_eval:
        Xtr, Xte, ytr, yte = train_test_split(Xs, y, test_size=0.3, random_state=42, stratify=y)
        model = RandomForestClassifier(n_estimators=260, random_state=42)
        model.fit(Xtr, ytr)
        yp = model.predict(Xte)
        labels = np.unique(np.concatenate([yte, yp]))
        cm = confusion_matrix(yte, yp, labels=labels)
        metrics = {
            'Accuracy': accuracy_score(yte, yp),
            'Precision': precision_score(yte, yp, average='macro', zero_division=0),
            'Recall': recall_score(yte, yp, average='macro', zero_division=0),
            'F1-score': f1_score(yte, yp, average='macro', zero_division=0),
        }
        bundle['trained_model'] = model
        bundle['metrics'] = metrics
    else:
        labels = np.array(['C1', 'C2', 'C3'])
        cm = np.array([[32, 4, 2], [5, 30, 3], [2, 3, 33]])
        metrics = {'Accuracy': 0.89, 'Precision': 0.88, 'Recall': 0.89, 'F1-score': 0.88}

    cm_ax = ax.inset_axes([0.08, 0.22, 0.47, 0.62])
    im = cm_ax.imshow(cm, cmap='Blues', vmin=0, vmax=max(1, cm.max()))
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            cm_ax.text(j, i, str(cm[i, j]), ha='center', va='center', fontsize=7)
    cm_ax.set_xticks(range(len(labels))); cm_ax.set_yticks(range(len(labels)))
    cm_ax.set_xticklabels([str(s)[:8] for s in labels], fontsize=6.6, rotation=30, ha='right')
    cm_ax.set_yticklabels([str(s)[:8] for s in labels], fontsize=6.6)
    plt.colorbar(im, ax=cm_ax, fraction=0.046, pad=0.04)
    for i, (k, v) in enumerate(metrics.items()):
        ax.text(0.62, 0.76 - i*0.12, f'{k}: {v:.2f}', fontsize=TEXT_FS)
    if not bundle['using_real_labels']:
        ax.text(0.62, 0.24, 'Real failure label not found', fontsize=TEXT_FS, color=RED)


def draw_explainability_decision(ax, bundle):
    style_panel(ax, 'Explainability & maintenance decision', 9)
    if bundle.get('trained_model') is not None and bundle['using_real_labels']:
        imp = bundle['trained_model'].feature_importances_
        idx = np.argsort(imp)[-7:][::-1]
        feats = [bundle['feature_names'][i] for i in idx]
        vals = imp[idx]
        left_title = 'RF feature importance'
    else:
        feats = ['Defect area fraction', 'Entropy', 'Contrast', 'StdDev', 'Skewness', 'Homogeneity', 'Correlation']
        vals = np.array([0.26, 0.21, 0.17, 0.14, 0.10, 0.07, 0.05])
        left_title = 'Feature importance demo'
    b_ax = ax.inset_axes([0.04, 0.20, 0.48, 0.66])
    y = np.arange(len(feats))
    b_ax.barh(y, vals, color='#8da0cb')
    b_ax.set_yticks(y); b_ax.set_yticklabels([f[:22] for f in feats], fontsize=6.6)
    b_ax.invert_yaxis(); b_ax.tick_params(axis='x', labelsize=6.4)
    b_ax.set_title(left_title, fontsize=7.6)

    ax.add_patch(Rectangle((0.58, 0.22), 0.36, 0.60, facecolor='#fbfbfb', edgecolor='#666666', lw=0.8))
    for i, d in enumerate(['Continue monitoring', 'Preventive maintenance', 'Repair recommendation', 'Scrap / replacement']):
        ax.text(0.61, 0.72 - i*0.13, f'• {d}', fontsize=TEXT_FS)


def connect_axes(fig, ax_from, ax_to, direction='right', color=RED):
    a = ax_from.get_position(); b = ax_to.get_position()
    if direction == 'right':
        start = (a.x1 + 0.003, (a.y0+a.y1)/2)
        end = (b.x0 - 0.003, (b.y0+b.y1)/2)
    elif direction == 'left':
        start = (a.x0 - 0.003, (a.y0+a.y1)/2)
        end = (b.x1 + 0.003, (b.y0+b.y1)/2)
    elif direction == 'down':
        start = ((a.x0+a.x1)/2, a.y0 - 0.004)
        end = ((b.x0+b.x1)/2, b.y1 + 0.004)
    else:  # up
        start = ((a.x0+a.x1)/2, a.y1 + 0.004)
        end = ((b.x0+b.x1)/2, b.y0 - 0.004)
    fig.add_artist(FancyArrowPatch(start, end, transform=fig.transFigure, arrowstyle='-|>', mutation_scale=15,
                                   lw=2.4, color=color, zorder=2))


def add_feedback_arrow(fig, ax_from, ax_to):
    a = ax_from.get_position(); b = ax_to.get_position()
    start = (a.x1 + 0.005, a.y0 + 0.02)
    end = (b.x1 + 0.005, b.y0 + 0.40)
    fig.add_artist(FancyArrowPatch(start, end, transform=fig.transFigure,
                                   arrowstyle='->', mutation_scale=12,
                                   connectionstyle='arc3,rad=0.55',
                                   lw=1.5, linestyle='--', color=LIGHT_RED, alpha=0.6, zorder=1))
    fig.text((start[0]+end[0])/2 + 0.005, (start[1]+end[1])/2, 'Feature refinement feedback',
             fontsize=7, color=LIGHT_RED, rotation=82, alpha=0.8)


def main():
    set_font()
    root = find_project_root()
    bundle = load_real_feature_data(root)
    prepare_pca_and_cluster(bundle)

    fig = plt.figure(figsize=(FIG_W, FIG_H), facecolor='white')
    gs = fig.add_gridspec(3, 3, left=0.03, right=0.95, top=0.95, bottom=0.12, wspace=0.10, hspace=0.18)

    ax1 = fig.add_subplot(gs[0, 0]); ax2 = fig.add_subplot(gs[0, 1]); ax3 = fig.add_subplot(gs[0, 2])
    ax6 = fig.add_subplot(gs[1, 0]); ax5 = fig.add_subplot(gs[1, 1]); ax4 = fig.add_subplot(gs[1, 2])
    ax7 = fig.add_subplot(gs[2, 0]); ax8 = fig.add_subplot(gs[2, 1]); ax9 = fig.add_subplot(gs[2, 2])

    draw_barrel_sampling(ax1, root)
    draw_sem_observation(ax2, root)
    draw_dataset_assembling(ax3, root, bundle)
    draw_feature_extraction(ax4, bundle)
    draw_pca(ax5, bundle)
    draw_clustering(ax6, bundle)
    draw_ml_training(ax7)
    draw_prediction_evaluation(ax8, bundle)
    draw_explainability_decision(ax9, bundle)

    connect_axes(fig, ax1, ax2, 'right')
    connect_axes(fig, ax2, ax3, 'right')
    connect_axes(fig, ax3, ax4, 'down')
    connect_axes(fig, ax4, ax5, 'left')
    connect_axes(fig, ax5, ax6, 'left')
    connect_axes(fig, ax6, ax7, 'down')
    connect_axes(fig, ax7, ax8, 'right')
    connect_axes(fig, ax8, ax9, 'right')
    add_feedback_arrow(fig, ax9, ax4)

    fig.text(0.5, 0.055,
             'Fig. 1. Architecture summary of the proposed barrel failure mode identification and machine-learning-assisted assessment framework.',
             ha='center', va='center', fontsize=11)

    out_name = 'Fig1_barrel_failure_ml_architecture'
    out_dir = root / '07_figures_main'
    out_dir.mkdir(parents=True, exist_ok=True)
    for ext in ['png', 'pdf', 'svg']:
        fig.savefig(out_dir / f'{out_name}.{ext}', dpi=600, bbox_inches='tight', facecolor='white')
        fig.savefig(f'{out_name}.{ext}', dpi=600, bbox_inches='tight', facecolor='white')

    plt.close(fig)
    print('Figure saved as Fig1_barrel_failure_ml_architecture.png/pdf/svg')


if __name__ == '__main__':
    main()
