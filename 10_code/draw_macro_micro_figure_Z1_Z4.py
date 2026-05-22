#!/usr/bin/env python3
"""Draw macro-to-micro correspondence figure for barrel zones Z1-Z4.

Outputs:
- PNG (600 dpi)
- PDF (submission-ready)
- SVG (editable vector + embedded raster images)
"""

from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont


# ------------------------------- 1) Path setup -------------------------------
def setup_paths() -> Dict[str, Path]:
    root = Path(__file__).resolve().parents[1]
    paths = {
        "root": root,
        "macro_dir": root / "01_raw_macro_photos",
        "sem_root_1": root / "02_raw_SEM_images",
        "sem_root_2": root / "03_standardized_SEM_2048x1536",
        "out_dir": root / "07_figures_main",
        "out_png": root / "07_figures_main" / "Figure_2_macro_micro_correspondence_Z1_Z4.png",
        "out_pdf": root / "07_figures_main" / "Figure_2_macro_micro_correspondence_Z1_Z4.pdf",
        "out_svg": root / "07_figures_main" / "Figure_2_macro_micro_correspondence_Z1_Z4.svg",
    }
    paths["out_dir"].mkdir(parents=True, exist_ok=True)
    return paths


# ------------------- 2) Image loading (png/jpg/tif/tiff) -------------------
def load_image_any(path: Path) -> Optional[Image.Image]:
    if not path.exists():
        return None
    try:
        with Image.open(path) as img:
            return img.convert("RGB")
    except Exception:
        arr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if arr is None:
            return None
        arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(arr)


# ---------------------- 3) Recursive search for SEM file ---------------------
def find_file_recursive(roots: Sequence[Path], filename: str) -> Optional[Path]:
    filename_lower = filename.lower()
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.name.lower() == filename_lower:
                return p
    return None


# ---------------------- 4) Aspect-ratio fit into a box ----------------------
def fit_image_keep_ratio(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
    img = image.copy()
    img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), "white")
    x = (target_w - img.width) // 2
    y = (target_h - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas


# -------------------------- 5) Center crop function --------------------------
def center_crop_keep_ratio(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = image.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        box = (left, 0, left + new_w, src_h)
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        box = (0, top, src_w, top + new_h)

    cropped = image.crop(box)
    return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)


# ---------------------- 6) SEM grayscale enhancement ------------------------
def enhance_sem_grayscale(image: Image.Image) -> Image.Image:
    arr = np.array(image.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    gray_eq = clahe.apply(gray)
    gray_eq = cv2.normalize(gray_eq, None, 0, 255, cv2.NORM_MINMAX)
    return Image.fromarray(gray_eq, mode="L").convert("RGB")


# -------------------------- 7) Draw SEM scale bar ---------------------------
def draw_scale_bar(img: Image.Image, text: str = "20 μm") -> Image.Image:
    d = ImageDraw.Draw(img)
    w, h = img.size
    bar_w = max(70, int(w * 0.28))
    bar_h = max(20, int(h * 0.12))
    x1 = w - bar_w - 8
    y1 = h - bar_h - 8
    x2 = w - 8
    y2 = h - 8
    d.rectangle([x1, y1, x2, y2], fill="black")

    try:
        font = ImageFont.truetype("DejaVuSans.ttf", max(11, int(bar_h * 0.45)))
    except Exception:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x1 + (bar_w - tw) // 2
    ty = y1 + (bar_h - th) // 2
    d.text((tx, ty), text, fill="white", font=font)
    return img


def get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "arialbd.ttf" if bold else "arial.ttf",
        "Calibri Bold.ttf" if bold else "Calibri.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ---------------------- 10) Text auto-wrap function -------------------------
def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> List[str]:
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        test = w if not cur else f"{cur} {w}"
        if draw.textlength(test, font=font) <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# --------------- 8) Annotate overall macro strip with zone boxes ------------
def annotate_macro_strip(base: Image.Image, colors: Dict[str, str]) -> Image.Image:
    img = base.copy()
    d = ImageDraw.Draw(img, "RGBA")
    w, h = img.size
    zones_left_to_right = ["Z4", "Z3", "Z2", "Z1"]
    zone_w = w / 4.0

    label_font = get_font(max(14, int(h * 0.06)), bold=True)
    for i, z in enumerate(zones_left_to_right):
        x1 = int(i * zone_w)
        x2 = int((i + 1) * zone_w)
        color = colors[z]
        rgba = tuple(int(color[j : j + 2], 16) for j in (1, 3, 5)) + (55,)
        d.rectangle([x1, 0, x2 - 1, h - 1], outline=color, width=max(2, h // 80), fill=rgba)

        tb = d.textbbox((0, 0), z, font=label_font)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        tx = x1 + (x2 - x1 - tw) // 2
        ty = 6
        d.rectangle([tx - 6, ty - 3, tx + tw + 6, ty + th + 3], fill=(255, 255, 255, 180))
        d.text((tx, ty), z, fill="black", font=label_font)

    return img


# --------------------- 9) Draw right-side four-row panels -------------------
def draw_right_panels(
    canvas: Image.Image,
    origin: Tuple[int, int],
    size: Tuple[int, int],
    zone_data: List[dict],
    macros: Dict[str, Optional[Image.Image]],
    sems: Dict[str, List[Tuple[str, Optional[Image.Image]]]],
    colors: Dict[str, str],
    missing: List[str],
) -> None:
    d = ImageDraw.Draw(canvas)
    x0, y0 = origin
    w, h = size
    row_gap = 12
    row_h = (h - row_gap * 3) // 4

    f_zone = get_font(28, bold=True)
    f_body = get_font(18)
    f_dsi = get_font(22, bold=True)

    for i, zrow in enumerate(zone_data):
        z = zrow["zone"]
        y = y0 + i * (row_h + row_gap)
        row_bg = Image.new("RGB", (w, row_h), "white")
        bg_draw = ImageDraw.Draw(row_bg)

        # ultra-light tint
        c = colors[z]
        rgb = tuple(int(c[j : j + 2], 16) for j in (1, 3, 5))
        tint = tuple(int(255 * 0.93 + v * 0.07) for v in rgb)
        bg_draw.rectangle([0, 0, w - 1, row_h - 1], fill=tint, outline="black", width=1)
        canvas.paste(row_bg, (x0, y))

        # Column geometry
        col_zone = int(w * 0.11)
        col_macro = int(w * 0.22)
        col_sem = int(w * 0.36)
        col_text = w - col_zone - col_macro - col_sem - 24

        pad = 8
        cx = x0 + pad

        # Zone block
        d.rectangle([cx, y + pad, cx + col_zone - pad, y + row_h - pad], outline=colors[z], width=2)
        zb = d.textbbox((0, 0), z, font=f_zone)
        d.text((cx + (col_zone - (zb[2]-zb[0])) // 2 - 2, y + (row_h - (zb[3]-zb[1])) // 2), z, fill=colors[z], font=f_zone)

        # Macro subimage
        cx2 = cx + col_zone + pad
        macro_box = (cx2, y + pad, cx2 + col_macro - pad, y + row_h - pad)
        d.rectangle(macro_box, outline="black", width=1)
        mimg = macros.get(z)
        if mimg is None:
            msg = f"image missing: macro_{z}.png"
            missing.append(msg)
            d.text((macro_box[0] + 8, macro_box[1] + 8), msg, fill="black", font=f_body)
        else:
            mw = macro_box[2] - macro_box[0] - 4
            mh = macro_box[3] - macro_box[1] - 4
            mfit = center_crop_keep_ratio(mimg, mw, mh)
            canvas.paste(mfit, (macro_box[0] + 2, macro_box[1] + 2))

        # SEMs (2 images)
        cx3 = cx2 + col_macro + pad
        sem_box = (cx3, y + pad, cx3 + col_sem - pad, y + row_h - pad)
        d.rectangle(sem_box, outline="black", width=1)
        sem_w = (sem_box[2] - sem_box[0] - 6) // 2
        sem_h = sem_box[3] - sem_box[1] - 4

        sem_list = sems.get(z, [])
        for j in range(2):
            sx = sem_box[0] + 2 + j * (sem_w + 2)
            sy = sem_box[1] + 2
            d.rectangle([sx, sy, sx + sem_w, sy + sem_h], outline="black", width=1)
            fname, simg = sem_list[j] if j < len(sem_list) else (f"{z}_missing_{j+1}.tif", None)
            if simg is None:
                msg = f"image missing: {fname}"
                missing.append(msg)
                d.text((sx + 4, sy + 4), msg, fill="black", font=get_font(12))
            else:
                proc = enhance_sem_grayscale(simg)
                crop = center_crop_keep_ratio(proc, sem_w - 2, sem_h - 2)
                crop = draw_scale_bar(crop, "20 μm")
                canvas.paste(crop, (sx + 1, sy + 1))

        # Text box
        cx4 = cx3 + col_sem + pad
        txt_box = (cx4, y + pad, x0 + w - pad, y + row_h - pad)
        d.rectangle(txt_box, outline="black", width=1)
        dsi_text = f"DSI = {zrow['dsi']:.3f}"
        feat = f"Main feature: {zrow['feature']}"

        d.text((txt_box[0] + 8, txt_box[1] + 8), dsi_text, fill=colors[z], font=f_dsi)
        lines = wrap_text(d, feat, f_body, txt_box[2] - txt_box[0] - 16)
        yy = txt_box[1] + 44
        for line in lines:
            d.text((txt_box[0] + 8, yy), line, fill="black", font=f_body)
            yy += 24


# -------------------- 14) Image to base64 for SVG embed ---------------------
def pil_image_to_base64_data_uri(img: Image.Image, fmt: str = "PNG") -> str:
    bio = io.BytesIO()
    img.save(bio, format=fmt)
    b64 = base64.b64encode(bio.getvalue()).decode("ascii")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


# ---------------------------- 11) Save PNG file -----------------------------
def save_png(img: Image.Image, out_path: Path) -> None:
    img.save(out_path, format="PNG", dpi=(600, 600))


# ---------------------------- 12) Save PDF file -----------------------------
def save_pdf(img: Image.Image, out_path: Path) -> None:
    rgb = img.convert("RGB")
    rgb.save(out_path, format="PDF", resolution=600.0)


# ---------------------------- 13) Save SVG file -----------------------------
def save_svg(
    out_path: Path,
    canvas_size: Tuple[int, int],
    vector_items: dict,
) -> None:
    w, h = canvas_size
    try:
        import svgwrite

        dwg = svgwrite.Drawing(str(out_path), size=(w, h), profile="full")
        dwg.add(dwg.rect(insert=(0, 0), size=(w, h), fill="white"))

        for item in vector_items["rects"]:
            dwg.add(dwg.rect(insert=(item["x"], item["y"]), size=(item["w"], item["h"]),
                             fill=item.get("fill", "none"), stroke=item.get("stroke", "black"),
                             stroke_width=item.get("stroke_width", 1), opacity=item.get("opacity", 1.0)))
        for item in vector_items["lines"]:
            dwg.add(dwg.line(start=(item["x1"], item["y1"]), end=(item["x2"], item["y2"]),
                             stroke=item.get("stroke", "black"), stroke_width=item.get("stroke_width", 1)))
        for item in vector_items["texts"]:
            dwg.add(dwg.text(item["text"], insert=(item["x"], item["y"]),
                             fill=item.get("fill", "black"), font_size=item.get("font_size", 14),
                             font_family=item.get("font_family", "DejaVu Sans"),
                             font_weight=item.get("font_weight", "normal")))
        for item in vector_items["images"]:
            dwg.add(dwg.image(href=item["href"], insert=(item["x"], item["y"]), size=(item["w"], item["h"])))

        # arrow head
        arrow = dwg.marker(insert=(8, 4), size=(8, 8), orient="auto")
        arrow.add(dwg.path(d="M0,0 L8,4 L0,8 z", fill="black"))
        dwg.defs.add(arrow)
        if "arrow_line" in vector_items:
            al = vector_items["arrow_line"]
            ln = dwg.line(start=(al["x1"], al["y1"]), end=(al["x2"], al["y2"]), stroke="black", stroke_width=2)
            ln.set_markers((None, None, arrow.get_funciri()))
            dwg.add(ln)

        dwg.save()
    except Exception:
        # Fallback: manual SVG XML
        lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
            '<rect x="0" y="0" width="100%" height="100%" fill="white"/>',
            '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="black"/></marker></defs>',
        ]
        for item in vector_items["rects"]:
            lines.append(
                f'<rect x="{item["x"]}" y="{item["y"]}" width="{item["w"]}" height="{item["h"]}" '
                f'fill="{item.get("fill", "none")}" stroke="{item.get("stroke", "black")}" stroke-width="{item.get("stroke_width", 1)}" opacity="{item.get("opacity", 1.0)}"/>'
            )
        for item in vector_items["lines"]:
            lines.append(
                f'<line x1="{item["x1"]}" y1="{item["y1"]}" x2="{item["x2"]}" y2="{item["y2"]}" '
                f'stroke="{item.get("stroke", "black")}" stroke-width="{item.get("stroke_width", 1)}"/>'
            )
        if "arrow_line" in vector_items:
            al = vector_items["arrow_line"]
            lines.append(
                f'<line x1="{al["x1"]}" y1="{al["y1"]}" x2="{al["x2"]}" y2="{al["y2"]}" stroke="black" stroke-width="2" marker-end="url(#arrow)"/>'
            )
        for item in vector_items["texts"]:
            lines.append(
                f'<text x="{item["x"]}" y="{item["y"]}" fill="{item.get("fill", "black")}" font-size="{item.get("font_size", 14)}" '
                f'font-family="{item.get("font_family", "DejaVu Sans")}" font-weight="{item.get("font_weight", "normal")}">{item["text"]}</text>'
            )
        for item in vector_items["images"]:
            lines.append(
                f'<image x="{item["x"]}" y="{item["y"]}" width="{item["w"]}" height="{item["h"]}" href="{item["href"]}"/>'
            )
        lines.append("</svg>")
        out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    paths = setup_paths()

    zone_data = [
        {"zone": "Z1", "dsi": 0.220, "feature": "mild surface damage; fine cracking / slight wear", "macro": "macro_Z1.png", "sem": ["Z1_img06_raw.tif", "Z1_img01_raw.tif"]},
        {"zone": "Z2", "dsi": 0.248, "feature": "moderate transitional wear", "macro": "macro_Z2.png", "sem": ["Z2_img04_raw.tif", "Z2_img01_raw.tif"]},
        {"zone": "Z3", "dsi": 0.357, "feature": "increased roughening; crack–wear coexistence", "macro": "macro_Z3.png", "sem": ["Z3_img09_raw.tif", "Z3_img01_raw.tif"]},
        {"zone": "Z4", "dsi": 0.461, "feature": "severe mixed surface damage", "macro": "macro_Z4.png", "sem": ["Z4_img07_raw.tif", "Z4_img08_raw.tif"]},
    ]
    colors = {"Z1": "#2D6CDF", "Z2": "#E58A00", "Z3": "#2E9E5B", "Z4": "#C73636"}

    W, H = 5200, 3000
    left_w = int(W * 0.43)
    margin = 60

    fig = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(fig)

    title_font = get_font(54, bold=True)
    body_font = get_font(26)
    foot_font = get_font(20)

    title = "Macro-to-micro correspondence of barrel zones Z1–Z4"
    tbox = draw.textbbox((0, 0), title, font=title_font)
    draw.text(((W - (tbox[2]-tbox[0])) // 2, 20), title, fill="black", font=title_font)

    missing: List[str] = []

    # Left panel
    left_panel = (margin, 120, left_w - margin, H - 180)
    draw.rectangle(left_panel, outline="black", width=2)

    overall = load_image_any(paths["macro_dir"] / "macro_overall_Z1_Z4.png")
    if overall is None:
        missing.append("image missing: macro_overall_Z1_Z4.png")
        draw.text((left_panel[0] + 20, left_panel[1] + 20), "image missing: macro_overall_Z1_Z4.png", fill="black", font=body_font)
        strip_img = Image.new("RGB", (left_panel[2]-left_panel[0]-40, 600), "white")
    else:
        strip_target_w = left_panel[2] - left_panel[0] - 40
        strip_target_h = int(strip_target_w * overall.height / max(1, overall.width))
        strip_target_h = min(strip_target_h, left_panel[3] - left_panel[1] - 220)
        strip_img = fit_image_keep_ratio(overall, strip_target_w, strip_target_h)

    strip_img = annotate_macro_strip(strip_img, colors)
    sx = left_panel[0] + 20
    sy = left_panel[1] + 30
    fig.paste(strip_img, (sx, sy))

    draw.text((left_panel[0] + 20, sy + strip_img.height + 24), "Left side of strip = Z4", fill="black", font=body_font)
    draw.text((left_panel[0] + 20, sy + strip_img.height + 64), "Right side of strip = Z1", fill="black", font=body_font)
    draw.text((left_panel[0] + 20, sy + strip_img.height + 110), "Z4 side", fill="black", font=body_font)
    ax1, ay = left_panel[0] + 150, sy + strip_img.height + 122
    ax2 = left_panel[2] - 100
    draw.line([ax1, ay, ax2, ay], fill="black", width=4)
    draw.polygon([(ax2, ay), (ax2 - 18, ay - 10), (ax2 - 18, ay + 10)], fill="black")
    draw.text((ax2 + 15, sy + strip_img.height + 110), "Z1 side", fill="black", font=body_font)

    # Right panel data loading
    macros: Dict[str, Optional[Image.Image]] = {}
    sems: Dict[str, List[Tuple[str, Optional[Image.Image]]]] = {}
    sem_roots = [paths["sem_root_1"], paths["sem_root_2"]]

    for zd in zone_data:
        z = zd["zone"]
        macros[z] = load_image_any(paths["macro_dir"] / zd["macro"])
        if macros[z] is None:
            missing.append(f"image missing: {zd['macro']}")

        sems[z] = []
        for fname in zd["sem"]:
            fpath = find_file_recursive(sem_roots, fname)
            if fpath is None:
                sems[z].append((fname, None))
                missing.append(f"image missing: {fname}")
            else:
                sems[z].append((fname, load_image_any(fpath)))

    right_x = left_w + 20
    right_y = 120
    right_w = W - right_x - margin
    right_h = H - 260
    draw_right_panels(fig, (right_x, right_y), (right_w, right_h), zone_data, macros, sems, colors, missing)

    draw.text((margin, H - 60), "DSI = Damage Severity Index.", fill="black", font=foot_font)

    # Save PNG/PDF
    save_png(fig, paths["out_png"])
    save_pdf(fig, paths["out_pdf"])

    # Build simplified vector + embedded raster SVG
    vector_items = {"rects": [], "lines": [], "texts": [], "images": []}
    vector_items["texts"].append({"text": title, "x": W * 0.24, "y": 80, "font_size": 46, "font_weight": "bold"})
    vector_items["texts"].append({"text": "Left side of strip = Z4", "x": left_panel[0] + 20, "y": sy + strip_img.height + 50, "font_size": 24})
    vector_items["texts"].append({"text": "Right side of strip = Z1", "x": left_panel[0] + 20, "y": sy + strip_img.height + 90, "font_size": 24})
    vector_items["texts"].append({"text": "DSI = Damage Severity Index.", "x": margin, "y": H - 30, "font_size": 20})
    vector_items["arrow_line"] = {"x1": ax1, "y1": ay, "x2": ax2, "y2": ay}

    # Embed final composed figure as base layer + vector overlays kept editable
    # (keeps compatibility while ensuring text/line objects remain editable)
    vector_items["images"].append({"x": 0, "y": 0, "w": W, "h": H, "href": pil_image_to_base64_data_uri(fig, "PNG")})
    save_svg(paths["out_svg"], (W, H), vector_items)

    print("Figure saved:")
    print(str(paths["out_png"]))
    print(str(paths["out_pdf"]))
    print(str(paths["out_svg"]))

    if missing:
        uniq = sorted(set(missing))
        print("\nmissing file list:")
        for m in uniq:
            print(m)


if __name__ == "__main__":
    main()
