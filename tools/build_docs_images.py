"""
Documentation image builder - Geekatplay 3D Multiview
Geekatplay Studio - Vladimir Chopine  |  https://www.geekatplay.com

Renders the figures used by README.md from the bundled demo sheet, running the
real nodes wherever a figure claims to show what a node produces. Re-run it
after changing the splitter or the fitting maths so the documentation cannot
drift away from the code.

    python tools/build_docs_images.py
"""

import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "nodes"))

SHEET = os.path.join(ROOT, "workflows", "assets", "4-ref-caveman.png")
OUT_DIR = os.path.join(ROOT, "docs", "images")

# The palette the node itself draws with, so the figures match the real thing.
PANEL_BG = (18, 20, 28)
CANVAS_BG = (11, 13, 20)
TEXT = (230, 232, 240)
MUTED = (138, 144, 166)
GUIDE_COLORS = [(0, 229, 255), (0, 255, 102), (255, 153, 0)]
SLICE_TINTS = [(0, 153, 255), (0, 255, 102), (255, 153, 0), (200, 0, 255)]
ACCENT = (0, 165, 255)
GOOD = (0, 255, 102)
BAD = (255, 90, 90)

GUIDES = [0.305, 0.48, 0.7735]


def font(size, bold=False):
    for name in (("arialbd.ttf", "arial.ttf") if bold else ("arial.ttf",)):
        for folder in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/Library/Fonts"):
            path = os.path.join(folder, name)
            if os.path.isfile(path):
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    pass
    for fallback in ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",):
        try:
            return ImageFont.truetype(fallback, size)
        except OSError:
            pass
    return ImageFont.load_default()


def tint(image, rgb, strength=0.10):
    layer = Image.new("RGB", image.size, rgb)
    return Image.blend(image, layer, strength)


def rounded(draw, box, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


# --------------------------------------------------------------------- figure 1

def figure_guides(sheet):
    """The sheet with the three guides and the four panels they produce."""
    pad = 24
    header = 34
    legend = 30
    view_w = 1120
    scale = view_w / sheet.width
    view_h = int(sheet.height * scale)

    width = view_w + pad * 2
    height = header + view_h + legend + pad * 2 + 10
    canvas = Image.new("RGB", (width, height), PANEL_BG)
    draw = ImageDraw.Draw(canvas)

    draw.text((pad, pad - 4), "Geekatplay | Turnaround Splitter", font=font(15, True), fill=TEXT)
    label = f"{sheet.width} x {sheet.height} px"
    draw.text((width - pad - draw.textlength(label, font=font(13)), pad - 2),
              label, font=font(13), fill=MUTED)

    top = header + pad
    view = sheet.resize((view_w, view_h), Image.LANCZOS).convert("RGB")

    # Tint each slice the way the node does.
    edges = [0.0] + GUIDES + [1.0]
    for index in range(4):
        left = int(edges[index] * view_w)
        right = int(edges[index + 1] * view_w)
        band = view.crop((left, 0, right, view_h))
        view.paste(tint(band, SLICE_TINTS[index]), (left, 0))

    canvas.paste(view, (pad, top))
    draw.rectangle((pad, top, pad + view_w, top + view_h), outline=(0, 153, 255), width=1)

    # Slice numbers.
    for index in range(4):
        left = pad + edges[index] * view_w
        right = pad + edges[index + 1] * view_w
        cx = (left + right) / 2
        draw.rectangle((cx - 15, top + 8, cx + 15, top + 36), fill=(0, 0, 0))
        text = str(index + 1)
        draw.text((cx - draw.textlength(text, font=font(20, True)) / 2, top + 11),
                  text, font=font(20, True), fill=(255, 255, 255))

    # Guides with their grab tabs and pixel readouts.
    for index, guide in enumerate(GUIDES):
        x = pad + guide * view_w
        color = GUIDE_COLORS[index]
        draw.line((x, top, x, top + view_h), fill=color, width=3)
        tab_h, tab_w = 46, 15
        tab_y = top + view_h / 2 - tab_h / 2
        draw.rectangle((x - tab_w / 2, tab_y, x + tab_w / 2, tab_y + tab_h),
                       fill=color, outline=CANVAS_BG, width=2)
        readout = f"{round(guide * sheet.width)}px"
        tw = draw.textlength(readout, font=font(13, True))
        draw.rectangle((x - tw / 2 - 5, top + view_h - 30, x + tw / 2 + 5, top + view_h - 8),
                       fill=(0, 0, 0))
        draw.text((x - tw / 2, top + view_h - 28), readout, font=font(13, True), fill=color)

    # Legend, matching the node footer.
    ly = top + view_h + 12
    lx = pad
    bounds = [0] + [round(g * sheet.width) for g in GUIDES] + [sheet.width]
    for index in range(4):
        w = bounds[index + 1] - bounds[index]
        draw.rectangle((lx, ly + 4, lx + 11, ly + 15), fill=SLICE_TINTS[index])
        text = f"{index + 1}: {w}x{sheet.height}"
        draw.text((lx + 17, ly + 1), text, font=font(13), fill=MUTED)
        lx += 17 + draw.textlength(text, font=font(13)) + 26

    hint = "drag a guide to move the cut"
    draw.text((width - pad - draw.textlength(hint, font=font(13)), ly + 1),
              hint, font=font(13), fill=MUTED)
    return canvas


# --------------------------------------------------------------------- figure 2

def figure_fit(sheet):
    """Stretch and crop against the node's pad-then-scale, all at 512x512."""
    import numpy as np
    import torch
    from fit_resize import GeekatplayFitResize

    panel = sheet.crop((0, 0, int(sheet.width * GUIDES[0]), sheet.height)).convert("RGB")

    stretched = panel.resize((512, 512), Image.LANCZOS)

    side = min(panel.width, panel.height)
    left = (panel.width - side) // 2
    top_c = (panel.height - side) // 2
    cropped = panel.crop((left, top_c, left + side, top_c + side)).resize((512, 512), Image.LANCZOS)

    # The real node, so this panel cannot drift from the shipped behaviour.
    tensor = torch.from_numpy(np.array(panel).astype("float32") / 255.0)[None]
    result, _, _ = GeekatplayFitResize().fit(
        tensor, 512, 512, "auto (sample edges)", "#000000", "center", "lanczos"
    )
    fitted = Image.fromarray((result[0].numpy() * 255).round().astype("uint8"))

    entries = [
        (stretched, "Plain resize", "squashed to fit", BAD),
        (cropped, "Crop to square", "head and feet lost", BAD),
        (fitted, "Fit & Resize", "padded, then scaled", GOOD),
    ]

    pad = 24
    gap = 22
    cap = 58
    header = 40
    width = pad * 2 + 512 * 3 + gap * 2
    height = header + 512 + cap + pad * 2
    canvas = Image.new("RGB", (width, height), PANEL_BG)
    draw = ImageDraw.Draw(canvas)

    draw.text((pad, pad - 2),
              f"One {panel.width}x{panel.height} panel brought to 512 x 512",
              font=font(19, True), fill=TEXT)

    for index, (image, title, note, color) in enumerate(entries):
        x = pad + index * (512 + gap)
        y = header + pad
        canvas.paste(image, (x, y))
        draw.rectangle((x, y, x + 511, y + 511), outline=color, width=3)
        draw.text((x, y + 522), title, font=font(18, True), fill=color)
        draw.text((x, y + 546), note, font=font(15), fill=MUTED)

    return canvas


# --------------------------------------------------------------------- figure 3

def figure_pipeline():
    """How the two shipped workflows fit together."""
    width, height = 1180, 440
    canvas = Image.new("RGB", (width, height), PANEL_BG)
    draw = ImageDraw.Draw(canvas)

    draw.text((30, 24), "What the workflows do", font=font(20, True), fill=TEXT)

    rows = [
        (86, "Turnaround workflow", ACCENT, [
            ("Turnaround\nSheet", MUTED),
            ("Turnaround\nSplitter", ACCENT),
            ("4x Fit &\nResize", ACCENT),
            ("Pixal3D\nmultiview", MUTED),
            ("Textured\nmesh", MUTED),
        ]),
        (256, "Mesh cleanup workflow (adds this tail)", GOOD, [
            ("Textured\nmesh", MUTED),
            ("Mesh to File\n(bridge)", ACCENT),
            ("Meshwright\nFix Mesh", GOOD),
            ("File to 3D\n(bridge)", ACCENT),
            ("Clean\nmodel", MUTED),
        ]),
    ]

    box_w, box_h, gap = 176, 84, 46
    for top, title, color, boxes in rows:
        draw.text((30, top - 26), title, font=font(15, True), fill=color)
        x = 30
        for index, (label, box_color) in enumerate(boxes):
            filled = box_color is not MUTED
            rounded(draw, (x, top, x + box_w, top + box_h), 10,
                    fill=(24, 28, 40) if filled else (16, 18, 26),
                    outline=box_color, width=2)
            lines = label.split("\n")
            for li, line in enumerate(lines):
                tw = draw.textlength(line, font=font(15, True))
                draw.text((x + box_w / 2 - tw / 2,
                           top + box_h / 2 - len(lines) * 10 + li * 20 - 2),
                          line, font=font(15, True), fill=TEXT if filled else MUTED)
            if index < len(boxes) - 1:
                ax = x + box_w + 8
                ay = top + box_h / 2
                draw.line((ax, ay, ax + gap - 16, ay), fill=MUTED, width=2)
                draw.polygon([(ax + gap - 16, ay - 5), (ax + gap - 16, ay + 5),
                              (ax + gap - 6, ay)], fill=MUTED)
            x += box_w + gap

    draw.text((30, 380),
              "Blue = nodes in this pack.  Green = Meshwright, a separate download.",
              font=font(14), fill=MUTED)
    draw.text((30, 404),
              "Geekatplay Studio - Vladimir Chopine | geekatplay.com",
              font=font(14), fill=MUTED)
    return canvas


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    sheet = Image.open(SHEET)

    figures = {
        "splitter-guides.png": lambda: figure_guides(sheet),
        "fit-resize.png": lambda: figure_fit(sheet),
        "pipeline.png": figure_pipeline,
    }

    for name, make in figures.items():
        path = os.path.join(OUT_DIR, name)
        make().save(path, optimize=True)
        print("wrote {}  ({} KB)".format(path, os.path.getsize(path) // 1024))


if __name__ == "__main__":
    main()
