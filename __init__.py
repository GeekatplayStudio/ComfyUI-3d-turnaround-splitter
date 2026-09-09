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


def _install_demo_asset():
    """
    Put the demo turnaround sheet in ComfyUI's input folder.

    The bundled workflow opens with this sheet already selected, so copying it
    once on startup means the example runs on a fresh install instead of
    greeting the user with a missing-file error. An existing file of the same
    name is left alone.
    """
    try:
        import folder_paths
    except ImportError:
        return

    source = os.path.join(os.path.dirname(__file__), "workflows", "assets", "4-ref-caveman.png")
    if not os.path.isfile(source):
        return

    destination = os.path.join(folder_paths.get_input_directory(), os.path.basename(source))
    if os.path.exists(destination):
        return

    try:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copyfile(source, destination)
    except OSError as error:
        print("[Geekatplay] could not copy the demo turnaround sheet: {}".format(error))


_install_demo_asset()
register_routes()
