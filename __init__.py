"""
ComfyUI-3d-turnaround-splitter
Geekatplay Studio - Vladimir Chopine  |  https://www.geekatplay.com

Turns a single turnaround reference sheet into a finished 3D model.

  Turnaround Splitter   one sheet in, four views out, cut on guides you drag
                        over the preview inside the node.
  Fit & Resize          brings each view to an exact output size by extending
                        the canvas with matching background, never by
                        stretching or cropping.
  Meshwright bridge     hands the generated mesh to Meshwright for repair and
                        brings the cleaned result back.
"""

import os
import shutil

from .nodes import GeekatplayTurnaroundSplitter, GeekatplayFitResize
from .nodes.meshwright_bridge import (
    NODE_CLASS_MAPPINGS as BRIDGE_CLASS_MAPPINGS,
    NODE_DISPLAY_NAME_MAPPINGS as BRIDGE_DISPLAY_MAPPINGS,
    register_routes,
)

NODE_CLASS_MAPPINGS = {
    "GeekatplayTurnaroundSplitter": GeekatplayTurnaroundSplitter,
    "GeekatplayFitResize": GeekatplayFitResize,
}
NODE_CLASS_MAPPINGS.update(BRIDGE_CLASS_MAPPINGS)

NODE_DISPLAY_NAME_MAPPINGS = {
    "GeekatplayTurnaroundSplitter": "Turnaround Splitter (Geekatplay)",
    "GeekatplayFitResize": "Fit & Resize (Geekatplay)",
}
NODE_DISPLAY_NAME_MAPPINGS.update(BRIDGE_DISPLAY_MAPPINGS)

WEB_DIRECTORY = "web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]


def _install_demo_assets():
    """
    Put the bundled turnaround sheets in ComfyUI's input folder.

    The bundled workflows open with one of these sheets already selected, so
    copying them once on startup means the example runs on a fresh install
    instead of greeting the user with a missing-file error. Existing files of
    the same name are left alone, so a sheet the user has edited is never
    overwritten.
    """
    try:
        import folder_paths
    except ImportError:
        return

    asset_dir = os.path.join(os.path.dirname(__file__), "workflows", "assets")
    if not os.path.isdir(asset_dir):
        return

    input_dir = folder_paths.get_input_directory()
    for name in sorted(os.listdir(asset_dir)):
        source = os.path.join(asset_dir, name)
        if not os.path.isfile(source) or not name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue

        destination = os.path.join(input_dir, name)
        if os.path.exists(destination):
            continue

        try:
            os.makedirs(input_dir, exist_ok=True)
            shutil.copyfile(source, destination)
        except OSError as error:
            print("[Geekatplay] could not copy the demo sheet {}: {}".format(name, error))


_install_demo_assets()
register_routes()
