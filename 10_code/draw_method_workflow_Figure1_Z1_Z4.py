#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import base64
import io
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


CANVAS_W, CANVAS_H = 2400, 1350


def setup_paths() -> Dict[str, Path]:
    """Prepare project-relative paths for I/O."""
    script_path = Path(__file__).resolve()
    project_root = script_path.parents[1]

    paths = {
        "root": project_root,
        "macro_dir": project_root / "01_raw_macro_photos",
        "sem_raw_dir": project_root / "02_raw_SEM_images",
        "sem_std_dir": project_root / "03_standardized_SEM_2048x1536",
        "overlay_dir": project_root / "06B_semantic_segmentation" / "overlay",
        "fig_dir": project_root / "07_figures_main",
        "out_png": project_root / "07_figures_main" / "Figure_1_method_workflow_Z1_Z4.png",
        "out_pdf": project_root / "07_figures_main" / "Figure_1_method_workflow_Z1_Z4.pdf",
        "out_svg": project_root / "07_figures_main" / "Figure_1_method_workflow_Z1_Z4.svg",
    }
    paths["fig_dir"].mkdir(parents=True, exist_ok=True)
    return paths


def load_image_any(path: Optional[Path]) -> Optional[Image.Image]:
    """Load image safely with PIL and convert to RGB."""
    if not path or not path.exists():
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def find_file_recursive(root: Path, filename: str) -> Optional[Path]:
    """Find an exact filename recursively in root."""
    if not root.exists():
        return None
    for p in root.rglob(filename):
        if p.is_file():
            return p
    return None


def fit_image_keep_ratio(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize image to fit inside target while preserving aspect ratio."""
    src_w, src_h = img.size
    scale = min(target_w / src_w, target_h / src_h)
    new_size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def center_crop_keep_ratio(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Crop center after scaling to cover target area."""
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = img.resize((max(1, int(src_w * scale)), max(1, int(src_h * scale))), Image.Resampling.LANCZOS)
    rw, rh = resized.size
    left = (rw - target_w) // 2
    top = (rh - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def enhance_sem_grayscale(img: Image.Image) -> Image.Image:
    """Enhance SEM-like grayscale visual quality."""
    g = img.convert("L")
    g = ImageEnhance.Contrast(g).enhance(1.3)
    g = ImageEnhance.Sharpness(g).enhance(1.2)
    return g.convert("RGB")


def draw_rounded_box(draw: ImageDraw.ImageDraw, box: Tuple[int, int, int, int], radius: int, fill: str, outline: str, width: int = 2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_arrow(draw: ImageDraw.ImageDraw, start: Tuple[int, int], end: Tuple[int, int], color: str = "#333333", width: int = 3):
    draw.line([start, end], fill=color, width=width)
    ex, ey = end
    sx, sy = start
    dx, dy = ex - sx, ey - sy
    norm = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / norm, dy / norm
    px, py = -uy, ux
    size = 12
    p1 = (ex - ux * size + px * size * 0.5, ey - uy * size + py * size * 0.5)
    p2 = (ex - ux * size - px * size * 0.5, ey - uy * size - py * size * 0.5)
    draw.polygon([end, p1, p2], fill=color)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    words = text.split()
    lines, current = [], ""
    for w in words:
        candidate = (current + " " + w).strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def draw_thumbnail_or_placeholder(base: Image.Image, box: Tuple[int, int, int, int], img: Optional[Image.Image], text: str, border="#999999"):
    d = ImageDraw.Draw(base)
    x1, y1, x2, y2 = box
    d.rectangle(box, outline=border, width=1, fill="#ffffff")
    if img is not None:
        thumb = center_crop_keep_ratio(img, x2 - x1 - 4, y2 - y1 - 4)
        base.paste(thumb, (x1 + 2, y1 + 2))
    else:
        font = ImageFont.load_default()
        lines = text.split("\n")
        y = y1 + (y2 - y1) // 2 - 8 * len(lines)
        for line in lines:
            tw = d.textlength(line, font=font)
            d.text((x1 + (x2 - x1 - tw) / 2, y), line, font=font, fill="#666666")
            y += 16


def draw_step_module(base: Image.Image, step_no: str, title: str, bullets: List[str], box: Tuple[int, int, int, int], fill: str,
                     thumb: Optional[Image.Image] = None):
    d = ImageDraw.Draw(base)
    title_font = ImageFont.load_default()
    txt_font = ImageFont.load_default()
    num_font = ImageFont.load_default()

    draw_rounded_box(d, box, radius=18, fill=fill, outline="#7f8c8d", width=2)
    x1, y1, x2, y2 = box

    nb = (x1 + 10, y1 - 28, x1 + 55, y1 - 5)
    draw_rounded_box(d, nb, radius=8, fill="#ffffff", outline="#606060", width=1)
    d.text((nb[0] + 12, nb[1] + 6), step_no, font=num_font, fill="#202020")

    d.text((x1 + 12, y1 + 10), title, font=title_font, fill="#111111")

    thumb_box = (x1 + 12, y1 + 32, x1 + 12 + 170, y1 + 32 + 110)
    draw_thumbnail_or_placeholder(base, thumb_box, thumb, "image missing")

    ty = y1 + 34
    tx = thumb_box[2] + 12
    max_w = x2 - tx - 12
    for b in bullets:
        lines = wrap_text(d, f"• {b}", txt_font, max_w)
        for li in lines:
            d.text((tx, ty), li, font=txt_font, fill="#1f1f1f")
            ty += 16
        ty += 2


def draw_workflow_png(paths: Dict[str, Path]) -> Tuple[Image.Image, List[Path], Dict]:
    missing: List[Path] = []
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    d = ImageDraw.Draw(img)
    title_font = ImageFont.load_default()
    d.text((40, 20), "Workflow for semantic SEM-based damage assessment of barrel zones Z1–Z4", fill="#111111", font=title_font)

    macro = load_image_any(paths["macro_dir"] / "macro_overall_Z1_Z4.png")
    if macro is None:
        missing.append(paths["macro_dir"] / "macro_overall_Z1_Z4.png")

    overlays = list(paths["overlay_dir"].glob("*_semantic_overlay.png")) if paths["overlay_dir"].exists() else []
    overlay = load_image_any(overlays[0]) if overlays else None
    if overlay is None:
        missing.append(paths["overlay_dir"] / "*_semantic_overlay.png")

    dsi_fig = load_image_any(paths["fig_dir"] / "Figure_6a_semantic_DSI_Z1_Z4.png")
    if dsi_fig is None:
        missing.append(paths["fig_dir"] / "Figure_6a_semantic_DSI_Z1_Z4.png")

    ml_fig = load_image_any(paths["fig_dir"] / "Figure_10_CM_Task3_3class_Z1_Z4.png") or load_image_any(paths["fig_dir"] / "Figure_11_RF_importance_Task3_Z1_Z4.png")
    if ml_fig is None:
        missing.append(paths["fig_dir"] / "Figure_10_CM_Task3_3class_Z1_Z4.png")
        missing.append(paths["fig_dir"] / "Figure_11_RF_importance_Task3_Z1_Z4.png")

    y = 160
    w, h, gap = 330, 380, 18
    xs = [30 + i * (w + gap) for i in range(6)]
    colors = ["#edf3fb", "#eef5ef", "#f8f0e8", "#f3eefb", "#eef7f7", "#f8f4ec"]
    steps = [
        ("01", "Step 1. Zone + SEM acquisition", ["Z1–Z4 barrel zones", "Macro region definition", "10 SEM images / zone", "Raw size: 2048 × 1536"], macro),
        ("02", "Step 2. Standardize + patches", ["Standardized to 2048 × 1536", "4 × 4 patches / image", "Patch: 512 × 384", "Total patches: 640"], None),
        ("03", "Step 3. Semantic classification", ["Ilastik pixel classification", "5 labels: background, crack, wear, severe, ignore", "Output: masks + overlays"], overlay),
        ("04", "Step 4. Feature extraction", ["Semantic: crack/wear/severe metrics", "Texture: entropy, contrast, homogeneity, std"], None),
        ("05", "Step 5. Semantic DSI", ["DSI = 0.30F_severe + 0.25F_crack", "+ 0.20F_entropy + 0.15F_wear + 0.10F_std", "Sensitivity: equal/crack/wear", "Output: zone-wise DSI ranking"], dsi_fig),
        ("06", "Step 6. ML interpretation", ["Input: semantic + texture", "Models: LR / SVM / RF", "**Image_ID-based 4-fold CV**", "Task 3: failure-mode ID"], ml_fig),
    ]

    for i, (no, tt, bl, thumb) in enumerate(steps):
        box = (xs[i], y, xs[i] + w, y + h)
        thumb_use = enhance_sem_grayscale(thumb) if thumb and i in (0, 2) else thumb
        draw_step_module(img, no, tt, bl, box, colors[i], thumb_use)
        if i < 5:
            draw_arrow(d, (xs[i] + w + 5, y + h // 2), (xs[i + 1] - 5, y + h // 2), color="#2f2f2f")

    out_box = (1980, 620, 2360, 1060)
    draw_rounded_box(d, out_box, 18, "#f4f8ff", "#6c7a89", 2)
    d.text((out_box[0] + 12, out_box[1] + 12), "Interpretable outputs", fill="#0f1f2f", font=ImageFont.load_default())
    out_lines = [
        "1. Zone-wise damage severity trend",
        "2. Semantic DSI for Z1–Z4",
        "3. Failure-mode identification",
        "4. Feature-importance interpretation",
        "Semantic features are more effective for",
        "failure-mode identification than",
        "direct zone classification.",
    ]
    oy = out_box[1] + 42
    for line in out_lines:
        d.text((out_box[0] + 12, oy), line, fill="#1a1a1a", font=ImageFont.load_default())
        oy += 18

    draw_arrow(d, (xs[-1] + w + 5, y + h // 2), (out_box[0] - 8, y + h // 2), color="#2f2f2f")

    d.text((40, CANVAS_H - 40), "DSI = Damage Severity Index; SEM = scanning electron microscopy.", fill="#555555", font=ImageFont.load_default())

    spec = {"steps": [{"box": (xs[i], y, xs[i]+w, y+h), "step": s[0], "title": s[1], "bullets": s[2]} for i, s in enumerate(steps)], "out_box": out_box}
    return img, missing, spec


def pil_image_to_base64_data_uri(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/{fmt.lower()};base64,{data}"


def save_png(img: Image.Image, out_path: Path):
    img.save(out_path, format="PNG", dpi=(600, 600))


def save_pdf(img: Image.Image, out_path: Path):
    img.convert("RGB").save(out_path, format="PDF", resolution=600.0)


def save_svg(paths: Dict[str, Path], spec: Dict):
    out = paths["out_svg"]
    # simple editable SVG with text/rect/line/path and optional raster embeds
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">']
    svg.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    svg.append('<text x="40" y="40" font-family="Arial, Calibri, DejaVu Sans" font-size="22">Workflow for semantic SEM-based damage assessment of barrel zones Z1–Z4</text>')

    for st in spec["steps"]:
        x1, y1, x2, y2 = st["box"]
        svg.append(f'<rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" rx="18" ry="18" fill="#eef3f8" stroke="#7f8c8d" stroke-width="2"/>')
        svg.append(f'<rect x="{x1+10}" y="{y1-28}" width="45" height="23" rx="8" ry="8" fill="white" stroke="#606060"/>')
        svg.append(f'<text x="{x1+22}" y="{y1-12}" font-size="12" font-family="Arial, Calibri, DejaVu Sans">{st["step"]}</text>')
        svg.append(f'<text x="{x1+12}" y="{y1+24}" font-size="13" font-family="Arial, Calibri, DejaVu Sans">{st["title"]}</text>')
        ty = y1 + 54
        for b in st["bullets"][:6]:
            esc = b.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            svg.append(f'<text x="{x1+188}" y="{ty}" font-size="12" font-family="Arial, Calibri, DejaVu Sans">• {esc}</text>')
            ty += 16

    # arrows
    for i in range(5):
        x1 = spec["steps"][i]["box"][2] + 5
        x2 = spec["steps"][i+1]["box"][0] - 5
        y = (spec["steps"][i]["box"][1] + spec["steps"][i]["box"][3]) // 2
        svg.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#2f2f2f" stroke-width="3"/>')
        svg.append(f'<path d="M {x2} {y} L {x2-10} {y-5} L {x2-10} {y+5} Z" fill="#2f2f2f"/>')

    ox1, oy1, ox2, oy2 = spec["out_box"]
    svg.append(f'<rect x="{ox1}" y="{oy1}" width="{ox2-ox1}" height="{oy2-oy1}" rx="18" ry="18" fill="#f4f8ff" stroke="#6c7a89" stroke-width="2"/>')
    svg.append(f'<text x="{ox1+12}" y="{oy1+30}" font-size="16" font-family="Arial, Calibri, DejaVu Sans">Interpretable outputs</text>')
    lines = ["1. Zone-wise damage severity trend", "2. Semantic DSI for Z1–Z4", "3. Failure-mode identification", "4. Feature-importance interpretation", "Semantic features are more effective for assisting failure-mode", "identification than direct zone classification."]
    yy = oy1 + 56
    for li in lines:
        esc = li.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        svg.append(f'<text x="{ox1+12}" y="{yy}" font-size="12" font-family="Arial, Calibri, DejaVu Sans">{esc}</text>')
        yy += 18

    svg.append('<text x="40" y="1310" font-size="14" fill="#555" font-family="Arial, Calibri, DejaVu Sans">DSI = Damage Severity Index; SEM = scanning electron microscopy.</text>')
    svg.append('</svg>')
    out.write_text("\n".join(svg), encoding="utf-8")


def main():
    paths = setup_paths()
    img, missing, spec = draw_workflow_png(paths)
    save_png(img, paths["out_png"])
    save_pdf(img, paths["out_pdf"])
    save_svg(paths, spec)

    print("Figure saved:")
    print(str(paths["out_png"]))
    print(str(paths["out_pdf"]))
    print(str(paths["out_svg"]))
    if missing:
        print("Missing file list:")
        for p in missing:
            print(str(p))


if __name__ == "__main__":
    main()
