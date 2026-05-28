import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TASK_DISPLAY_ORDER = ["Task 1: Zone", "Task 2: Severity", "Task 3: Failure mode"]
MODELS = ["Logistic Regression", "SVM", "Random Forest"]


def resolve_project_root() -> Path:
    env_root = os.environ.get("BARREL_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    p = Path(__file__).resolve()
    return p.parent.parent if p.parent.name == "10_code" else p.parents[1]


def norm(x) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(x).strip().lower())


def standardize_task(x: str) -> Optional[str]:
    n = norm(x)
    if any(k in n for k in ["task1", "zoneclassification", "zone"]):
        return "Task 1: Zone"
    if any(k in n for k in ["task2", "damageseverity", "severity"]):
        return "Task 2: Severity"
    if any(k in n for k in ["task3", "failuremode", "failure"]):
        return "Task 3: Failure mode"
    return None


def standardize_model(x: str) -> Optional[str]:
    n = norm(x)
    if any(k in n for k in ["logisticregression", "logistic", "lr"]):
        return "Logistic Regression"
    if any(k in n for k in ["supportvector", "supportvectormachine", "support", "svm"]):
        return "SVM"
    if any(k in n for k in ["randomforest", "randomf", "random", "rf"]):
        return "Random Forest"
    return None


def to_score(v):
    if pd.isna(v):
        return np.nan
    s = str(v).strip()
    if not s:
        return np.nan
    m = re.search(r"[-+]?\d*\.?\d+", s.replace("%", ""))
    if not m:
        return np.nan
    x = float(m.group())
    if x > 1:
        x = x / 100.0
    return np.nan if x < 0 else min(x, 1.0)


def pick_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cmap = {norm(c): c for c in df.columns}
    for c in candidates:
        if norm(c) in cmap:
            return cmap[norm(c)]
    for c in df.columns:
        nc = norm(c)
        if any(norm(can) in nc for can in candidates):
            return c
    return None


def detect_task_model(sheet_name: str, df: pd.DataFrame) -> Dict[str, Optional[str]]:
    task = standardize_task(sheet_name)
    model = standardize_model(sheet_name)
    for c in df.columns:
        task = task or standardize_task(c)
        model = model or standardize_model(c)
    for _, row in df.head(30).iterrows():
        text = " | ".join(str(v) for v in row.values)
        task = task or standardize_task(text)
        model = model or standardize_model(text)
    return {"Task": task, "Model": model}


def parse_format_b_wide(df: pd.DataFrame) -> pd.DataFrame:
    task_col = pick_col(df, ["Task"])
    model_col = pick_col(df, ["Model"])
    acc_col = pick_col(df, ["Accuracy"])
    macro_col = pick_col(df, ["Macro-F1", "Macro_F1", "macro_f1"])
    weighted_col = pick_col(df, ["Weighted-F1", "Weighted_F1", "weighted_f1"])
    if not task_col or not model_col or not any([acc_col, macro_col, weighted_col]):
        return pd.DataFrame()
    out = pd.DataFrame()
    out["Task"] = df[task_col].map(lambda x: standardize_task(x) or str(x))
    out["Model"] = df[model_col].map(lambda x: standardize_model(x) or str(x))
    out["Accuracy"] = df[acc_col].map(to_score) if acc_col else np.nan
    out["Macro_F1"] = df[macro_col].map(to_score) if macro_col else np.nan
    out["Weighted_F1"] = df[weighted_col].map(to_score) if weighted_col else np.nan
    return out


def parse_format_c_long(df: pd.DataFrame) -> pd.DataFrame:
    task_col = pick_col(df, ["Task"])
    model_col = pick_col(df, ["Model"])
    metric_col = pick_col(df, ["Metric"])
    value_col = pick_col(df, ["Value"])
    if not all([task_col, model_col, metric_col, value_col]):
        return pd.DataFrame()
    tmp = df[[task_col, model_col, metric_col, value_col]].copy()
    tmp.columns = ["Task", "Model", "Metric", "Value"]
    tmp["Task"] = tmp["Task"].map(lambda x: standardize_task(x) or str(x))
    tmp["Model"] = tmp["Model"].map(lambda x: standardize_model(x) or str(x))
    mn = tmp["Metric"].map(norm)
    tmp["MetricKey"] = np.where(mn.str.contains("accuracy"), "Accuracy", np.nan)
    tmp["MetricKey"] = np.where(mn.str.contains("macro"), "Macro_F1", tmp["MetricKey"])
    tmp["MetricKey"] = np.where(mn.str.contains("weighted"), "Weighted_F1", tmp["MetricKey"])
    tmp = tmp.dropna(subset=["MetricKey"])
    tmp["Value"] = tmp["Value"].map(to_score)
    if tmp.empty:
        return pd.DataFrame()
    out = tmp.pivot_table(index=["Task", "Model"], columns="MetricKey", values="Value", aggfunc="mean").reset_index()
    for c in ["Accuracy", "Macro_F1", "Weighted_F1"]:
        if c not in out.columns:
            out[c] = np.nan
    return out[["Task", "Model", "Accuracy", "Macro_F1", "Weighted_F1"]]


def parse_report_table(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    d = df.copy()
    row_col = d.columns[0]
    d[row_col] = d[row_col].astype(str)
    f1_col = pick_col(d, ["f1-score", "f1 score", "f1"])
    if not f1_col:
        return pd.DataFrame()
    acc_row = d[d[row_col].str.fullmatch(r"\s*accuracy\s*", case=False, na=False)]
    macro_row = d[d[row_col].str.contains(r"macro\s*avg", case=False, na=False)]
    w_row = d[d[row_col].str.contains(r"weighted\s*avg", case=False, na=False)]
    if acc_row.empty and macro_row.empty and w_row.empty:
        return pd.DataFrame()
    acc = np.nan
    if not acc_row.empty:
        vals = [to_score(acc_row.iloc[0][c]) for c in d.columns[1:]]
        vals = [v for v in vals if not pd.isna(v)]
        if vals:
            acc = vals[0]
    macro = to_score(macro_row.iloc[0][f1_col]) if not macro_row.empty else np.nan
    weighted = to_score(w_row.iloc[0][f1_col]) if not w_row.empty else np.nan
    tm = detect_task_model(sheet_name, d)
    if not tm["Task"] or not tm["Model"]:
        return pd.DataFrame()
    return pd.DataFrame([{"Task": tm["Task"], "Model": tm["Model"], "Accuracy": acc, "Macro_F1": macro, "Weighted_F1": weighted}])


def diagnose_workbook(xlsx: Path, diag_txt: Path, debug_xlsx: Path):
    xls = pd.ExcelFile(xlsx)
    with open(diag_txt, "w", encoding="utf-8") as f, pd.ExcelWriter(debug_xlsx, engine="openpyxl") as writer:
        f.write(f"Workbook path: {xlsx}\n")
        f.write("Sheet names:\n")
        for s in xls.sheet_names:
            f.write(f"- {s}\n")
        f.write("\n")
        for s in xls.sheet_names:
            df = pd.read_excel(xlsx, sheet_name=s)
            f.write(f"=== Sheet: {s} ===\n")
            f.write(f"shape: {df.shape}\n")
            f.write("first 20 rows:\n")
            f.write(df.head(20).to_string(index=False))
            f.write("\n\n")
            df.head(30).to_excel(writer, sheet_name=s[:31], index=False)
    return xls


def main():
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["figure.facecolor"] = "white"

    root = resolve_project_root()
    in_xlsx = root / "05_tables" / "S13_classification_reports_Z1_Z4.xlsx"
    out_dir = root / "07_figures_main"
    out_dir.mkdir(parents=True, exist_ok=True)

    diag_txt = out_dir / "Figure9_S13_workbook_diagnosis.txt"
    debug_xlsx = out_dir / "Figure9_parse_failed_debug.xlsx"
    summary_xlsx = out_dir / "Figure9_model_performance_summary.xlsx"
    summary_txt = out_dir / "Figure9_model_performance_summary.txt"

    if not in_xlsx.exists():
        raise FileNotFoundError(f"Input not found: {in_xlsx}")

    xls = diagnose_workbook(in_xlsx, diag_txt, debug_xlsx)

    parsed, notes = [], []
    for s in xls.sheet_names:
        df = pd.read_excel(in_xlsx, sheet_name=s)
        parsers = [
            ("format_b_wide", lambda z: parse_format_b_wide(z)),
            ("format_c_long", lambda z: parse_format_c_long(z)),
            ("format_a_classification_report", lambda z: parse_report_table(z, s)),
        ]
        ok = False
        for name, fn in parsers:
            out = fn(df)
            if not out.empty:
                parsed.append(out)
                notes.append(f"{s}: parsed by {name}")
                ok = True
                break
        if not ok:
            notes.append(f"{s}: parse failed")

    perf = pd.concat(parsed, ignore_index=True) if parsed else pd.DataFrame(columns=["Task", "Model", "Accuracy", "Macro_F1", "Weighted_F1"])
    if not perf.empty:
        perf["Task"] = perf["Task"].map(lambda x: standardize_task(x) or x)
        perf["Model"] = perf["Model"].map(lambda x: standardize_model(x) or x)
        perf = perf[perf["Task"].isin(TASK_DISPLAY_ORDER) & perf["Model"].isin(MODELS)]
        perf = perf.groupby(["Task", "Model"], as_index=False)[["Accuracy", "Macro_F1", "Weighted_F1"]].mean()

    full = pd.MultiIndex.from_product([TASK_DISPLAY_ORDER, MODELS], names=["Task", "Model"]).to_frame(index=False)
    perf = full.merge(perf, on=["Task", "Model"], how="left")
    perf.to_excel(summary_xlsx, index=False)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4), sharey=True)
    metrics = [("Accuracy", "(a) Accuracy"), ("Macro_F1", "(b) Macro-F1"), ("Weighted_F1", "(c) Weighted-F1")]
    x = np.arange(len(TASK_DISPLAY_ORDER))
    w = 0.24
    colors = ["#4E79A7", "#F28E2B", "#59A14F"]
    for ax, (metric, ttl) in zip(axes, metrics):
        for i, m in enumerate(MODELS):
            vals = [perf[(perf.Task == t) & (perf.Model == m)][metric].values[0] for t in TASK_DISPLAY_ORDER]
            bars = ax.bar(x + (i - 1) * w, vals, width=w, color=colors[i], edgecolor="black", linewidth=0.5, label=m)
            for b, v in zip(bars, vals):
                if pd.isna(v):
                    ax.text(b.get_x() + b.get_width() / 2, 0.02, "NA", ha="center", va="bottom", fontsize=8)
                else:
                    ax.text(b.get_x() + b.get_width() / 2, min(1.03, v + 0.015), f"{v:.2f}", ha="center", va="bottom", fontsize=8)
        ax.set_title(ttl, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(TASK_DISPLAY_ORDER, fontsize=9)
        ax.set_ylabel("Score")
        ax.set_ylim(0, 1.05)
        ax.grid(axis="y", linestyle="--", alpha=0.3)

    handles = [plt.Rectangle((0, 0), 1, 1, color=c, ec="black", lw=0.5) for c in colors]
    fig.legend(handles, MODELS, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 1.03))
    plt.tight_layout(rect=[0, 0, 1, 0.92])
    png = out_dir / "Figure_9_model_performance_comparison.png"
    tif = out_dir / "Figure_9_model_performance_comparison.tif"
    pdf = out_dir / "Figure_9_model_performance_comparison.pdf"
    fig.savefig(png, dpi=600)
    fig.savefig(tif, dpi=600)
    fig.savefig(pdf, dpi=600)
    plt.close(fig)

    with open(summary_txt, "w", encoding="utf-8") as f:
        f.write(f"S13 path: {in_xlsx}\n")
        f.write("Recognized sheet names:\n")
        for s in xls.sheet_names:
            f.write(f"- {s}\n")
        f.write("\nParse notes:\n")
        for n in notes:
            f.write(f"- {n}\n")
        f.write("\nTask | Model | Accuracy | Macro-F1 | Weighted-F1\n")
        for _, r in perf.iterrows():
            f.write(f"{r['Task']} | {r['Model']} | {r['Accuracy']} | {r['Macro_F1']} | {r['Weighted_F1']}\n")
        for metric, label in [("Macro_F1", "Macro-F1"), ("Weighted_F1", "Weighted-F1")]:
            f.write(f"\nBest {label} by task:\n")
            for t in TASK_DISPLAY_ORDER:
                sub = perf[perf.Task == t]
                if sub[metric].notna().any():
                    rr = sub.loc[sub[metric].idxmax()]
                    f.write(f"- {t}: {rr['Model']} ({rr[metric]:.4f})\n")
                else:
                    f.write(f"- {t}: N/A (missing from S13)\n")

    print(str(diag_txt))
    print(str(debug_xlsx))
    print(str(summary_xlsx))
    print(str(summary_txt))
    print(str(png))
    print(str(tif))
    print(str(pdf))


if __name__ == "__main__":
    main()
