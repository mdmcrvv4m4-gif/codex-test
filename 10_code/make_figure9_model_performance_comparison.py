import os
import re
from pathlib import Path
from typing import List, Optional, Dict

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


TASK_ORDER = [
    "Task1_zone_classification",
    "Task2_damage_severity",
    "Task3_failure_mode_3class",
]
TASK_DISPLAY = {
    "Task1_zone_classification": "Task 1: Zone",
    "Task2_damage_severity": "Task 2: Severity",
    "Task3_failure_mode_3class": "Task 3: Failure mode",
}
MODELS = ["Logistic Regression", "SVM", "Random Forest"]


def resolve_project_root() -> Path:
    env_root = os.environ.get("BARREL_PROJECT_ROOT")
    if env_root:
        return Path(env_root)
    p = Path(__file__).resolve()
    if p.parent.name == "10_code":
        return p.parent.parent
    return p.parents[1]


def norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def map_task(x: str) -> Optional[str]:
    n = norm(x)
    if any(k in n for k in ["task1", "zoneclassification", "zone"]):
        return "Task1_zone_classification"
    if any(k in n for k in ["task2", "damageseverity", "severity"]):
        return "Task2_damage_severity"
    if any(k in n for k in ["task3", "failuremode", "failure"]):
        return "Task3_failure_mode_3class"
    return None


def map_model(x: str) -> Optional[str]:
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
    if x < 0:
        return np.nan
    return min(x, 1.0)


def pick_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cmap = {norm(c): c for c in df.columns}
    for c in candidates:
        nc = norm(c)
        if nc in cmap:
            return cmap[nc]
    for c in df.columns:
        n = norm(c)
        for cand in candidates:
            if norm(cand) in n:
                return c
    return None


def detect_task_model(sheet_name: str, df: pd.DataFrame) -> Dict[str, Optional[str]]:
    task = map_task(sheet_name)
    model = map_model(sheet_name)
    for c in df.columns:
        task = task or map_task(c)
        model = model or map_model(c)
    for _, row in df.head(20).iterrows():
        row_text = " | ".join([str(v) for v in row.values])
        task = task or map_task(row_text)
        model = model or map_model(row_text)
    return {"Task": task, "Model": model}


def parse_format_b_wide(df: pd.DataFrame) -> pd.DataFrame:
    task_col = pick_col(df, ["Task"])
    model_col = pick_col(df, ["Model"])
    acc_col = pick_col(df, ["Accuracy", "test accuracy"])
    macro_col = pick_col(df, ["Macro-F1", "Macro_F1", "macro_f1", "test Macro-F1", "Test_Macro_F1"])
    weighted_col = pick_col(df, ["Weighted-F1", "Weighted_F1", "weighted_f1", "test Weighted-F1", "Test_Weighted_F1"])
    if not task_col or not model_col:
        return pd.DataFrame()
    if not any([acc_col, macro_col, weighted_col]):
        return pd.DataFrame()

    out = pd.DataFrame()
    out["Task"] = df[task_col].map(lambda x: map_task(x) or str(x))
    out["Model"] = df[model_col].map(lambda x: map_model(x) or str(x))
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
    tmp["Task"] = tmp["Task"].map(lambda x: map_task(x) or str(x))
    tmp["Model"] = tmp["Model"].map(lambda x: map_model(x) or str(x))
    tmp["MetricNorm"] = tmp["Metric"].map(norm)
    tmp["Value"] = tmp["Value"].map(to_score)

    tmp["MetricKey"] = np.where(tmp["MetricNorm"].str.contains("accuracy"), "Accuracy", np.nan)
    tmp["MetricKey"] = np.where(tmp["MetricNorm"].str.contains("macro"), "Macro_F1", tmp["MetricKey"])
    tmp["MetricKey"] = np.where(tmp["MetricNorm"].str.contains("weighted"), "Weighted_F1", tmp["MetricKey"])
    tmp = tmp.dropna(subset=["MetricKey"])
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
        numeric_cols = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
        f1_col = numeric_cols[0] if numeric_cols else None
    if not f1_col:
        return pd.DataFrame()

    macro_row = d[d[row_col].str.contains(r"macro\s*avg", case=False, na=False)]
    weighted_row = d[d[row_col].str.contains(r"weighted\s*avg", case=False, na=False)]
    accuracy_row = d[d[row_col].str.fullmatch(r"\s*accuracy\s*", case=False, na=False)]
    if macro_row.empty and weighted_row.empty and accuracy_row.empty:
        return pd.DataFrame()

    acc = np.nan
    if not accuracy_row.empty:
        vals = [to_score(accuracy_row.iloc[0][c]) for c in d.columns[1:]]
        vals = [v for v in vals if not pd.isna(v)]
        if vals:
            acc = vals[0]

    macro = to_score(macro_row.iloc[0][f1_col]) if not macro_row.empty else np.nan
    weighted = to_score(weighted_row.iloc[0][f1_col]) if not weighted_row.empty else np.nan

    tm = detect_task_model(sheet_name, d)
    if not tm["Task"] or not tm["Model"]:
        return pd.DataFrame()
    return pd.DataFrame([{"Task": tm["Task"], "Model": tm["Model"], "Accuracy": acc, "Macro_F1": macro, "Weighted_F1": weighted}])


def parse_report_text(df: pd.DataFrame, sheet_name: str) -> pd.DataFrame:
    text = "\n".join(df.astype(str).fillna("").values.ravel().tolist())
    if not any(k in text.lower() for k in ["accuracy", "macro avg", "weighted avg"]):
        return pd.DataFrame()

    macro = np.nan
    weighted = np.nan
    acc = np.nan

    m_macro = re.search(r"macro\s+avg\s+[0-9.]+\s+[0-9.]+\s+([0-9.]+)", text, flags=re.I)
    if m_macro:
        macro = to_score(m_macro.group(1))
    m_weight = re.search(r"weighted\s+avg\s+[0-9.]+\s+[0-9.]+\s+([0-9.]+)", text, flags=re.I)
    if m_weight:
        weighted = to_score(m_weight.group(1))
    m_acc = re.search(r"accuracy\s+([0-9.]+)", text, flags=re.I)
    if m_acc:
        acc = to_score(m_acc.group(1))

    if pd.isna(acc) and pd.isna(macro) and pd.isna(weighted):
        return pd.DataFrame()

    tm = detect_task_model(sheet_name, df)
    if not tm["Task"] or not tm["Model"]:
        return pd.DataFrame()
    return pd.DataFrame([{"Task": tm["Task"], "Model": tm["Model"], "Accuracy": acc, "Macro_F1": macro, "Weighted_F1": weighted}])


def diagnose_workbook(xlsx: Path, out_txt: Path):
    xls = pd.ExcelFile(xlsx)
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(f"Workbook: {xlsx}\n")
        f.write("Sheets:\n")
        for s in xls.sheet_names:
            f.write(f"- {s}\n")
        f.write("\n")

        for s in xls.sheet_names:
            df = pd.read_excel(xlsx, sheet_name=s)
            f.write(f"=== Sheet: {s} ===\n")
            f.write(f"shape: {df.shape}\n")
            f.write(f"columns: {list(df.columns)}\n")
            f.write("head(15):\n")
            f.write(df.head(15).to_string(index=False))
            f.write("\n\n")
    return xls


def main():
    plt.rcParams["font.family"] = "DejaVu Sans"
    plt.rcParams["figure.facecolor"] = "white"

    root = resolve_project_root()
    in_xlsx = root / "05_tables" / "S13_classification_reports_Z1_Z4.xlsx"
    out_dir = root / "07_figures_main"
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnosis_txt = out_dir / "Figure9_S13_workbook_diagnosis.txt"
    if not in_xlsx.exists():
        raise FileNotFoundError(f"Input not found: {in_xlsx}")

    xls = diagnose_workbook(in_xlsx, diagnosis_txt)
    print(f"[INFO] Diagnosis saved: {diagnosis_txt}")

    parsed = []
    notes = []

    for s in xls.sheet_names:
        df = pd.read_excel(in_xlsx, sheet_name=s)
        for parser_name, parser in [
            ("format_b_wide", parse_format_b_wide),
            ("format_c_long", parse_format_c_long),
            ("report_table", lambda x: parse_report_table(x, s)),
            ("report_text", lambda x: parse_report_text(x, s)),
        ]:
            out = parser(df)
            if not out.empty:
                parsed.append(out)
                notes.append(f"{s}: parsed by {parser_name}")
                break
        else:
            notes.append(f"{s}: not parsed")

    if parsed:
        perf = pd.concat(parsed, ignore_index=True)
    else:
        perf = pd.DataFrame(columns=["Task", "Model", "Accuracy", "Macro_F1", "Weighted_F1"])

    if not perf.empty:
        perf["Task"] = perf["Task"].map(lambda x: map_task(x) or x)
        perf["Model"] = perf["Model"].map(lambda x: map_model(x) or x)
        perf = perf[perf["Task"].isin(TASK_ORDER) & perf["Model"].isin(MODELS)].copy()
        if not perf.empty:
            perf = perf.groupby(["Task", "Model"], as_index=False)[["Accuracy", "Macro_F1", "Weighted_F1"]].mean()

    full = pd.MultiIndex.from_product([TASK_ORDER, MODELS], names=["Task", "Model"]).to_frame(index=False)
    perf = full.merge(perf, on=["Task", "Model"], how="left")

    summary_xlsx = out_dir / "Figure9_model_performance_summary.xlsx"
    perf.to_excel(summary_xlsx, index=False)

    if perf[["Accuracy", "Macro_F1", "Weighted_F1"]].isna().all().all():
        debug_xlsx = out_dir / "Figure9_parse_failed_debug.xlsx"
        with pd.ExcelWriter(debug_xlsx, engine="openpyxl") as writer:
            for s in xls.sheet_names:
                pd.read_excel(in_xlsx, sheet_name=s).head(30).to_excel(writer, sheet_name=s[:31], index=False)
        print(f"[WARN] No metrics parsed. Debug saved: {debug_xlsx}")

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4), sharey=True)
    metrics = [("Accuracy", "(a) Accuracy"), ("Macro_F1", "(b) Macro-F1"), ("Weighted_F1", "(c) Weighted-F1")]
    x = np.arange(len(TASK_ORDER))
    w = 0.24
    colors = ["#4E79A7", "#F28E2B", "#59A14F"]

    for ax, (metric, title) in zip(axes, metrics):
        if perf[metric].notna().sum() == 0:
            ax.text(0.5, 0.5, f"{metric.replace('_', '-')} not available in S13", ha="center", va="center", transform=ax.transAxes)
            ax.set_title(title, fontsize=11)
            ax.set_xticks(x)
            ax.set_xticklabels([TASK_DISPLAY[t] for t in TASK_ORDER], fontsize=9)
            ax.set_ylim(0, 1.05)
            ax.set_ylabel("Score")
            continue

        for i, m in enumerate(MODELS):
            vals = [perf[(perf.Task == t) & (perf.Model == m)][metric].values[0] for t in TASK_ORDER]
            bars = ax.bar(x + (i - 1) * w, vals, width=w, label=m, color=colors[i], edgecolor="black", linewidth=0.5)
            for b, v in zip(bars, vals):
                if pd.isna(v):
                    continue
                ax.text(b.get_x() + b.get_width()/2, min(1.03, v + 0.015), f"{v:.2f}", ha="center", va="bottom", fontsize=8)

        ax.set_title(title, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels([TASK_DISPLAY[t] for t in TASK_ORDER], fontsize=9)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Score")
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

    txt = out_dir / "Figure9_model_performance_summary.txt"
    with open(txt, "w", encoding="utf-8") as f:
        f.write(f"Data source: {in_xlsx}\n")
        f.write("Detected sheets:\n")
        for s in xls.sheet_names:
            f.write(f"- {s}\n")
        f.write("\nParse notes:\n")
        for n in notes:
            f.write(f"- {n}\n")

        f.write("\nTask | Model | Accuracy | Macro_F1 | Weighted_F1\n")
        for _, r in perf.iterrows():
            f.write(f"{r['Task']} | {r['Model']} | {r['Accuracy']} | {r['Macro_F1']} | {r['Weighted_F1']}\n")

        f.write("\nBest Macro-F1 by task:\n")
        for t in TASK_ORDER:
            sub = perf[perf.Task == t]
            if sub["Macro_F1"].notna().any():
                rr = sub.loc[sub["Macro_F1"].idxmax()]
                f.write(f"- {t}: {rr['Model']} ({rr['Macro_F1']:.4f})\n")
            else:
                f.write(f"- {t}: N/A\n")

        f.write("\nBest Weighted-F1 by task:\n")
        for t in TASK_ORDER:
            sub = perf[perf.Task == t]
            if sub["Weighted_F1"].notna().any():
                rr = sub.loc[sub["Weighted_F1"].idxmax()]
                f.write(f"- {t}: {rr['Model']} ({rr['Weighted_F1']:.4f})\n")
            else:
                f.write(f"- {t}: N/A\n")

    print(f"[DONE] {diagnosis_txt}")
    print(f"[DONE] {summary_xlsx}")
    print(f"[DONE] {txt}")
    print(f"[DONE] {png}")
    print(f"[DONE] {tif}")
    print(f"[DONE] {pdf}")


if __name__ == "__main__":
    main()
