import os
from pathlib import Path
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TASK_ORDER = ["Task 1: Zone", "Task 2: Severity", "Task 3: Failure mode"]
MODEL_ORDER = ["Logistic Regression", "SVM", "Random Forest"]


def resolve_project_root() -> Path:
    env_root = os.environ.get("BARREL_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    p = Path(__file__).resolve()
    return p.parent.parent if p.parent.name == "10_code" else p.parents[1]


def norm(x) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(x).strip().lower())


def find_col(df: pd.DataFrame, target: str):
    t = norm(target)
    for c in df.columns:
        if norm(c) == t:
            return c
    for c in df.columns:
        if t in norm(c):
            return c
    return None


def map_task(v: str):
    n = norm(v)
    if "task1zoneclassification" in n or n == "task1" or n == "zone" or "zoneclassification" in n:
        return "Task 1: Zone"
    if "task2damageseverity" in n or n == "task2" or n == "severity" or "damageseverity" in n:
        return "Task 2: Severity"
    if "task3failuremode3class" in n or n == "task3" or n == "failuremode" or "failuremode3class" in n:
        return "Task 3: Failure mode"
    return None


def map_model(v: str):
    n = norm(v)
    if "logisticregression" in n or n == "logistic":
        return "Logistic Regression"
    if "supportvectormachine" in n or n == "svm" or "supportvector" in n:
        return "SVM"
    if "randomforest" in n:
        return "Random Forest"
    return None


def write_diagnosis(xlsx: Path, out_txt: Path, debug_xlsx: Path):
    xls = pd.ExcelFile(xlsx)
    sheet_dfs = {}
    lines = [f"Workbook path: {xlsx}", "Sheet names:"]
    for s in xls.sheet_names:
        lines.append(f"- {s}")

    for s in xls.sheet_names:
        df = pd.read_excel(xlsx, sheet_name=s)
        sheet_dfs[s] = df
        lines.append("")
        lines.append(f"=== Sheet: {s} ===")
        lines.append(f"shape: {df.shape}")
        lines.append(f"columns: {list(df.columns)}")
        lines.append("first 30 rows:")
        lines.append(df.head(30).to_string(index=False))

    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    with pd.ExcelWriter(debug_xlsx, engine="openpyxl") as writer:
        for s, df in sheet_dfs.items():
            safe_name = str(s)[:31]
            df.head(30).to_excel(writer, sheet_name=safe_name, index=False)

    return xls


def compute_metrics_from_expanded_table(df: pd.DataFrame) -> pd.DataFrame:
    task_col = find_col(df, "Task")
    model_col = find_col(df, "Model")
    label_col = find_col(df, "Label")
    precision_col = find_col(df, "Precision")
    recall_col = find_col(df, "Recall")
    f1_col = find_col(df, "F1")
    support_col = find_col(df, "Support")

    required = [task_col, model_col, label_col, precision_col, recall_col, f1_col, support_col]
    if any(c is None for c in required):
        missing = [n for n, c in zip(["Task", "Model", "Label", "Precision", "Recall", "F1", "Support"], required) if c is None]
        raise ValueError(f"Missing required columns in expanded S13 table: {missing}")

    d = df[[task_col, model_col, label_col, recall_col, f1_col, support_col]].copy()
    d.columns = ["Task", "Model", "Label", "Recall", "F1", "Support"]

    d["Task"] = d["Task"].map(map_task)
    d["Model"] = d["Model"].map(map_model)

    d["Recall"] = pd.to_numeric(d["Recall"], errors="coerce")
    d["F1"] = pd.to_numeric(d["F1"], errors="coerce")
    d["Support"] = pd.to_numeric(d["Support"], errors="coerce")

    d = d.dropna(subset=["Task", "Model", "Recall", "F1", "Support"]).copy()
    d = d[d["Support"] > 0].copy()

    def agg_func(g):
        support_sum = g["Support"].sum()
        macro_f1 = g["F1"].mean()
        weighted_f1 = (g["F1"] * g["Support"]).sum() / support_sum
        accuracy = (g["Recall"] * g["Support"]).sum() / support_sum
        return pd.Series({"Accuracy": accuracy, "Macro_F1": macro_f1, "Weighted_F1": weighted_f1})

    out = d.groupby(["Task", "Model"], as_index=False).apply(agg_func).reset_index(drop=True)

    full = pd.MultiIndex.from_product([TASK_ORDER, MODEL_ORDER], names=["Task", "Model"]).to_frame(index=False)
    out = full.merge(out, on=["Task", "Model"], how="left")

    if out[["Accuracy", "Macro_F1", "Weighted_F1"]].isna().any().any():
        raise ValueError("Some Task+Model metrics are missing after aggregation; check source rows and name mapping.")

    return out


def plot_figure(perf: pd.DataFrame, out_dir: Path):
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["figure.facecolor"] = "white"

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), sharey=True)
    metrics = [("Accuracy", "(a) Accuracy"), ("Macro_F1", "(b) Macro-F1"), ("Weighted_F1", "(c) Weighted-F1")]
    colors = ["#4E79A7", "#F28E2B", "#59A14F"]
    x = np.arange(len(TASK_ORDER))
    w = 0.24

    for ax, (metric, subtitle) in zip(axes, metrics):
        for i, model in enumerate(MODEL_ORDER):
            vals = [perf[(perf["Task"] == t) & (perf["Model"] == model)][metric].iloc[0] for t in TASK_ORDER]
            bars = ax.bar(x + (i - 1) * w, vals, width=w, color=colors[i], edgecolor="black", linewidth=0.5)
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, min(1.03, v + 0.015), f"{v:.2f}", ha="center", va="bottom", fontsize=8)
        ax.set_title(subtitle, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(TASK_ORDER, fontsize=9)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Score")
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", linestyle="--", alpha=0.3)

    handles = [plt.Rectangle((0, 0), 1, 1, color=c, ec="black", lw=0.5) for c in colors]
    fig.legend(handles, MODEL_ORDER, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.03))
    plt.tight_layout(rect=[0, 0, 1, 0.92])
    png = out_dir / "Figure_9_model_performance_comparison.png"
    tif = out_dir / "Figure_9_model_performance_comparison.tif"
    pdf = out_dir / "Figure_9_model_performance_comparison.pdf"
    fig.savefig(png, dpi=600)
    fig.savefig(tif, dpi=600)
    fig.savefig(pdf, dpi=600)
    plt.close(fig)
    return [png, tif, pdf]


def write_summary_txt(out_txt: Path, s13_path: Path, perf: pd.DataFrame):
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"S13 path: {s13_path}\n")
        f.write("S13 is an expanded per-class table, not a macro avg summary table.\n")
        f.write("Metrics are recalculated by Task+Model from class-level rows using Recall, F1, and Support.\n\n")

        f.write("Task | Model | Accuracy | Macro-F1 | Weighted-F1\n")
        for _, r in perf.iterrows():
            f.write(f"{r['Task']} | {r['Model']} | {r['Accuracy']:.6f} | {r['Macro_F1']:.6f} | {r['Weighted_F1']:.6f}\n")

        f.write("\nBest Macro-F1 by task:\n")
        for t in TASK_ORDER:
            sub = perf[perf["Task"] == t]
            rr = sub.loc[sub["Macro_F1"].idxmax()]
            f.write(f"- {t}: {rr['Model']} ({rr['Macro_F1']:.4f})\n")

        f.write("\nBest Weighted-F1 by task:\n")
        for t in TASK_ORDER:
            sub = perf[perf["Task"] == t]
            rr = sub.loc[sub["Weighted_F1"].idxmax()]
            f.write(f"- {t}: {rr['Model']} ({rr['Weighted_F1']:.4f})\n")


def main():
    root = resolve_project_root()
    s13_path = root / "05_tables" / "S13_classification_reports_Z1_Z4.xlsx"
    out_dir = root / "07_figures_main"
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnosis_txt = out_dir / "Figure9_S13_workbook_diagnosis.txt"
    summary_xlsx = out_dir / "Figure9_model_performance_summary.xlsx"
    summary_txt = out_dir / "Figure9_model_performance_summary.txt"
    debug_xlsx = out_dir / "Figure9_parse_failed_debug.xlsx"

    if not s13_path.exists():
        raise FileNotFoundError(f"Input workbook not found: {s13_path}")

    xls = write_diagnosis(s13_path, diagnosis_txt, debug_xlsx)
    df = pd.read_excel(s13_path, sheet_name=xls.sheet_names[0])
    perf = compute_metrics_from_expanded_table(df)
    perf.to_excel(summary_xlsx, index=False)

    figure_paths = plot_figure(perf, out_dir)
    write_summary_txt(summary_txt, s13_path, perf)

    print(str(diagnosis_txt))
    print(str(debug_xlsx))
    print(str(summary_xlsx))
    print(str(summary_txt))
    for p in figure_paths:
        print(str(p))


if __name__ == "__main__":
    main()
