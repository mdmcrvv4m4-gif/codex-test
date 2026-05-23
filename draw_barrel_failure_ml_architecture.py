import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Ellipse, FancyArrowPatch
from matplotlib import rcParams
from sklearn.decomposition import PCA
from sklearn.datasets import make_blobs
from sklearn.cluster import KMeans


FIG_W, FIG_H = 16, 10  # 16:10 layout
RED = '#c00000'
BORDER = '#cfcfcf'
TITLE_FS = 12
TEXT_FS = 9
SMALL_FS = 8


def set_font():
    """Use Times New Roman if available, otherwise DejaVu Serif."""
    available = {f.name for f in plt.matplotlib.font_manager.fontManager.ttflist}
    if 'Times New Roman' in available:
        rcParams['font.family'] = 'Times New Roman'
    else:
        rcParams['font.family'] = 'DejaVu Serif'


def style_panel(ax, title):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    panel = FancyBboxPatch(
        (0.02, 0.08), 0.96, 0.88,
        boxstyle='round,pad=0.012,rounding_size=0.03',
        linewidth=1.2, edgecolor=BORDER, facecolor='white'
    )
    ax.add_patch(panel)
    ax.text(0.5, 0.99, title, ha='center', va='top', fontsize=TITLE_FS, fontweight='bold', color='black')


def draw_barrel_sampling(ax):
    style_panel(ax, 'Failed barrel sampling')
    ax.add_patch(Rectangle((0.12, 0.45), 0.76, 0.12, facecolor='#f2f2f2', edgecolor='black', lw=1.0))
    ax.add_patch(Ellipse((0.12, 0.51), 0.08, 0.12, facecolor='#e0e0e0', edgecolor='black', lw=1.0))
    ax.add_patch(Ellipse((0.88, 0.51), 0.08, 0.12, facecolor='#fafafa', edgecolor='black', lw=1.0))
    for x, label in [(0.18, 'Breech'), (0.50, 'Middle'), (0.82, 'Muzzle')]:
        ax.plot([x, x], [0.40, 0.62], '--', color=RED, lw=1.8)
        ax.text(x, 0.36, label, ha='center', va='top', fontsize=SMALL_FS)
    ax.text(0.18, 0.72, 'Macro photos', fontsize=SMALL_FS, color='black')
    ax.text(0.64, 0.72, 'SEM sampling', fontsize=SMALL_FS, color='black')


def draw_sem_observation(ax):
    style_panel(ax, 'Surface damage observation')
    rng = np.random.default_rng(42)
    positions = [(0.08, 0.57), (0.39, 0.57), (0.70, 0.57), (0.08, 0.20), (0.39, 0.20), (0.70, 0.20)]
    for i, (x, y) in enumerate(positions):
        w, h = 0.22, 0.28
        arr = rng.normal(0.55, 0.15, (30, 30))
        arr = np.clip(arr, 0, 1)
        ax.imshow(arr, extent=(x, x+w, y, y+h), cmap='gray', vmin=0, vmax=1, zorder=1)
        ax.add_patch(Rectangle((x, y), w, h, facecolor='none', edgecolor='black', lw=0.8, zorder=2))
        if i in (0, 3):
            ax.plot([x+0.03, x+w-0.02], [y+0.04, y+h-0.05], color='black', lw=1.1)
            ax.plot([x+0.05, x+w-0.05], [y+h-0.07, y+0.03], color='black', lw=0.8)
        elif i in (1, 4):
            for yy in np.linspace(y+0.04, y+h-0.04, 4):
                ax.plot([x+0.03, x+w-0.03], [yy, yy+0.02], color='dimgray', lw=1.0)
        else:
            for _ in range(4):
                cx, cy = rng.uniform(x+0.04, x+w-0.04), rng.uniform(y+0.05, y+h-0.05)
                ax.add_patch(Ellipse((cx, cy), 0.04, 0.025, facecolor='none', edgecolor='black', lw=0.8))
    ax.text(0.04, 0.10,
            'thermal fatigue cracks | directional wear grooves | erosion pits | coating/substrate spalling',
            fontsize=7.5)


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
    fields = ['Image_ID', 'Patch_ID', 'Zone', 'Failure label']
    for i, f in enumerate(fields):
        y = 0.66 - i*0.11
        ax.text(0.77, y, f, fontsize=SMALL_FS)
        ax.plot([0.75, 0.95], [y-0.04, y-0.04], color='#d0d0d0', lw=0.8)


def draw_feature_extraction(ax):
    style_panel(ax, 'Feature extraction')
    cats = ['Gray', 'GLCM', 'Morph.']
    vals = [6, 8, 5]
    x = np.arange(3)
    ax.bar(0.10 + x*0.10, vals, width=0.07, color=['#999999', '#7f7f7f', '#4d4d4d'])
    ax.set_ylim(0, 12)
    for i, c in enumerate(cats):
        ax.text(0.10 + i*0.10, 0.13, c, fontsize=7, ha='center', transform=ax.transAxes)
    ax.text(0.08, 0.73, 'Grayscale statistics', fontsize=SMALL_FS)
    ax.text(0.08, 0.67, 'GLCM texture features', fontsize=SMALL_FS)
    ax.text(0.08, 0.61, 'Defect morphology features', fontsize=SMALL_FS)
    ax.add_patch(Rectangle((0.45, 0.24), 0.48, 0.56, facecolor='white', edgecolor='black', lw=0.9))
    table_lines = [
        'Mean, StdDev, Skewness, Kurtosis',
        'Entropy, Contrast, Homogeneity, Correlation',
        'Defect area fraction'
    ]
    for i, t in enumerate(table_lines):
        ax.text(0.47, 0.70 - i*0.16, t, fontsize=7.5)


def draw_pca(ax):
    style_panel(ax, 'PCA dimensionality reduction')
    X, y = make_blobs(n_samples=120, centers=3, n_features=8, cluster_std=1.8, random_state=7)
    pca = PCA(n_components=3, random_state=7)
    Z = pca.fit_transform(X)
    colors = ['#d73027', '#4575b4', '#66a61e']
    labels = ['Crack-dominated', 'Wear-dominated', 'Severe damage']
    for k in range(3):
        pts = Z[y == k]
        ax.scatter(0.12 + (pts[:, 0]-Z[:,0].min())/(Z[:,0].ptp()+1e-9)*0.75,
                   0.22 + (pts[:, 1]-Z[:,1].min())/(Z[:,1].ptp()+1e-9)*0.58,
                   s=12, c=colors[k], alpha=0.8, label=labels[k])
    ax.text(0.12, 0.18, 'PC1', fontsize=SMALL_FS)
    ax.text(0.04, 0.24, 'PC2', fontsize=SMALL_FS, rotation=90)
    ax.text(0.80, 0.76, 'PC3', fontsize=SMALL_FS)
    ax.legend(loc='lower left', fontsize=6.8, frameon=False)


def draw_clustering(ax):
    style_panel(ax, 'Clustering analysis')
    X, _ = make_blobs(n_samples=90, centers=3, n_features=2, cluster_std=1.2, random_state=5)
    km = KMeans(n_clusters=3, random_state=5, n_init=10).fit(X)
    labels = km.labels_
    colors = ['#f46d43', '#74add1', '#66bd63']
    xn = (X[:, 0]-X[:, 0].min())/(X[:, 0].ptp()+1e-9)
    yn = (X[:, 1]-X[:, 1].min())/(X[:, 1].ptp()+1e-9)
    for k, c in enumerate(colors):
        mask = labels == k
        ax.scatter(0.08 + xn[mask]*0.50, 0.20 + yn[mask]*0.60, s=14, c=c)
        cx, cy = 0.08 + xn[mask].mean()*0.50, 0.20 + yn[mask].mean()*0.60
        ax.add_patch(Ellipse((cx, cy), 0.18, 0.12, fill=False, edgecolor='black', lw=1.0))
        ax.text(cx, cy+0.08, f'Cluster {k+1}', ha='center', fontsize=7)
    heat = np.array([[0.8, 0.5, 0.3], [0.3, 0.9, 0.6], [0.5, 0.4, 0.85]])
    ax.imshow(heat, extent=(0.68, 0.94, 0.28, 0.70), cmap='YlGnBu', vmin=0, vmax=1)
    ax.add_patch(Rectangle((0.68, 0.28), 0.26, 0.42, fill=False, edgecolor='black', lw=0.8))
    ax.text(0.81, 0.73, 'Feature difference', fontsize=7, ha='center')


def draw_ml_training(ax):
    style_panel(ax, 'ML model training')
    models = ['Random\nForest', 'SVM', 'XGBoost', 'KNN', 'Neural\nNetwork']
    xs = [0.12, 0.30, 0.48, 0.66, 0.84]
    for x, m in zip(xs, models):
        ax.add_patch(FancyBboxPatch((x-0.07, 0.50), 0.14, 0.18, boxstyle='round,pad=0.01,rounding_size=0.02',
                                    facecolor='#f7f7f7', edgecolor='black', lw=0.9))
        ax.text(x, 0.59, m, ha='center', va='center', fontsize=7.5)
    ax.annotate('', xy=(0.80, 0.38), xytext=(0.20, 0.38), arrowprops=dict(arrowstyle='->', color=RED, lw=2))
    ax.text(0.50, 0.40, 'training', color=RED, ha='center', fontsize=SMALL_FS)
    ax.text(0.10, 0.24, 'train/test split', fontsize=SMALL_FS)
    ax.text(0.42, 0.24, 'cross-validation', fontsize=SMALL_FS)
    ax.text(0.74, 0.24, 'model selection', fontsize=SMALL_FS, ha='center')


def draw_prediction_evaluation(ax):
    style_panel(ax, 'Prediction evaluation')
    cm = np.array([[34, 3, 1], [4, 29, 2], [2, 3, 31]])
    ax.imshow(cm, extent=(0.08, 0.55, 0.22, 0.78), cmap='Blues')
    for i in range(3):
        for j in range(3):
            x = 0.08 + (j + 0.5) * (0.47/3)
            y = 0.22 + (2.5 - i) * (0.56/3)
            ax.text(x, y, str(cm[i, j]), ha='center', va='center', fontsize=8)
    classes = ['Crack', 'Wear', 'Severe']
    for j, c in enumerate(classes):
        ax.text(0.08 + (j + 0.5) * (0.47/3), 0.18, c, ha='center', fontsize=7)
        ax.text(0.04, 0.22 + (2.5 - j) * (0.56/3), c, va='center', fontsize=7)
    ax.text(0.57, 0.68, 'Accuracy: 0.90', fontsize=SMALL_FS)
    ax.text(0.57, 0.58, 'Precision: 0.89', fontsize=SMALL_FS)
    ax.text(0.57, 0.48, 'Recall: 0.90', fontsize=SMALL_FS)
    ax.text(0.57, 0.38, 'F1-score: 0.89', fontsize=SMALL_FS)


def draw_explainability_decision(ax):
    style_panel(ax, 'Explainability & maintenance decision')
    feats = ['Defect area fraction', 'Entropy', 'Contrast', 'StdDev', 'Crack density', 'Groove orientation']
    vals = np.array([0.28, 0.22, 0.18, 0.14, 0.10, 0.08])
    y = np.arange(len(feats))
    ax.barh(0.18 + y*0.08, vals, height=0.05, color='#8da0cb')
    for i, f in enumerate(feats):
        ax.text(0.02, 0.185 + i*0.08, f, fontsize=6.8, va='center')
    ax.text(0.36, 0.75, 'SHAP-like importance', fontsize=7.5)
    ax.add_patch(Rectangle((0.58, 0.22), 0.36, 0.58, facecolor='#fbfbfb', edgecolor='black', lw=0.9))
    decisions = ['Continue monitoring', 'Preventive maintenance', 'Repair recommendation', 'Scrap / replacement']
    for i, d in enumerate(decisions):
        yy = 0.70 - i*0.13
        ax.text(0.61, yy, f'• {d}', fontsize=SMALL_FS)


def add_global_arrows(fig, axes):
    order = [axes[0], axes[1], axes[2], axes[5], axes[8], axes[7], axes[6], axes[3], axes[4]]
    # Actually connect in requested logical chain across row-major panels.
    chain = [axes[0], axes[1], axes[2], axes[3], axes[4], axes[5], axes[6], axes[7], axes[8]]
    for i in range(len(chain)-1):
        a, b = chain[i].get_position(), chain[i+1].get_position()
        x1, y1 = a.x1, (a.y0+a.y1)/2
        x2, y2 = b.x0, (b.y0+b.y1)/2
        if abs(y1-y2) > 0.1:
            x1, y1 = (a.x0+a.x1)/2, a.y0
            x2, y2 = (b.x0+b.x1)/2, b.y1
        fig.add_artist(FancyArrowPatch((x1, y1), (x2, y2), transform=fig.transFigure,
                                       arrowstyle='-|>', mutation_scale=16, lw=2.4, color=RED))

    # feedback arrow: module 9 -> module 4
    a, b = axes[8].get_position(), axes[3].get_position()
    start = (a.x0 + 0.90*(a.x1-a.x0), a.y0 + 0.15*(a.y1-a.y0))
    end = (b.x0 + 0.05*(b.x1-b.x0), b.y0 + 0.85*(b.y1-b.y0))
    fb = FancyArrowPatch(start, end, transform=fig.transFigure, arrowstyle='-|>',
                         connectionstyle='arc3,rad=-0.35', mutation_scale=16,
                         lw=2.4, color=RED, linestyle='-')
    fig.add_artist(fb)


def main():
    set_font()
    fig, axs = plt.subplots(3, 3, figsize=(FIG_W, FIG_H), facecolor='white')
    plt.subplots_adjust(left=0.03, right=0.97, top=0.95, bottom=0.11, wspace=0.14, hspace=0.20)

    draw_barrel_sampling(axs[0, 0])
    draw_sem_observation(axs[0, 1])
    draw_dataset_assembling(axs[0, 2])
    draw_feature_extraction(axs[1, 0])
    draw_pca(axs[1, 1])
    draw_clustering(axs[1, 2])
    draw_ml_training(axs[2, 0])
    draw_prediction_evaluation(axs[2, 1])
    draw_explainability_decision(axs[2, 2])

    axes_list = [axs[0, 0], axs[0, 1], axs[0, 2], axs[1, 0], axs[1, 1], axs[1, 2], axs[2, 0], axs[2, 1], axs[2, 2]]
    add_global_arrows(fig, axes_list)

    fig.text(
        0.5, 0.045,
        'Fig. 1. Architecture summary of the proposed barrel failure mode identification and machine-learning-assisted assessment framework.',
        ha='center', va='center', fontsize=11
    )

    outbase = 'Fig1_barrel_failure_ml_architecture'
    fig.savefig(f'{outbase}.png', dpi=600, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{outbase}.pdf', dpi=600, bbox_inches='tight', facecolor='white')
    fig.savefig(f'{outbase}.svg', dpi=600, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print('Figure saved as Fig1_barrel_failure_ml_architecture.png/pdf/svg')


if __name__ == '__main__':
    main()
