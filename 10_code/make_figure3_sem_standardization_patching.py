"""Create Fig. 3: SEM image standardization and patch construction workflow.

The script reads the example raw SEM image, builds the standardization and
4 x 4 patching schematic, and exports PNG, TIF, and SVG versions suitable for
journal-figure editing.
"""

from __future__ import annotations

from pathlib import Path
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from matplotlib.patches import FancyArrowPatch, Rectangle
from PIL import Image

PROJECT_DIR = Path(r"E:\Barrel_SEM_Z1_Z4_New")
RAW_IMAGE_PATH = PROJECT_DIR / "02_raw_SEM_images" / "Z2_img01_raw.tif"
OUTPUT_DIR = PROJECT_DIR / "07_figures_main"

OUT_PNG = OUTPUT_DIR / "Figure_3_SEM_standardization_patch_workflow.png"
OUT_TIF = OUTPUT_DIR / "Figure_3_SEM_standardization_patch_workflow.tif"
OUT_SVG = OUTPUT_DIR / "Figure_3_SEM_standardization_patch_workflow.svg"

STANDARD_SIZE = (2048, 1536)  # width, height
PATCH_COLS = 4
PATCH_ROWS = 4
PATCH_SIZE = (STANDARD_SIZE[0] // PATCH_COLS, STANDARD_SIZE[1] // PATCH_ROWS)
DARK_RED = "#8B1A1A"


def configure_fonts() -> None:
    """Use Times New Roman when available, otherwise DejaVu Serif."""
    available = {f.name for f in mpl.font_manager.fontManager.ttflist}
    family = "Times New Roman" if "Times New Roman" in available else "DejaVu Serif"
    mpl.rcParams.update(
        {
            "font.family": family,
            "font.size": 9,
            "axes.linewidth": 0.8,
            "svg.fonttype": "none",  # keep SVG text editable
            "savefig.facecolor": "white",
        }
    )


def read_sem_image(path: Path) -> np.ndarray:
    """Read a TIF SEM image as 8-bit grayscale from 8/16-bit or RGB input."""
    if not path.exists():
        raise FileNotFoundError(f"Raw SEM image not found: {path}")

    with Image.open(path) as img:
        arr = np.asarray(img)

    if arr.ndim == 3:
        arr = arr[..., :3].astype(np.float32)
        arr = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    else:
        arr = arr.astype(np.float32)

    finite = np.isfinite(arr)
    if not finite.any():
        raise ValueError(f"Image contains no finite pixels: {path}")
    vmin = float(np.nanmin(arr[finite]))
    vmax = float(np.nanmax(arr[finite]))
    if vmax <= vmin:
        return np.zeros(arr.shape, dtype=np.uint8)
    return np.clip((arr - vmin) / (vmax - vmin) * 255.0, 0, 255).astype(np.uint8)


def crop_sem_bar(image: np.ndarray) -> np.ndarray:
    """Crop the bottom SEM parameter/scale-bar strip."""
    height = image.shape[0]
    crop_px = 160 if height > 1600 else max(1, int(round(height * 0.10)))
    return image[: height - crop_px, :]


def resize_image(image: np.ndarray, size: tuple[int, int] = STANDARD_SIZE) -> np.ndarray:
    """Resize grayscale image to the fixed standard dimensions."""
    return np.asarray(Image.fromarray(image).resize(size, Image.Resampling.BICUBIC))


def normalize_0_255(image: np.ndarray) -> np.ndarray:
    """Normalize grayscale values to 0-255."""
    arr = image.astype(np.float32)
    imin, imax = float(arr.min()), float(arr.max())
    if imax <= imin:
        return np.zeros_like(image, dtype=np.uint8)
    return np.clip((arr - imin) / (imax - imin) * 255.0, 0, 255).astype(np.uint8)


def hide_axis(ax: plt.Axes) -> None:
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)


def show_image(ax: plt.Axes, image: np.ndarray, title: str | None = None) -> None:
    ax.imshow(image, cmap="gray", vmin=0, vmax=255)
    hide_axis(ax)
    if title:
        ax.set_title(title, fontsize=9, pad=3)


def panel_box(fig: plt.Figure, axes: list[plt.Axes], label: str) -> None:
    boxes = [ax.get_position(fig) for ax in axes]
    x0 = min(b.x0 for b in boxes) - 0.010
    y0 = min(b.y0 for b in boxes) - 0.017
    x1 = max(b.x1 for b in boxes) + 0.010
    y1 = max(b.y1 for b in boxes) + 0.024
    fig.add_artist(
        Rectangle(
            (x0, y0),
            x1 - x0,
            y1 - y0,
            transform=fig.transFigure,
            fill=False,
            linestyle=(0, (3, 3)),
            linewidth=1.1,
            edgecolor="black",
            zorder=20,
        )
    )
    fig.text(x0 + 0.006, y1 - 0.015, label, fontsize=10, weight="bold", va="top")


def fig_arrow(fig: plt.Figure, start: tuple[float, float], end: tuple[float, float], ms: int = 12) -> None:
    fig.add_artist(
        FancyArrowPatch(
            start,
            end,
            transform=fig.transFigure,
            arrowstyle="-|>",
            mutation_scale=ms,
            linewidth=1.6,
            color=DARK_RED,
            shrinkA=1,
            shrinkB=1,
            zorder=25,
        )
    )


def connect_axes(fig: plt.Figure, left: plt.Axes, right: plt.Axes) -> None:
    lb, rb = left.get_position(fig), right.get_position(fig)
    fig_arrow(fig, (lb.x1 + 0.004, (lb.y0 + lb.y1) / 2), (rb.x0 - 0.004, (rb.y0 + rb.y1) / 2))


def draw_zone_icon(ax: plt.Axes) -> None:
    hide_axis(ax)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    y, h = 0.36, 0.22
    zones = ["Z1", "Z2", "Z3", "Z4"]
    for i, z in enumerate(zones):
        x = 0.08 + i * 0.21
        color = "#EFEFEF" if z != "Z2" else "#D9D9D9"
        ax.add_patch(Rectangle((x, y), 0.18, h, facecolor=color, edgecolor="black", linewidth=0.8))
        ax.text(x + 0.09, y + h / 2, z, ha="center", va="center", fontsize=8)
    ax.annotate("", xy=(0.38, y + h + 0.11), xytext=(0.38, y + h + 0.34), arrowprops=dict(arrowstyle="-|>", color=DARK_RED, lw=1.2))


def draw_grid(ax: plt.Axes, image: np.ndarray) -> None:
    show_image(ax, image)
    height, width = image.shape
    for i in range(1, PATCH_COLS):
        ax.axvline(i * width / PATCH_COLS, color="white", lw=1.0)
        ax.axvline(i * width / PATCH_COLS, color="black", lw=0.35)
    for i in range(1, PATCH_ROWS):
        ax.axhline(i * height / PATCH_ROWS, color="white", lw=1.0)
        ax.axhline(i * height / PATCH_ROWS, color="black", lw=0.35)
    ax.set_title("4×4    512×384", fontsize=9, pad=3)


def draw_metadata(ax: plt.Axes) -> None:
    hide_axis(ax)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    headers = ["Zone", "Image_ID", "Patch_ID"]
    vals = ["Z2", "img01", "p_01"]
    x0, y0, w, h = 0.08, 0.58, 0.84, 0.22
    for i in range(3):
        xi = x0 + i * w / 3
        ax.add_patch(Rectangle((xi, y0), w / 3, h, fill=False, edgecolor="black", linewidth=0.9))
        ax.text(xi + w / 6, y0 + h * 0.68, headers[i], ha="center", va="center", fontsize=8)
        ax.text(xi + w / 6, y0 + h * 0.28, vals[i], ha="center", va="center", fontsize=8)
    ax.text(0.5, 0.41, "Image_ID grouped split", ha="center", fontsize=8)
    y = 0.18
    labels = ["Train", "Val", "Test"]
    xs = [0.18, 0.43, 0.68]
    for x, lab in zip(xs, labels):
        ax.add_patch(Rectangle((x, y), 0.18, 0.10, fill=False, edgecolor="black", linewidth=0.9))
        ax.text(x + 0.09, y + 0.05, lab, ha="center", va="center", fontsize=8)
    ax.text(0.5, 0.08, "by image", ha="center", fontsize=8)


def build_figure(raw: np.ndarray) -> plt.Figure:
    cropped = crop_sem_bar(raw)
    resized = resize_image(cropped)
    normalized = normalize_0_255(resized)

    fig = plt.figure(figsize=(15.5, 5.1), facecolor="white", constrained_layout=False)
    outer = GridSpec(1, 4, figure=fig, left=0.025, right=0.985, top=0.90, bottom=0.16, wspace=0.23, width_ratios=[1.0, 1.55, 1.35, 0.95])

    # Panel 1
    gs1 = GridSpecFromSubplotSpec(2, 1, subplot_spec=outer[0], height_ratios=[5, 1], hspace=0.12)
    ax_raw = fig.add_subplot(gs1[0]); show_image(ax_raw, raw, "Raw SEM")
    ax_zone = fig.add_subplot(gs1[1]); draw_zone_icon(ax_zone)

    # Panel 2
    gs2 = GridSpecFromSubplotSpec(2, 4, subplot_spec=outer[1], height_ratios=[5, 0.9], hspace=0.18, wspace=0.11)
    std_axes = [fig.add_subplot(gs2[0, i]) for i in range(4)]
    for ax, im, title in zip(std_axes, [raw, cropped, resized, normalized], ["Raw", "Crop bar", "Resize", "Normalize"]):
        show_image(ax, im, title)
    for ax in std_axes[1:]:
        ax.set_aspect("equal")
    ax_formula = fig.add_subplot(gs2[1, :]); hide_axis(ax_formula)
    ax_formula.text(0.5, 0.50, r"$I_{norm}=(I-I_{min})/(I_{max}-I_{min})\times255$        2048×1536        0–255", ha="center", va="center", fontsize=8.5)
    for a, b in zip(std_axes[:-1], std_axes[1:]):
        connect_axes(fig, a, b)

    # Panel 3
    gs3 = GridSpecFromSubplotSpec(6, 4, subplot_spec=outer[2], height_ratios=[3.25, 0.28, 1, 1, 1, 1], hspace=0.13, wspace=0.04)
    ax_grid = fig.add_subplot(gs3[0, 1:3]); draw_grid(ax_grid, normalized)
    ax_patch_label = fig.add_subplot(gs3[1, :]); hide_axis(ax_patch_label)
    ax_patch_label.text(0.5, 0.5, "16 patches / image     640 total patches", ha="center", va="center", fontsize=8.5)
    patch_axes = []
    for r in range(4):
        for c in range(4):
            ax = fig.add_subplot(gs3[2 + r, c])
            patch_id = r * 4 + c + 1
            y0, y1 = r * PATCH_SIZE[1], (r + 1) * PATCH_SIZE[1]
            x0, x1 = c * PATCH_SIZE[0], (c + 1) * PATCH_SIZE[0]
            show_image(ax, normalized[y0:y1, x0:x1])
            ax.set_title(f"p_{patch_id:02d}", fontsize=5.2, pad=0.6)
            patch_axes.append(ax)
    gb, lb = ax_grid.get_position(fig), ax_patch_label.get_position(fig)
    fig_arrow(fig, ((gb.x0 + gb.x1) / 2, gb.y0 - 0.006), ((lb.x0 + lb.x1) / 2, lb.y1 + 0.002), ms=11)

    # Panel 4
    gs4 = GridSpecFromSubplotSpec(1, 1, subplot_spec=outer[3])
    ax_meta = fig.add_subplot(gs4[0]); draw_metadata(ax_meta)

    panel_box(fig, [ax_raw, ax_zone], "Raw SEM")
    panel_box(fig, std_axes + [ax_formula], "Standardization")
    panel_box(fig, [ax_grid, ax_patch_label] + patch_axes, "4×4 patching")
    panel_box(fig, [ax_meta], "Patch metadata")

    # Main between-panel arrows.
    panel_axes = [ax_raw, std_axes[0], ax_grid, ax_meta]
    for a, b in zip(panel_axes[:-1], panel_axes[1:]):
        ab, bb = a.get_position(fig), b.get_position(fig)
        fig_arrow(fig, (ab.x1 + 0.018, (ab.y0 + ab.y1) / 2), (bb.x0 - 0.018, (bb.y0 + bb.y1) / 2), ms=14)

    fig.text(0.5, 0.055, "Fig. 3. SEM image standardization and patch construction workflow.", ha="center", va="center", fontsize=11)
    return fig


def save_outputs(fig: plt.Figure) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=600, bbox_inches="tight", pad_inches=0.04)
    fig.savefig(OUT_SVG, bbox_inches="tight", pad_inches=0.04)
    # Save TIFF through Pillow to ensure a broadly compatible compressed RGB file.
    tmp_png = OUTPUT_DIR / "._figure3_tmp_for_tif.png"
    fig.savefig(tmp_png, dpi=600, bbox_inches="tight", pad_inches=0.04)
    with Image.open(tmp_png) as im:
        im.convert("RGB").save(OUT_TIF, compression="tiff_lzw", dpi=(600, 600))
    tmp_png.unlink(missing_ok=True)


def main() -> None:
    configure_fonts()
    raw = read_sem_image(RAW_IMAGE_PATH)
    fig = build_figure(raw)
    save_outputs(fig)
    plt.close(fig)
    for path in (OUT_PNG, OUT_TIF, OUT_SVG):
        print(path)


if __name__ == "__main__":
    main()
