#!/usr/bin/env python3
import base64
import io
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

CONFIG = {
    "Z1": {
        "raw": "Z1_img01_p01.png",
        "mask": "Z1_img01_p01_mask.tif",
        "zoom_box": [260, 120, 430, 260],
        "description": "Slight damage",
    },
    "Z2": {
        "raw": "Z2_img01_p01.png",
        "mask": "Z2_img01_p01_mask.tif",
        "zoom_box": [220, 100, 420, 260],
        "description": "Directional wear",
    },
    "Z3": {
        "raw": "Z3_img01_p01.png",
        "mask": "Z3_img01_p01_mask.tif",
        "zoom_box": [180, 90, 380, 250],
        "description": "Crack–wear coexistence",
    },
    "Z4": {
        "raw": "Z4_img01_p01.png",
        "mask": "Z4_img01_p01_mask.tif",
        "zoom_box": [160, 80, 380, 260],
        "description": "Severe mixed damage",
    },
}

CLASS_COLORS = {
    1: (200, 200, 200),
    2: (220, 30, 30),
    3: (40, 90, 220),
    4: (245, 140, 30),
    5: (0, 0, 0),
}


def setup_paths() -> Dict[str, Path]:
    root = Path(__file__).resolve().parent.parent
    return {
        "root": root,
        "raw_dir": root / "04_patches_4x4",
        "mask_dir": root / "06B_semantic_segmentation",
        "output_dir": root / "07_figures_main",
        "png": root / "07_figures_main" / "Figure_3_semantic_segmentation_examples_Z1_Z4.png",
        "pdf": root / "07_figures_main" / "Figure_3_semantic_segmentation_examples_Z1_Z4.pdf",
        "svg": root / "07_figures_main" / "Figure_3_semantic_segmentation_examples_Z1_Z4.svg",
    }


def find_file_recursive(base_dir: Path, filename: str) -> Optional[Path]:
    if not filename:
        return None
    target = filename.lower()
    for p in base_dir.rglob("*"):
        if p.is_file() and p.name.lower() == target:
            return p
    return None


def find_first_available_file(base_dir: Path, zone: str, kind: str) -> Optional[Path]:
    zone_l = zone.lower()
    if kind == "raw":
        exts = [".png", ".tif", ".tiff", ".jpg", ".jpeg"]
        keywords = []
    else:
        exts = [".tif", ".tiff", ".png"]
        keywords = ["mask", "prediction", "segmentation", "simple segmentation"]

    candidates = []
    for p in base_dir.rglob("*"):
        if not p.is_file():
            continue
        name_l = p.name.lower()
        if zone_l not in name_l:
            continue
        if p.suffix.lower() not in exts:
            continue
        if keywords and not any(k in name_l for k in keywords):
            continue
        candidates.append(p)
    if candidates:
        return sorted(candidates)[0]

    if kind == "mask":
        fallback = []
        for p in base_dir.rglob("*"):
            if p.is_file() and zone_l in p.name.lower() and p.suffix.lower() in exts:
                fallback.append(p)
        if fallback:
            return sorted(fallback)[0]
    return None


def load_grayscale_image(path: Path) -> Image.Image:
    return Image.open(path).convert("L")


def load_mask_image(path: Path) -> Image.Image:
    return Image.open(path)


def normalize_mask_values(mask_img: Image.Image) -> Image.Image:
    gray = mask_img.convert("L")
    vals = list(gray.getdata())
    uniq = sorted(set(vals))
    if set(uniq).issubset({0, 1, 2, 3, 4, 5}):
        norm = [1 if v == 0 else v for v in vals]
    else:
        mapping = {}
        for i, u in enumerate([u for u in uniq if u >= 0][:5], start=1):
            mapping[u] = i
        norm = [mapping.get(v, 1) for v in vals]
        norm = [min(5, max(1, v)) for v in norm]
    out = Image.new("L", gray.size)
    out.putdata(norm)
    return out


def colorize_mask(mask_img: Image.Image) -> Image.Image:
    mask = mask_img.convert("L")
    vals = list(mask.getdata())
    rgb_vals = [CLASS_COLORS.get(v, CLASS_COLORS[1]) for v in vals]
    out = Image.new("RGB", mask.size)
    out.putdata(rgb_vals)
    return out


def create_overlay(raw_gray: Image.Image, color_mask: Image.Image, alpha: float = 0.40) -> Image.Image:
    raw_rgb = raw_gray.convert("RGB")
    return Image.blend(raw_rgb, color_mask.convert("RGB"), alpha=alpha)


def clamp_zoom_box(box: List[int], width: int, height: int) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = [int(v) for v in box]
    x1, x2 = sorted((x1, x2))
    y1, y2 = sorted((y1, y2))
    x1 = max(0, min(x1, width - 2))
    y1 = max(0, min(y1, height - 2))
    x2 = max(x1 + 1, min(x2, width - 1))
    y2 = max(y1 + 1, min(y2, height - 1))
    return x1, y1, x2, y2


def crop_and_resize_zoom(img: Image.Image, zoom_box: Tuple[int, int, int, int], panel_size: Tuple[int, int]) -> Image.Image:
    crop = img.crop(zoom_box)
    return fit_image_keep_ratio(crop, panel_size)


def fit_image_keep_ratio(img: Image.Image, panel_size: Tuple[int, int], background=(255, 255, 255)) -> Image.Image:
    pw, ph = panel_size
    mode = "RGB" if img.mode != "L" else "L"
    canvas = Image.new(mode, panel_size, color=background if mode == "RGB" else 255)
    scale = min(pw / img.width, ph / img.height)
    nw = max(1, int(img.width * scale))
    nh = max(1, int(img.height * scale))
    resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
    ox = (pw - nw) // 2
    oy = (ph - nh) // 2
    canvas.paste(resized, (ox, oy))
    return canvas


def draw_placeholder_panel(draw: ImageDraw.ImageDraw, rect: Tuple[int, int, int, int], text: str):
    x1, y1, x2, y2 = rect
    draw.rectangle(rect, fill=(230, 230, 230), outline=(0, 0, 0), width=1)
    draw.multiline_text((x1 + 10, y1 + 10), text, fill=(50, 50, 50), spacing=4)


def draw_panel_border(draw: ImageDraw.ImageDraw, rect: Tuple[int, int, int, int]):
    draw.rectangle(rect, outline=(0, 0, 0), width=1)


def draw_legend(draw: ImageDraw.ImageDraw, start_xy: Tuple[int, int]):
    x, y = start_xy
    labels = [
        ("background", CLASS_COLORS[1]),
        ("surface crack", CLASS_COLORS[2]),
        ("directional wear", CLASS_COLORS[3]),
        ("severe surface damage", CLASS_COLORS[4]),
        ("ignore", CLASS_COLORS[5]),
    ]
    sw, sh = 24, 14
    gap = 16
    cx = x
    for label, c in labels:
        draw.rectangle((cx, y, cx + sw, y + sh), fill=c, outline=(0, 0, 0), width=1)
        draw.text((cx + sw + 6, y - 2), label, fill=(0, 0, 0))
        cx += sw + 6 + int(len(label) * 7.0) + gap


def draw_figure_png(paths: Dict[str, Path]):
    panel_w, panel_h = 380, 260
    left_margin, right_margin = 140, 60
    top_margin, bottom_margin = 120, 180
    col_gap, row_gap = 30, 40
    fig_w = left_margin + 4 * panel_w + 3 * col_gap + right_margin
    fig_h = top_margin + 4 * panel_h + 3 * row_gap + bottom_margin

    canvas = Image.new("RGB", (fig_w, fig_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    missing: List[str] = []
    columns = ["Raw SEM", "Mask", "Overlay", "Magnified region"]
    rows = ["Z1", "Z2", "Z3", "Z4"]
    desc = {z: CONFIG[z].get("description", "") for z in rows}

    draw.text((left_margin, 26), "Figure 3. Semantic segmentation examples of barrel SEM patches", fill=(0, 0, 0))

    for c, col_name in enumerate(columns):
        x = left_margin + c * (panel_w + col_gap)
        draw.text((x + panel_w // 2 - int(len(col_name) * 3.2), 86), col_name, fill=(0, 0, 0))

    panel_letters = [f"({chr(ord('a') + i)})" for i in range(16)]
    letter_idx = 0

    for r, zone in enumerate(rows):
        y = top_margin + r * (panel_h + row_gap)
        draw.text((24, y + 8), zone, fill=(0, 0, 0))
        draw.text((24, y + 30), f"{zone}: {desc[zone]}", fill=(0, 0, 0))

        raw_cfg = CONFIG[zone].get("raw", "")
        mask_cfg = CONFIG[zone].get("mask", "")
        raw_p = find_file_recursive(paths["raw_dir"], raw_cfg) or find_first_available_file(paths["raw_dir"], zone, "raw")
        mask_p = find_file_recursive(paths["mask_dir"], mask_cfg) or find_first_available_file(paths["mask_dir"], zone, "mask")

        raw_img = None
        color_mask = None
        overlay = None
        zoom_img = None
        zoom_box = None

        if raw_p is None:
            missing.append(f"{zone} raw missing: {raw_cfg}")
        if mask_p is None:
            missing.append(f"{zone} mask missing: {mask_cfg}")

        if raw_p is not None:
            raw_img = load_grayscale_image(raw_p)
        if mask_p is not None:
            m = normalize_mask_values(load_mask_image(mask_p))
            color_mask = colorize_mask(m)

        if raw_img is not None and color_mask is not None:
            if color_mask.size != raw_img.size:
                color_mask = color_mask.resize(raw_img.size, Image.Resampling.NEAREST)
            overlay = create_overlay(raw_img, color_mask, alpha=0.40)
            zoom_box = clamp_zoom_box(CONFIG[zone].get("zoom_box", [0, 0, raw_img.width // 2, raw_img.height // 2]), raw_img.width, raw_img.height)
            zoom_img = crop_and_resize_zoom(overlay, zoom_box, (panel_w, panel_h))

        panels: List[Optional[Image.Image]] = [
            fit_image_keep_ratio(raw_img, (panel_w, panel_h)).convert("RGB") if raw_img else None,
            fit_image_keep_ratio(color_mask, (panel_w, panel_h)) if color_mask else None,
            fit_image_keep_ratio(overlay, (panel_w, panel_h)) if overlay else None,
            zoom_img,
        ]

        for c in range(4):
            x = left_margin + c * (panel_w + col_gap)
            rect = (x, y, x + panel_w, y + panel_h)
            if panels[c] is None:
                miss_name = raw_cfg if c == 0 else (mask_cfg if c == 1 else f"{zone} overlay/zoom")
                draw_placeholder_panel(draw, rect, f"image missing:\n{miss_name}")
            else:
                canvas.paste(panels[c], (x, y))
                draw_panel_border(draw, rect)
                if c == 2 and zoom_box and raw_img is not None:
                    scale = min(panel_w / raw_img.width, panel_h / raw_img.height)
                    ox = x + (panel_w - int(raw_img.width * scale)) // 2
                    oy = y + (panel_h - int(raw_img.height * scale)) // 2
                    zx1, zy1, zx2, zy2 = zoom_box
                    rz = (
                        ox + int(zx1 * scale),
                        oy + int(zy1 * scale),
                        ox + int(zx2 * scale),
                        oy + int(zy2 * scale),
                    )
                    draw.rectangle(rz, outline=(0, 0, 0), width=2)
            draw.text((x + 8, y + 8), panel_letters[letter_idx], fill=(0, 0, 0))
            letter_idx += 1

    draw_legend(draw, (left_margin, fig_h - 90))
    draw.text((left_margin, fig_h - 50), "Semantic labels were obtained from Ilastik pixel classification.", fill=(0, 0, 0))

    return canvas, missing


def pil_image_to_base64_data_uri(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{encoded}"


def save_png(img: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG", dpi=(600, 600))


def save_pdf(img: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, format="PDF", resolution=600.0)


def save_svg(path: Path, figure_img: Image.Image):
    path.parent.mkdir(parents=True, exist_ok=True)
    data_uri = pil_image_to_base64_data_uri(figure_img, "PNG")
    w, h = figure_img.size
    svg = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <rect x="0" y="0" width="{w}" height="{h}" fill="white"/>
  <image x="0" y="0" width="{w}" height="{h}" href="{data_uri}"/>
</svg>
'''
    path.write_text(svg, encoding="utf-8")


def main():
    paths = setup_paths()
    paths["output_dir"].mkdir(parents=True, exist_ok=True)

    fig, missing = draw_figure_png(paths)

    save_png(fig, paths["png"])
    save_pdf(fig, paths["pdf"])
    save_svg(paths["svg"], fig)

    print("Figure saved:")
    print(str(paths["png"]))
    print(str(paths["pdf"]))
    print(str(paths["svg"]))

    if missing:
        print("missing file list:")
        for m in missing:
            print(f"- {m}")


if __name__ == "__main__":
    main()
