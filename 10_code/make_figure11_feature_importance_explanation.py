import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split


BASE_WINDOWS = Path(r"E:\Barrel_SEM_Z1_Z4_New")
BASE_LOCAL = Path(__file__).resolve().parents[1]
BASE_DIR = BASE_WINDOWS if BASE_WINDOWS.exists() else BASE_LOCAL

S14_PATH = BASE_DIR / "05_tables" / "S14_RF_feature_importance_Z1_Z4.xlsx"
S10_PATH = BASE_DIR / "05_tables" / "S10_ML_labeled_feature_table_Z1_Z4.xlsx"
OUT_DIR = BASE_DIR / "07_figures_main"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _find_col(columns, candidates):
    lower_map = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    for col in columns:
        col_l = col.lower()
        if any(cand.lower() in col_l for cand in candidates):
            return col
    return None


def clean_feature_name(name: str) -> str:
    mapping = {
        "stddev": "Standard deviation",
        "dsi_semantic": "Semantic DSI",
    }
    x = str(name).strip()
    key = x.lower()
    if key in mapping:
        return mapping[key]
    x = x.replace("_", " ").replace("-", " ")
    x = " ".join(x.split())
    return x[:1].upper() + x[1:]


def wrap_label(s, width=28):
    return "\n".join(textwrap.wrap(s, width=width))


def pick_task3_s14(df, feature_col, importance_col, task_col):
    if task_col is None:
        return df.copy(), "No task column found; used all rows"
    task_vals = df[task_col].astype(str)
    mask = task_vals.str.lower().str.contains(r"task\s*3|failure|failure_mode", regex=True, na=False)
    if mask.any():
        sub = df.loc[mask].copy()
        return sub, sub[task_col].mode().iloc[0]
    best_task = (
        df.groupby(task_col)[importance_col]
        .mean()
        .sort_values(ascending=False)
        .index[0]
    )
    return df[df[task_col] == best_task].copy(), f"Fallback task: {best_task}"


def annotate_barh(ax, bars, vals):
    xmax = max(vals) if len(vals) else 1
    for b, v in zip(bars, vals):
        ax.text(b.get_width() + xmax * 0.01, b.get_y() + b.get_height()/2, f"{v:.3f}", va="center", fontsize=8)


def main():
    summary_lines = []

    if not S14_PATH.exists():
        raise FileNotFoundError(f"S14 not found: {S14_PATH}")
    if not S10_PATH.exists():
        raise FileNotFoundError(f"S10 not found: {S10_PATH}")

    s14 = pd.read_excel(S14_PATH)
    feat_col = _find_col(s14.columns, ["Feature", "feature", "feature_name", "Variable"])
    imp_col = _find_col(s14.columns, ["Importance", "importance", "rf_importance", "mean_decrease_impurity", "MDI"])
    task_col = _find_col(s14.columns, ["Task", "task", "task_name"])
    if feat_col is None or imp_col is None:
        raise ValueError("Could not detect feature/importance columns in S14")

    s14_task, s14_task_used = pick_task3_s14(s14, feat_col, imp_col, task_col)
    s14_task = s14_task[[feat_col, imp_col]].dropna()
    s14_task[imp_col] = pd.to_numeric(s14_task[imp_col], errors="coerce")
    s14_task = s14_task.dropna(subset=[imp_col]).sort_values(imp_col, ascending=False)
    top_rf = s14_task.head(10).copy()
    top_rf["feature_display"] = top_rf[feat_col].map(clean_feature_name)
    top_rf.to_excel(OUT_DIR / "Figure11_RF_importance_top_features.xlsx", index=False)

    s10 = pd.read_excel(S10_PATH)
    label_candidates = ["failure_mode", "failure_mode_3class", "mode_label", "Task3_label", "y_task3", "failure_label"]
    y_col = _find_col(s10.columns, label_candidates)

    if y_col is None:
        summary_lines.append("Failed to identify Task 3 label column in S10.")
        summary_lines.append("S10 columns:")
        summary_lines.extend([f"- {c}" for c in s10.columns])
        raise ValueError("Task 3 label column not found in S10")

    exclude_keywords = [
        "patch_id", "image_id", "zone", "region", "label", "class", "target", "severity", "failure", "mode",
        "y_true", "y_pred", "prediction", "predicted", "file", "path", "mask", "overlay", "status", "split",
        "fold", "rank", "count"
    ]

    y = s10[y_col]
    X_num = s10.select_dtypes(include=[np.number]).copy()
    X_num = X_num.dropna(axis=1, how="all")

    keep_cols = []
    for c in X_num.columns:
        cl = c.lower()
        if c == y_col:
            continue
        if any(k in cl for k in exclude_keywords):
            continue
        keep_cols.append(c)

    X = X_num[keep_cols].copy()
    valid_mask = y.notna()
    X = X.loc[valid_mask]
    y = y.loc[valid_mask]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    imputer = SimpleImputer(strategy="median")
    X_train_imp = pd.DataFrame(imputer.fit_transform(X_train), columns=X_train.columns, index=X_train.index)
    X_test_imp = pd.DataFrame(imputer.transform(X_test), columns=X_test.columns, index=X_test.index)

    clf = RandomForestClassifier(
        n_estimators=500,
        random_state=42,
        class_weight="balanced",
        n_jobs=-1,
    )
    clf.fit(X_train_imp, y_train)
    y_pred = clf.predict(X_test_imp)

    acc = accuracy_score(y_test, y_pred)
    f1_macro = f1_score(y_test, y_pred, average="macro")
    f1_weighted = f1_score(y_test, y_pred, average="weighted")

    perm = permutation_importance(
        clf,
        X_test_imp,
        y_test,
        n_repeats=30,
        random_state=42,
        scoring="f1_macro",
        n_jobs=-1,
    )
    perm_df = pd.DataFrame({
        "feature": X_test_imp.columns,
        "perm_importance_mean": perm.importances_mean,
        "perm_importance_std": perm.importances_std,
    }).sort_values("perm_importance_mean", ascending=False)

    top_perm = perm_df.head(10).copy()
    top_perm["feature_display"] = top_perm["feature"].map(clean_feature_name)
    top_perm.to_excel(OUT_DIR / "Figure11_permutation_importance_top_features.xlsx", index=False)

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), facecolor="white")

    rf_plot = top_rf.iloc[::-1]
    ylabels_a = [wrap_label(x) for x in rf_plot["feature_display"]]
    bars_a = axes[0].barh(ylabels_a, rf_plot[imp_col], color="#4C78A8")
    axes[0].set_xlabel("RF feature importance")
    axes[0].set_title("(a) RF impurity-based importance", loc="left")
    annotate_barh(axes[0], bars_a, rf_plot[imp_col].values)

    pm_plot = top_perm.iloc[::-1]
    ylabels_b = [wrap_label(x) for x in pm_plot["feature_display"]]
    bars_b = axes[1].barh(
        ylabels_b,
        pm_plot["perm_importance_mean"],
        xerr=pm_plot["perm_importance_std"],
        color="#F58518",
        ecolor="black",
        capsize=2,
    )
    axes[1].set_xlabel("Permutation importance decrease in Macro-F1")
    axes[1].set_title("(b) Permutation importance", loc="left")
    annotate_barh(axes[1], bars_b, pm_plot["perm_importance_mean"].values)

    for ax in axes:
        ax.set_facecolor("white")
        ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    main_png = OUT_DIR / "Figure_11_feature_importance_explanation.png"
    main_tif = OUT_DIR / "Figure_11_feature_importance_explanation.tif"
    main_pdf = OUT_DIR / "Figure_11_feature_importance_explanation.pdf"
    fig.savefig(main_png, dpi=600, bbox_inches="tight")
    fig.savefig(main_tif, dpi=600, bbox_inches="tight")
    fig.savefig(main_pdf, dpi=600, bbox_inches="tight")
    plt.close(fig)

    shap_success = False
    shap_msg = ""
    try:
        import shap
        explainer = shap.TreeExplainer(clf)
        shap_values = explainer.shap_values(X_test_imp)
        plt.figure(figsize=(8, 6), facecolor="white")
        shap.summary_plot(shap_values, X_test_imp, plot_type="bar", show=False)
        plt.tight_layout()
        shap_png = OUT_DIR / "Figure_11_SHAP_summary_Task3.png"
        shap_tif = OUT_DIR / "Figure_11_SHAP_summary_Task3.tif"
        shap_pdf = OUT_DIR / "Figure_11_SHAP_summary_Task3.pdf"
        plt.savefig(shap_png, dpi=600, bbox_inches="tight")
        plt.savefig(shap_tif, dpi=600, bbox_inches="tight")
        plt.savefig(shap_pdf, dpi=600, bbox_inches="tight")
        plt.close()
        shap_success = True
    except Exception:
        shap_msg = "SHAP was skipped because shap was not installed or failed in the current environment."

    rf_feats = [str(x) for x in top_rf[feat_col].tolist()]
    perm_feats = [str(x) for x in top_perm["feature"].tolist()]
    overlap = [f for f in rf_feats if f in set(perm_feats)]

    summary_lines.extend([
        f"S14 task used: {s14_task_used}",
        f"S10 Task 3 label column: {y_col}",
        f"Train samples: {len(X_train_imp)}, Test samples: {len(X_test_imp)}",
        f"Test Accuracy: {acc:.4f}",
        f"Test Macro-F1: {f1_macro:.4f}",
        f"Test Weighted-F1: {f1_weighted:.4f}",
        "RF importance Top 10:",
        *[f"- {a}: {b:.6f}" for a, b in zip(top_rf[feat_col], top_rf[imp_col])],
        "Permutation importance Top 10:",
        *[f"- {a}: {b:.6f}" for a, b in zip(top_perm['feature'], top_perm['perm_importance_mean'])],
        "Common key features between methods:",
        *([f"- {x}" for x in overlap] if overlap else ["- None"]),
        "SHAP status: success" if shap_success else f"SHAP status: failed/skipped. {shap_msg}",
    ])

    summary_path = OUT_DIR / "Figure11_feature_importance_summary.txt"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    outputs = [
        main_png, main_tif, main_pdf,
        OUT_DIR / "Figure11_RF_importance_top_features.xlsx",
        OUT_DIR / "Figure11_permutation_importance_top_features.xlsx",
        summary_path,
    ]
    if shap_success:
        outputs.extend([
            OUT_DIR / "Figure_11_SHAP_summary_Task3.png",
            OUT_DIR / "Figure_11_SHAP_summary_Task3.tif",
            OUT_DIR / "Figure_11_SHAP_summary_Task3.pdf",
        ])

    print("Generated files:")
    for p in outputs:
        print(str(p))


if __name__ == "__main__":
    main()
