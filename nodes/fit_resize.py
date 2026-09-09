"""
Fit and Resize - Geekatplay 3D Multiview
Geekatplay Studio - Vladimir Chopine  |  https://www.geekatplay.com

Brings an image to an exact output size without ever stretching or cutting it.

The panel of a turnaround sheet is usually a tall, narrow strip, and a plain
resize to 512x512 squashes the character. This node first grows the canvas with
background-coloured margin until it matches the requested proportions - a
1024x400 strip headed for 512x512 becomes 1024x1024 - and only then scales the
whole thing down. Nothing is cropped and nothing changes shape.
"""

import torch

import comfy.utils

try:
    from .branding import CATEGORY
except ImportError:  # pragma: no cover
    from branding import CATEGORY


RESIZE_METHODS = ("lanczos", "bicubic", "bilinear", "area", "nearest-exact")
BACKGROUND_SOURCES = ("auto (sample edges)", "custom color")
ALIGNMENTS = ("center", "start", "end")

# Fraction of the shorter side read from each border when sampling the backdrop.
EDGE_SAMPLE_FRACTION = 0.02


def hex_to_rgb(value):
    """Accept #rgb, #rrggbb or the same without the hash; return 0..1 floats."""
    text = str(value).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(channel * 2 for channel in text)
    if len(text) != 6:
        raise ValueError(
            "background_color must be a hex colour such as #000000, got '{}'".format(value)
        )
    try:
        return tuple(int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        raise ValueError(
            "background_color must be a hex colour such as #000000, got '{}'".format(value)
        )


def sample_edge_color(image):
    """
    Median colour of the four borders.

    A median rather than a mean, so a subject that touches one edge tints the
    result far less than it would otherwise.
    """
    _, height, width, channels = image.shape
    depth = max(1, int(round(min(height, width) * EDGE_SAMPLE_FRACTION)))
    depth = min(depth, height, width)

    borders = torch.cat(
        (
            image[:, :depth, :, :].reshape(-1, channels),
            image[:, -depth:, :, :].reshape(-1, channels),
            image[:, :, :depth, :].reshape(-1, channels),
            image[:, :, -depth:, :].reshape(-1, channels),
        ),
        dim=0,
    )
    return borders.median(dim=0).values


def canvas_size(width, height, target_width, target_height):
    """Smallest canvas that holds the image and matches the target proportions."""
    if width * target_height > target_width * height:
        # Wider than the target: grow vertically.
        return width, max(height, int(round(width * target_height / target_width)))
    # Taller than the target: grow horizontally.
    return max(width, int(round(height * target_width / target_height))), height


def offset_for(total, size, alignment):
    slack = total - size
    if alignment == "start":
        return 0
    if alignment == "end":
        return slack
    return slack // 2


class GeekatplayFitResize:
    """Pads an image out to the requested proportions, then scales it to size."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {"default": 512, "min": 1, "max": 16384, "step": 8,
                                  "tooltip": "Exact width of the image leaving this node."}),
                "height": ("INT", {"default": 512, "min": 1, "max": 16384, "step": 8,
                                   "tooltip": "Exact height of the image leaving this node."}),
                "background_source": (BACKGROUND_SOURCES, {
                    "default": BACKGROUND_SOURCES[0],
                    "tooltip": "Read the margin colour from the image borders, or use the colour below.",
                }),
                "background_color": ("STRING", {
                    "default": "#000000",
                    "tooltip": "Hex colour for the added margin when 'custom color' is selected.",
                }),
                "alignment": (ALIGNMENTS, {
                    "default": "center",
                    "tooltip": "Where the original sits once the canvas grows: centred, or pushed to one side.",
                }),
                "resize_method": (RESIZE_METHODS, {"default": "lanczos"}),
            }
        }

    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Extends an image with matching background until it has the requested "
        "proportions, then scales it to the exact output size. The subject is "
        "never stretched and never cropped."
    )

    RETURN_TYPES = ("IMAGE", "INT", "INT")
    RETURN_NAMES = ("image", "width", "height")
    FUNCTION = "fit"

    def fit(self, image, width, height, background_source, background_color,
            alignment, resize_method):
        batch, source_height, source_width, channels = image.shape

        target_width = max(1, int(width))
        target_height = max(1, int(height))

        # --- grow the canvas to the target proportions -----------------------
        pad_width, pad_height = canvas_size(
            source_width, source_height, target_width, target_height
        )

        if pad_width != source_width or pad_height != source_height:
            if background_source == BACKGROUND_SOURCES[0]:
                fill = sample_edge_color(image).to(device=image.device, dtype=image.dtype)
            else:
                rgb = hex_to_rgb(background_color)
                if channels >= 4:
                    # Keep the added margin opaque.
                    rgb = tuple(rgb) + (1.0,) * (channels - 3)
                fill = torch.tensor(rgb[:channels], device=image.device, dtype=image.dtype)

            canvas = fill.view(1, 1, 1, channels).repeat(batch, pad_height, pad_width, 1)

            left = offset_for(pad_width, source_width, alignment)
            top = offset_for(pad_height, source_height, alignment)
            canvas[:, top:top + source_height, left:left + source_width, :] = image
        else:
            canvas = image

        # --- scale the padded canvas to the exact requested size -------------
        if pad_width == target_width and pad_height == target_height:
            result = canvas
        else:
            samples = canvas.movedim(-1, 1)
            samples = comfy.utils.common_upscale(
                samples, target_width, target_height, resize_method, "disabled"
            )
            result = samples.movedim(1, -1)

        return (result.clamp(0.0, 1.0), target_width, target_height)
