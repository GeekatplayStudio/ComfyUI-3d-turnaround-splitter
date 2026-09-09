"""
Turnaround Splitter - Geekatplay 3D Multiview
Geekatplay Studio - Vladimir Chopine  |  https://www.geekatplay.com

Loads one turnaround reference sheet and cuts it into four views along three
vertical guides. The guides are dragged straight over the preview drawn inside
the node, so the cut lines are placed by eye instead of by typing pixel offsets
into four separate crop nodes.

Each view leaves the node with its own measured width and height, because the
four panels of a hand-made sheet are almost never the same width.
"""

import hashlib
import os

import numpy as np
import torch
from PIL import Image, ImageOps

import folder_paths

try:  # ComfyUI ships this helper; it retries on truncated files.
    import node_helpers
except ImportError:  # pragma: no cover - stand-alone import for tests
    node_helpers = None

try:
    from .branding import CATEGORY
except ImportError:  # pragma: no cover
    from branding import CATEGORY


VIEW_COUNT = 4
GUIDE_COUNT = VIEW_COUNT - 1


def _pillow(function, *args, **kwargs):
    if node_helpers is not None:
        return node_helpers.pillow(function, *args, **kwargs)
    return function(*args, **kwargs)


def load_sheet(path):
    """Read the sheet as a single (1, H, W, 3) float image in the 0..1 range."""
    image = _pillow(Image.open, path)
    image = _pillow(ImageOps.exif_transpose, image)
    image = image.convert("RGB")
    array = np.array(image).astype(np.float32) / 255.0
    return torch.from_numpy(array)[None,]


def guide_boundaries(width, guides):
    """
    Turn three 0..1 guide positions into the five pixel boundaries of four slices.

    The guides are sorted and then pushed apart just enough to keep every slice at
    least one pixel wide, so dragging two guides onto each other degrades into a
    thin slice rather than an empty tensor.
    """
    if width < VIEW_COUNT:
        raise ValueError(
            "The reference sheet is {}px wide; it needs at least {}px to split "
            "into {} views.".format(width, VIEW_COUNT, VIEW_COUNT)
        )

    cuts = sorted(int(round(min(max(float(g), 0.0), 1.0) * width)) for g in guides)

    boundaries = [0]
    for index, cut in enumerate(cuts):
        lowest = boundaries[-1] + 1
        highest = width - (len(cuts) - index)
        boundaries.append(max(lowest, min(highest, cut)))
    boundaries.append(width)
    return boundaries


class GeekatplayTurnaroundSplitter:
    """Splits one turnaround sheet into four separate view images."""

    @classmethod
    def INPUT_TYPES(cls):
        input_dir = folder_paths.get_input_directory()
        files = [
            name for name in os.listdir(input_dir)
            if os.path.isfile(os.path.join(input_dir, name))
        ]
        if hasattr(folder_paths, "filter_files_content_types"):
            files = folder_paths.filter_files_content_types(files, ["image"])

        guide = {
            "min": 0.0,
            "max": 1.0,
            "step": 0.001,
            "round": 0.0001,
            "display": "number",
        }
        return {
            "required": {
                "image": (sorted(files), {"image_upload": True}),
                "guide_1": ("FLOAT", dict(guide, default=0.25,
                                          tooltip="First cut, as a fraction of the sheet width.")),
                "guide_2": ("FLOAT", dict(guide, default=0.50,
                                          tooltip="Second cut, as a fraction of the sheet width.")),
                "guide_3": ("FLOAT", dict(guide, default=0.75,
                                          tooltip="Third cut, as a fraction of the sheet width.")),
            }
        }

    CATEGORY = CATEGORY
    DESCRIPTION = (
        "Loads a turnaround reference sheet and splits it into four view images "
        "along three guides you drag across the preview. Each view also reports "
        "its own width and height."
    )

    RETURN_TYPES = (
        "IMAGE", "INT", "INT",
        "IMAGE", "INT", "INT",
        "IMAGE", "INT", "INT",
        "IMAGE", "INT", "INT",
    )
    RETURN_NAMES = (
        "image_1", "width_1", "height_1",
        "image_2", "width_2", "height_2",
        "image_3", "width_3", "height_3",
        "image_4", "width_4", "height_4",
    )
    FUNCTION = "split"

    def split(self, image, guide_1, guide_2, guide_3):
        sheet = load_sheet(folder_paths.get_annotated_filepath(image))
        height = sheet.shape[1]
        width = sheet.shape[2]

        boundaries = guide_boundaries(width, (guide_1, guide_2, guide_3))

        results = []
        for index in range(VIEW_COUNT):
            left = boundaries[index]
            right = boundaries[index + 1]
            results.append(sheet[:, :, left:right, :].contiguous())
            results.append(right - left)
            results.append(height)
        return tuple(results)

    @classmethod
    def IS_CHANGED(cls, image, guide_1, guide_2, guide_3):
        path = folder_paths.get_annotated_filepath(image)
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            digest.update(handle.read())
        digest.update("{:.6f}|{:.6f}|{:.6f}".format(guide_1, guide_2, guide_3).encode("utf-8"))
        return digest.hexdigest()

    @classmethod
    def VALIDATE_INPUTS(cls, image, guide_1, guide_2, guide_3):
        if not folder_paths.exists_annotated_filepath(image):
            return "Invalid image file: {}".format(image)
        return True
