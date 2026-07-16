"""生成 Z1--Z4 语义损伤特征的小提琴图、箱线图和散点图。

默认路径对应 Windows 项目目录；如在其他电脑运行，可用 --data-dir 和
--output-dir 覆盖。脚本只读取源工作簿，绝不写入 ``05_tables``。
"""
from __future__ import annotations

import argparse
import math
import re
import shutil
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy.stats import kruskal

# ===== 可集中调整的绘图参数 =====
ZONE_ORDER = ["Z1", "Z2", "Z3", "Z4"]
COLORS = {"Z1": "#4E79A7", "Z2": "#4EAAA8", "Z3": "#F28E2B", "Z4": "#9C6ADE"}
FIGSIZE = (170 / 25.4, 108 / 25.4)  # mm -> inch
DPI = 600
VIOLIN_ALPHA, VIOLIN_WIDTH, KDE_BW = 0.30, 0.72, 0.32
JITTER, POINT_SIZE, POINT_ALPHA, RANDOM_SEED = 0.085, 9, 0.38, 2026
DEFAULT_DATA_DIR = Path(r"E:\Barrel_SEM_Z1_Z4_New\05_tables")
DEFAULT_OUTPUT_DIR = Path(r"E:\Barrel_SEM_Z1_Z4_New\06_figures\semantic_feature_violin")

FEATURES = [
    ("crack_area_fraction", "裂纹面积分数", ["crack_area_fraction", "crack fraction", "crack_area", "surface_crack_fraction"]),
    ("wear_area_fraction", "磨损面积分数", ["wear_area_fraction", "wear fraction", "directional_wear_fraction", "wear_area"]),
    ("severe_damage_area_fraction", "严重损伤面积分数", ["severe_damage_area_fraction", "severe_surface_damage_fraction", "severe_area_fraction", "severe_damage_fraction"]),
    ("crack_length_density", "裂纹长度密度", ["crack_length_density", "crack skeleton density", "crack_length"]),
    ("crack_network_density", "裂纹网络密度", ["crack_network_density", "crack junction density", "crack_junction_density", "network_density"]),
    ("wear_mark_density", "磨痕密度", ["wear_mark_density", "wear_line_density", "wear_trace_density", "wear_density"]),
]
ZONE_NAMES = {"zone", "region", "区域", "zoneid", "samplezone"}


def norm(value: object) -> str:
    """比较字段名时忽略大小写、空白、下划线和连字符。"""
    return re.sub(r"[\s_\-]+", "", str(value).strip().casefold())


def canonical_zone(value: object) -> str | None:
    """将 Z1、zone_1、1 等值规范为 Z1--Z4。"""
    if pd.isna(value):
        return None
    text = str(value).strip().casefold()
    match = re.fullmatch(r"(?:z|zone|region|区域)?\s*[_\- ]*([1-4])(?:\.0)?", text)
    return f"Z{match.group(1)}" if match else None


def score_column(column: object, aliases: list[str], series: pd.Series) -> tuple[float, int]:
    """按字段名相似度和可转换数值数量打分，避免任意挑选同名候选。"""
    name = norm(column)
    best = 0.0
    for alias in aliases:
        target = norm(alias)
        if name == target:
            best = max(best, 100.0)
        elif target in name or name in target:
            best = max(best, 70.0 + 20.0 * min(len(name), len(target)) / max(len(name), len(target)))
        else:
            tokens_a, tokens_b = set(re.findall(r"[a-z]+", name)), set(re.findall(r"[a-z]+", target))
            if tokens_a and tokens_b:
                best = max(best, 40.0 * len(tokens_a & tokens_b) / len(tokens_a | tokens_b))
    numeric_count = int(np.isfinite(pd.to_numeric(series, errors="coerce")).sum())
    return best, numeric_count


def choose_column(df: pd.DataFrame, aliases: list[str], label: str) -> tuple[object, str]:
    candidates = [(score_column(c, aliases, df[c]), c) for c in df.columns]
    candidates = [(score, count, c) for ((score, count), c) in candidates if score >= 65 and count > 0]
    if not candidates:
        raise ValueError(f"未找到“{label}”的可靠字段。")
    candidates.sort(key=lambda item: (-item[0], -item[1], str(item[2])))
    best_score, best_count, best = candidates[0]
    # 同等名称得分且有效数据量相同，无法客观区分，必须停止。
    tied = [c for score, count, c in candidates[1:] if abs(score - best_score) < 1e-9 and count == best_count]
    if tied:
        raise ValueError(f"“{label}”存在无法可靠判定的候选列：{best!r}、{tied!r}。")
    return best, f"选择 {best!r}（名称得分 {best_score:.1f}，有效数值 {best_count}）"


def choose_zone_column(df: pd.DataFrame) -> object:
    candidates = []
    for c in df.columns:
        if norm(c) in {norm(x) for x in ZONE_NAMES}:
            count = sum(canonical_zone(v) is not None for v in df[c])
            if count:
                candidates.append((count, c))
    if not candidates:
        raise ValueError("未找到区域列（支持 Zone、Region、区域、Zone_ID、Sample_Zone）。")
    candidates.sort(key=lambda x: (-x[0], str(x[1])))
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise ValueError(f"存在无法可靠判定的区域列：{[x[1] for x in candidates if x[0] == candidates[0][0]]}")
    return candidates[0][1]


def find_source(data_dir: Path) -> tuple[Path, str, pd.DataFrame, object, dict[str, object]]:
    if not data_dir.exists():
        raise FileNotFoundError(f"数据目录不存在：{data_dir}")
    preferred = ["S6_semantic_features_Z1_Z4.xlsx", "S7_feature_table_with_semantic_DSI_Z1_Z4.xlsx", "S10_ML_labeled_feature_table_Z1_Z4.xlsx"]
    all_files = list(data_dir.rglob("*.xlsx"))
    ordered = [next((p for p in all_files if p.name.casefold() == n.casefold()), None) for n in preferred]
    ordered += sorted([p for p in all_files if p not in ordered], key=lambda p: str(p).casefold())
    errors = []
    for path in (p for p in ordered if p is not None):
        try:
            for sheet in pd.ExcelFile(path, engine="openpyxl").sheet_names:
                df = pd.read_excel(path, sheet_name=sheet, engine="openpyxl")
                try:
                    zone = choose_zone_column(df)
                    columns = {key: choose_column(df, aliases, cn)[0] for key, cn, aliases in FEATURES}
                    return path, sheet, df, zone, columns
                except ValueError as exc:
                    errors.append(f"{path.name} / {sheet}: {exc}")
        except Exception as exc:  # 记录损坏或不可读工作簿，继续候选文件
            errors.append(f"{path.name}: 无法读取（{exc}）")
    detail = "\n  ".join(errors[-20:]) or "目录中未找到 .xlsx 文件"
    raise RuntimeError("没有工作表同时包含区域列和六类语义特征。检查记录：\n  " + detail)


def pick_font() -> str:
    available = {f.name for f in fm.fontManager.ttflist}
    for font in ["SimSun", "Microsoft YaHei", "SimHei", "Noto Serif CJK SC"]:
        if font in available:
            print(f"中文字体：{font}")
            return font
    raise RuntimeError("未找到可用中文字体（SimSun、Microsoft YaHei、SimHei、Noto Serif CJK SC）。")


def p_text(p: float) -> str:
    if p < 1e-300:
        return r"$p < 1\times10^{-300}$"
    if p < .001:
        exponent = int(math.floor(math.log10(p)))
        coefficient = p / 10 ** exponent
        return rf"$p = {coefficient:.3g}\times10^{{{exponent}}}$"
    return f"p = {p:.3g}"


def styled_axis(ax: plt.Axes, values: list[np.ndarray], feature_cn: str, letter: str, font_cn: str, p: float) -> None:
    positions = np.arange(1, 5)
    violin = ax.violinplot(values, positions=positions, widths=VIOLIN_WIDTH, showmeans=False, showmedians=False,
                           showextrema=False, bw_method=KDE_BW)
    for body, zone in zip(violin["bodies"], ZONE_ORDER):
        body.set_facecolor(COLORS[zone]); body.set_edgecolor(COLORS[zone]); body.set_alpha(VIOLIN_ALPHA); body.set_linewidth(.8)
    bp = ax.boxplot(values, positions=positions, widths=.17, patch_artist=True, showfliers=False, whis=1.5)
    for box in bp["boxes"]: box.set(facecolor="white", edgecolor="black", linewidth=.8)
    for key in ("whiskers", "caps"):
        for artist in bp[key]: artist.set(color="black", linewidth=.8)
    for artist in bp["medians"]: artist.set(color="black", linewidth=1.1)
    rng = np.random.default_rng(RANDOM_SEED + ord(letter))
    for pos, zone, data in zip(positions, ZONE_ORDER, values):
        ax.scatter(pos + rng.uniform(-JITTER, JITTER, len(data)), data, s=POINT_SIZE, color=COLORS[zone], alpha=POINT_ALPHA,
                   edgecolors="none", zorder=3)
    maximum = max(float(np.max(v)) for v in values)
    ax.set_ylim(bottom=0, top=maximum * 1.15 if maximum > 0 else 1)
    ax.text(.02, .97, f"Kruskal–Wallis：{p_text(p)}", transform=ax.transAxes, va="top", fontsize=8, fontname="Times New Roman")
    ax.set_title(f"({letter})", loc="left", fontsize=10, fontweight="bold", fontname="Times New Roman", pad=5)
    ax.set_xticks(positions, ZONE_ORDER, fontname="Times New Roman", fontsize=8.5)
    ax.set_xlabel("区域", fontname=font_cn, fontsize=9)
    ax.set_ylabel(feature_cn, fontname=font_cn, fontsize=9)
    ax.tick_params(direction="in", width=.8, labelsize=8.5)
    for label in ax.get_yticklabels(): label.set_fontname("Times New Roman")
    ax.grid(axis="y", color="#D9D9D9", linewidth=.45, alpha=.55); ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    for spine in ax.spines.values(): spine.set_linewidth(.8)


def main() -> None:
    parser = argparse.ArgumentParser(description="绘制语义特征小提琴－箱线－散点组合图")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    output = args.output_dir; output.mkdir(parents=True, exist_ok=True)
    mpl.rcParams.update({"svg.fonttype": "none", "pdf.fonttype": 42, "ps.fonttype": 42, "axes.unicode_minus": False,
                         "figure.facecolor": "white", "savefig.facecolor": "white"})
    print("开始递归检查 Excel 工作簿……")
    path, sheet, df, zone_col, columns = find_source(args.data_dir)
    df = df.copy(); df["_Zone"] = df[zone_col].map(canonical_zone)
    print(f"最终使用的 Excel 文件：{path}\n使用的工作表：{sheet}\n原始列名：{list(df.columns[:-1])}")
    print(f"区域字段：{zone_col!r}")
    for key, cn, _ in FEATURES: print(f"{cn} -> {columns[key]!r}；{choose_column(df, next(a for k, _, a in FEATURES if k == key), cn)[1]}")
    zone_counts = df["_Zone"].value_counts(); print("各区域原始识别样本量：", {z: int(zone_counts.get(z, 0)) for z in ZONE_ORDER})
    if any(zone_counts.get(z, 0) == 0 for z in ZONE_ORDER): raise RuntimeError("未同时识别出 Z1、Z2、Z3、Z4，停止绘图。")
    font_cn = pick_font(); mpl.rcParams["font.family"] = [font_cn, "Times New Roman"]
    long_rows, summary_rows, result_rows, panel_data = [], [], [], []
    for key, cn, _ in FEATURES:
        numeric = pd.to_numeric(df[columns[key]], errors="coerce").replace([np.inf, -np.inf], np.nan)
        print(f"{cn}：缺失/无穷值 {int(numeric.isna().sum())}；范围及分位数：{numeric.quantile([0,.25,.5,.75,1]).to_dict()}")
        groups = []
        for zone in ZONE_ORDER:
            vals = numeric[df["_Zone"] == zone].dropna().to_numpy(dtype=float)
            if len(vals) < 2 or np.all(vals == vals[0]): raise RuntimeError(f"{cn} 的 {zone} 有效数据不足或全部为常数，停止绘图。")
            groups.append(vals)
            q1, median, q3 = np.percentile(vals, [25, 50, 75])
            summary_rows.append({"特征中文名": cn, "实际数据列名": columns[key], "Zone": zone, "样本量": len(vals), "均值": vals.mean(), "标准差": vals.std(ddof=1), "最小值": vals.min(), "第25百分位数": q1, "中位数": median, "第75百分位数": q3, "最大值": vals.max(), "四分位距": q3-q1})
            long_rows += [{"Zone": zone, "Feature": key, "Feature_CN": cn, "Value": v, "Source_File": str(path), "Source_Sheet": sheet} for v in vals]
        h, p = kruskal(*groups)
        result_rows.append({"特征中文名": cn, "实际数据列名": columns[key], **{f"{z}样本量": len(v) for z, v in zip(ZONE_ORDER, groups)}, "Kruskal–Wallis H值": h, "p值": p, "显著性说明": "p < 0.05" if p < .05 else "p ≥ 0.05"})
        panel_data.append((key, cn, groups, p))
    fig, axes = plt.subplots(2, 3, figsize=FIGSIZE, constrained_layout=True, dpi=DPI)
    for ax, (letter, (_, cn, groups, p)) in zip(axes.flat, zip("abcdef", panel_data)): styled_axis(ax, groups, cn, letter, font_cn, p)
    base = output / "semantic_features_violin_box_scatter"
    for suffix in ["svg", "pdf", "eps", "png"]: fig.savefig(base.with_suffix("." + suffix), dpi=DPI, bbox_inches="tight", pad_inches=.04)
    fig.savefig(base.with_suffix(".tiff"), dpi=DPI, bbox_inches="tight", pad_inches=.04, pil_kwargs={"compression": "tiff_lzw"})
    # 单图使用同一绘图函数，确保可编辑 SVG 与组合图样式一致。
    for letter, (key, cn, groups, p) in zip("abcdef", panel_data):
        panel_fig, panel_ax = plt.subplots(figsize=(170/25.4/3, 108/25.4/2), constrained_layout=True, dpi=DPI)
        styled_axis(panel_ax, groups, cn, letter, font_cn, p)
        panel_fig.savefig(output / f"panel_{letter}_{key}.svg", bbox_inches="tight", pad_inches=.04); plt.close(panel_fig)
    plt.close(fig)
    pd.DataFrame(result_rows).to_excel(output / "semantic_feature_kruskal_results.xlsx", index=False)
    pd.DataFrame(summary_rows).to_excel(output / "semantic_feature_summary.xlsx", index=False)
    pd.DataFrame(long_rows).to_excel(output / "semantic_features_long_format.xlsx", index=False)
    (output / "figure_caption_zh_en.txt").write_text("""中文图题：\n图3 不同取样区域语义损伤特征的分布\n\n中文图注：\n图3 不同取样区域语义损伤特征的分布。（a）裂纹面积分数；（b）磨损面积分数；（c）严重损伤面积分数；（d）裂纹长度密度；（e）裂纹网络密度；（f）磨痕密度。小提琴轮廓表示数据的核密度分布，箱体表示四分位距，箱内横线表示中位数，散点表示单个SEM图像块的特征值。\n\n英文图题：\nFig. 3 Distributions of semantic damage features in different sampling zones\n\n英文图注：\nFig. 3 Distributions of semantic damage features in different sampling zones: (a) crack area fraction, (b) wear area fraction, (c) severe damage area fraction, (d) crack length density, (e) crack network density, and (f) wear mark density. The violin profiles represent kernel-density distributions, the boxes represent interquartile ranges, the horizontal lines indicate medians, and the points denote individual SEM patches.\n""", encoding="utf-8")
    shutil.copy2(Path(__file__), output / Path(__file__).name)
    generated = sorted(p for p in output.iterdir() if p.is_file())
    if any(p.stat().st_size == 0 for p in generated): raise RuntimeError("最终检查失败：发现空输出文件。")
    required = [base.with_suffix("." + ext) for ext in ("svg", "pdf", "eps", "png", "tiff")]
    required += [output / f"panel_{letter}_{key}.svg" for letter, (key, *_rest) in zip("abcdef", panel_data)]
    if any(not item.exists() for item in required): raise RuntimeError("最终检查失败：缺少要求的图形文件。")
    for raster in (base.with_suffix(".png"), base.with_suffix(".tiff")):
        with Image.open(raster) as image:
            dpi = image.info.get("dpi", (0, 0))
            if any(abs(value - DPI) > 2 for value in dpi):
                raise RuntimeError(f"最终检查失败：{raster.name} 的 DPI 不是 {DPI}。")
    svg_text = base.with_suffix(".svg").read_text(encoding="utf-8")
    if "裂纹面积分数" not in svg_text or "区域" not in svg_text:
        raise RuntimeError("最终检查失败：SVG 中未检测到可编辑中文文字，可能发生中文乱码。")
    print("最终检查通过：已识别 Z1--Z4、六个特征、实际计算的 p 值、统一配色和全部要求的非空输出；PNG/TIFF 为 600 dpi。")
    print("\n完成报告："); print(f"数据文件和工作表：{path} / {sheet}")
    print(pd.DataFrame(result_rows).to_string(index=False)); print("所有输出文件：\n" + "\n".join(str(p.resolve()) for p in generated))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        sys.exit(1)
