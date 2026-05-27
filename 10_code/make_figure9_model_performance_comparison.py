import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


TASK_CANONICAL = {
    "task1zoneclassification": "Task1_zone_classification",
    "task2damageseverity": "Task2_damage_severity",
    "task3failuremode3class": "Task3_failure_mode_3class",
}
TASK_DISPLAY = {
    "Task1_zone_classification": "Task 1: Zone",
    "Task2_damage_severity": "Task 2: Severity",
    "Task3_failure_mode_3class": "Task 3: Failure mode",
}
MODEL_DISPLAY_ORDER = ["Logistic Regression", "SVM", "Random Forest"]
TASK_ORDER = [
    "Task1_zone_classification",
    "Task2_damage_severity",
    "Task3_failure_mode_3class",
]


def resolve_project_root() -> Path:
    env_root = os.environ.get("BARREL_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    script_path = Path(__file__).resolve()
    if script_path.parent.name == "10_code":
        return script_path.parent.parent
    return script_path.parents[1]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def map_task(raw: str) -> Optional[str]:
    n = norm(raw)
    for k, v in TASK_CANONICAL.items():
        if k in n:
            return v
    return None


def map_model(raw: str) -> Optional[str]:
    n = norm(raw)
    if any(k in n for k in ["logisticregression", "logistic", "lr"]):
        return "Logistic Regression"
    if any(k in n for k in ["svm", "supportvector", "supportvectormachine", "support"]):
        return "SVM"
    if any(k in n for k in ["randomforest", "randomf", "rf"]):
        return "Random Forest"
    return None


def find_col(df: pd.DataFrame, keys: List[str]) -> Optional[str]:
    cols = {norm(c): c for c in df.columns}
    for k in keys:
        nk = norm(k)
        if nk in cols:
            return cols[nk]
    for c in df.columns:
        cn = norm(c)
        if all(token in cn for token in norm(keys[0]).split()):
            return c
    return None


def to_score(x):
    if pd.isna(x):
        return np.nan
    try:
        v = float(str(x).replace("%", "").strip())
    except Exception:
        return np.nan
    if v > 1:
        v = v / 100.0
    return max(0.0, min(1.0, v))


def pick_report_subset(df: pd.DataFrame, note: List[str], context: str) -> pd.DataFrame:
    lower_cols = [norm(c) for c in df.columns]
    test_cols = [c for c in df.columns if "test" in norm(c)]
    train_cols = [c for c in df.columns if "train" in norm(c)]
    if test_cols:
        note.append(f"{context}: found test markers; prioritized rows/cols containing 'test'.")
        mask = pd.Series(False, index=df.index)
        for c in df.columns:
            if df[c].astype(str).str.contains("test", case=False, na=False).any():
                mask = mask | df[c].astype(str).str.contains("test", case=False, na=False)
        if mask.any():
            return df.loc[mask].copy()
    if train_cols and not test_cols:
        note.append(f"{context}: train marker found but no explicit test marker; used available report values.")
    return df


def parse_summary_sheet(df: pd.DataFrame, sheet_name: str, notes: List[str]) -> pd.DataFrame:
    c_task = find_col(df, ["Task"])
    c_model = find_col(df, ["Model"])
    c_acc = find_col(df, ["Accuracy"])
    c_macro = find_col(df, ["Macro F1", "Macro-F1", "macro avg f1-score"])
    c_weighted = find_col(df, ["Weighted F1", "Weighted-F1", "weighted avg f1-score"])
    if not all([c_task, c_model, c_acc, c_macro, c_weighted]):
        return pd.DataFrame()

    out = df[[c_task, c_model, c_acc, c_macro, c_weighted]].copy()
    out.columns = ["Task", "Model", "Accuracy", "Macro_F1", "Weighted_F1"]
    out["Task"] = out["Task"].map(lambda x: map_task(x) or x)
    out["Model"] = out["Model"].map(lambda x: map_model(x) or str(x))
    for c in ["Accuracy", "Macro_F1", "Weighted_F1"]:
        out[c] = out[c].map(to_score)
    notes.append(f"{sheet_name}: parsed as summary-format sheet.")
    return out


def parse_classification_report(df: pd.DataFrame, sheet_name: str, notes: List[str]) -> pd.DataFrame:
    d = pick_report_subset(df.copy(), notes, sheet_name)
    row_key_col = d.columns[0]
    d[row_key_col] = d[row_key_col].astype(str)

    f1_col = None
    acc_col = None
    for c in d.columns:
        nc = norm(c)
        if "f1score" in nc:
            f1_col = c
        if "accuracy" in nc:
            acc_col = c
    if f1_col is None:
        for c in d.columns:
            if pd.api.types.is_numeric_dtype(d[c]):
                f1_col = c
                break

    macro_row = d[d[row_key_col].str.contains("macro", case=False, na=False)]
    weighted_row = d[d[row_key_col].str.contains("weighted", case=False, na=False)]
    accuracy_row = d[d[row_key_col].str.fullmatch(r"\s*accuracy\s*", case=False, na=False)]

    if macro_row.empty or weighted_row.empty:
        return pd.DataFrame()

    macro = to_score(macro_row.iloc[0][f1_col])
    weighted = to_score(weighted_row.iloc[0][f1_col])

    acc = np.nan
    if not accuracy_row.empty:
        if acc_col:
            acc = to_score(accuracy_row.iloc[0][acc_col])
        else:
            for c in d.columns[1:]:
                val = to_score(accuracy_row.iloc[0][c])
                if not pd.isna(val):
                    acc = val
                    break

    task = map_task(sheet_name)
    model = map_model(sheet_name)
    for col in d.columns:
        task = task or map_task(col)
        model = model or map_model(col)
    for val in d[row_key_col].head(10).tolist():
        task = task or map_task(val)
        model = model or map_model(val)

    if not task or not model:
        return pd.DataFrame()

    notes.append(f"{sheet_name}: parsed as sklearn classification_report format.")
    return pd.DataFrame([
        {
            "Task": task,
            "Model": model,
            "Accuracy": acc,
            "Macro_F1": macro,
            "Weighted_F1": weighted,
        }
    ])


def main():
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["figure.facecolor"] = "white"

    root = resolve_project_root()
    in_xlsx = root / "05_tables" / "S13_classification_reports_Z1_Z4.xlsx"
    out_dir = root / "07_figures_main"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not in_xlsx.exists():
        raise FileNotFoundError(f"Input not found: {in_xlsx}")

    xls = pd.ExcelFile(in_xlsx)
    all_notes: List[str] = []
    parsed_frames: List[pd.DataFrame] = []

    for sheet in xls.sheet_names:
        sdf = pd.read_excel(in_xlsx, sheet_name=sheet)
        f_summary = parse_summary_sheet(sdf, sheet, all_notes)
        if not f_summary.empty:
            parsed_frames.append(f_summary)
            continue
        f_report = parse_classification_report(sdf, sheet, all_notes)
        if not f_report.empty:
            parsed_frames.append(f_report)
        else:
            all_notes.append(f"{sheet}: unable to parse, skipped.")

    if not parsed_frames:
        raise ValueError("No usable data parsed from workbook.")

    perf = pd.concat(parsed_frames, ignore_index=True)
    perf["Task"] = perf["Task"].map(lambda x: map_task(x) or x)
    perf["Model"] = perf["Model"].map(lambda x: map_model(x) or str(x))

    perf = perf[perf["Task"].isin(TASK_ORDER) & perf["Model"].isin(MODEL_DISPLAY_ORDER)].copy()
    perf = perf.groupby(["Task", "Model"], as_index=False).agg({"Accuracy": "mean", "Macro_F1": "mean", "Weighted_F1": "mean"})

    for t in TASK_ORDER:
        for m in MODEL_DISPLAY_ORDER:
            sub = perf[(perf["Task"] == t) & (perf["Model"] == m)]
            if sub.empty:
                print(f"[WARN] Missing task/model combination: {t} - {m}")

    full_idx = pd.MultiIndex.from_product([TASK_ORDER, MODEL_DISPLAY_ORDER], names=["Task", "Model"])
    perf = perf.set_index(["Task", "Model"]).reindex(full_idx).reset_index()

    summary_xlsx = out_dir / "Figure9_model_performance_summary.xlsx"
    perf.to_excel(summary_xlsx, index=False)

    tasks_disp = [TASK_DISPLAY[t] for t in TASK_ORDER]
    x = np.arange(len(TASK_ORDER))
    w = 0.24
    colors = ["#4E79A7", "#F28E2B", "#59A14F"]
    metrics = [("Accuracy", "(a) Accuracy"), ("Macro_F1", "(b) Macro-F1"), ("Weighted_F1", "(c) Weighted-F1")]

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4), sharey=True)
    legend_handles = None

    for ax, (metric, title) in zip(axes, metrics):
        for i, model in enumerate(MODEL_DISPLAY_ORDER):
            vals = [perf[(perf.Task == t) & (perf.Model == model)][metric].values[0] for t in TASK_ORDER]
            bars = ax.bar(x + (i - 1) * w, vals, width=w, label=model, color=colors[i], edgecolor="black", linewidth=0.5)
            for b, v in zip(bars, vals):
                if not pd.isna(v):
                    ax.text(b.get_x() + b.get_width()/2, min(1.03, v + 0.015), f"{v:.2f}", ha="center", va="bottom", fontsize=8)
            if legend_handles is None:
                legend_handles = bars
        ax.set_title(title, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(tasks_disp, fontsize=9)
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", linestyle="--", alpha=0.3)
        ax.set_ylabel("Score")

    fig.legend(legend_handles, MODEL_DISPLAY_ORDER, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.03))
    plt.tight_layout(rect=[0, 0, 1, 0.92])

    out_png = out_dir / "Figure_9_model_performance_comparison.png"
    out_tif = out_dir / "Figure_9_model_performance_comparison.tif"
    out_pdf = out_dir / "Figure_9_model_performance_comparison.pdf"
    fig.savefig(out_png, dpi=600)
    fig.savefig(out_tif, dpi=600)
    fig.savefig(out_pdf, dpi=600)
    plt.close(fig)

    txt_path = out_dir / "Figure9_model_performance_summary.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"Data source: {in_xlsx}\n")
        f.write("Detected sheets:\n")
        for s in xls.sheet_names:
            f.write(f"- {s}\n")
        f.write("\nParsing notes:\n")
        for n in all_notes:
            f.write(f"- {n}\n")

        f.write("\nPerformance table (Task, Model, Accuracy, Macro-F1, Weighted-F1):\n")
        for _, r in perf.iterrows():
            f.write(f"- {r['Task']} | {r['Model']} | {r['Accuracy']:.4f} | {r['Macro_F1']:.4f} | {r['Weighted_F1']:.4f}\n")

        f.write("\nBest model per task (Macro-F1):\n")
        for t in TASK_ORDER:
            sub = perf[perf["Task"] == t]
            row = sub.loc[sub["Macro_F1"].idxmax()] if sub["Macro_F1"].notna().any() else None
            if row is not None:
                f.write(f"- {t}: {row['Model']} ({row['Macro_F1']:.4f})\n")
            else:
                f.write(f"- {t}: N/A\n")

        f.write("\nBest model per task (Weighted-F1):\n")
        for t in TASK_ORDER:
            sub = perf[perf["Task"] == t]
            row = sub.loc[sub["Weighted_F1"].idxmax()] if sub["Weighted_F1"].notna().any() else None
            if row is not None:
                f.write(f"- {t}: {row['Model']} ({row['Weighted_F1']:.4f})\n")
            else:
                f.write(f"- {t}: N/A\n")

    print(f"[DONE] {out_png}")
    print(f"[DONE] {out_tif}")
    print(f"[DONE] {out_pdf}")
    print(f"[DONE] {summary_xlsx}")
    print(f"[DONE] {txt_path}")


if __name__ == "__main__":
    main()
