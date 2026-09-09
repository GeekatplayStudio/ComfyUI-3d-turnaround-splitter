"""
Meshwright bridge - Geekatplay 3D Multiview
Geekatplay Studio - Vladimir Chopine  |  https://www.geekatplay.com

Connects ComfyUI's own 3D pipeline to Meshwright, the desktop mesh repair tool.

Why a bridge is needed at all: ComfyUI's mesh sockets and Meshwright's mesh
sockets are both named MESH, so the editor is happy to let you draw a link
between them - but they carry different payloads. ComfyUI hands over batched
torch tensors; Meshwright expects a trimesh object. Wired directly, the graph
looks correct and then fails the moment it runs.

These nodes route around that through a file on disk, which both sides already
understand and which the desktop app can open as well:

    ComfyUI mesh -> Mesh to File (Meshwright) -> Meshwright Load 3D Model
    Meshwright Save 3D Mesh -> File to 3D Model -> Preview 3D / Save 3D

Meshwright is a separate download:  https://github.com/GeekatplayStudio/Meshwright
"""

import json
import os
import subprocess
import sys

import folder_paths

try:
    from .branding import CATEGORY
except ImportError:  # pragma: no cover
    from branding import CATEGORY


BRIDGE_CATEGORY = CATEGORY + "/Meshwright"
MESHWRIGHT_URL = "https://github.com/GeekatplayStudio/Meshwright"

# Every 3D file socket in ComfyUI core, so the output drops straight into
# Preview 3D, Save 3D (Advanced) or Get 3D Components.
FILE_3D = "FILE_3D"


def _output_path(filename_prefix, extension, overwrite):
    """Resolve a prefix like "meshwright/model" to a real path under output/."""
    output_dir = folder_paths.get_output_directory()
    prefix = filename_prefix.strip().replace("\\", "/").strip("/") or "meshwright/model"

    sub_dir = os.path.dirname(prefix)
    base = os.path.basename(prefix) or "model"
    target_dir = os.path.join(output_dir, sub_dir) if sub_dir else output_dir
    os.makedirs(target_dir, exist_ok=True)

    path = os.path.join(target_dir, base + extension)
    if overwrite:
        return path

    counter = 1
    while os.path.exists(path):
        path = os.path.join(target_dir, "{}_{:03d}{}".format(base, counter, extension))
        counter += 1
    return path


def locate_meshwright(hint=""):
    """
    Find a Meshwright installation.

    Checked in order: the path typed into the node, the MESHWRIGHT_HOME
    environment variable, and the meshwright_config.json that Meshwright's own
    ComfyUI installer leaves next to its nodes.
    """
    candidates = []

    if hint and hint.strip():
        candidates.append(hint.strip().strip('"').strip("'"))

    env_home = os.environ.get("MESHWRIGHT_HOME", "")
    if env_home:
        candidates.append(env_home)

    # Meshwright's installer writes this file beside its node package.
    try:
        for entry in os.listdir(folder_paths.get_folder_paths("custom_nodes")[0]):
            config = os.path.join(
                folder_paths.get_folder_paths("custom_nodes")[0], entry, "meshwright_config.json"
            )
            if os.path.isfile(config):
                with open(config, "r", encoding="utf-8") as handle:
                    root = json.load(handle).get("meshwright_root", "")
                if root:
                    candidates.append(root)
    except Exception:
        pass

    for candidate in candidates:
        if candidate and os.path.isfile(os.path.join(candidate, "app.py")):
            return os.path.abspath(candidate)
    return None


class GeekatplayMeshToFile:
    """Writes a ComfyUI mesh to a GLB on disk and reports where it went."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mesh": ("MESH", {"tooltip": "Mesh from the ComfyUI 3D pipeline."}),
                "filename_prefix": ("STRING", {
                    "default": "meshwright/turnaround",
                    "tooltip": "Written under ComfyUI's output folder.",
                }),
                "overwrite": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Keep one stable path so the desktop app always opens the newest result. "
                               "Turn off to number every run instead.",
                }),
            }
        }

    CATEGORY = BRIDGE_CATEGORY
    DESCRIPTION = (
        "Saves a ComfyUI mesh as a GLB and returns its path, ready for Meshwright's "
        "Load 3D Model node. Needed because both packs use a socket named MESH but "
        "carry different data inside it."
    )

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("model_path",)
    FUNCTION = "write"

    def write(self, mesh, filename_prefix, overwrite):
        # Imported here so the pack still loads on a ComfyUI without the 3D extras.
        from comfy_extras.nodes_save_3d import mesh_item_to_glb_bytes

        if getattr(mesh, "vertices", None) is None:
            raise ValueError("Mesh to File: the input is not a ComfyUI mesh.")

        glb = mesh_item_to_glb_bytes(mesh, 0)
        if glb is None:
            raise ValueError("Mesh to File: the mesh is empty (no vertices or faces).")

        path = _output_path(filename_prefix, ".glb", overwrite)
        with open(path, "wb") as handle:
            handle.write(glb)
        return (path,)


class GeekatplayFileToModel3D:
    """Turns a path on disk back into a 3D file socket."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_path": ("STRING", {
                    "default": "",
                    "tooltip": "Path to a 3D file, e.g. the one Meshwright's Save 3D Mesh reports.",
                }),
            }
        }

    CATEGORY = BRIDGE_CATEGORY
    DESCRIPTION = (
        "Wraps a 3D file on disk as a model socket, so a mesh that came back from "
        "Meshwright can go into Preview 3D, Save 3D (Advanced) or Get 3D Components."
    )

    RETURN_TYPES = (FILE_3D,)
    RETURN_NAMES = ("model_3d",)
    FUNCTION = "wrap"

    def wrap(self, model_path):
        from comfy_api.latest import Types

        path = str(model_path).strip().strip('"').strip("'")
        if not path:
            raise ValueError("File to 3D Model: no path given.")
        if not os.path.isfile(path):
            raise FileNotFoundError("File to 3D Model: nothing at {}".format(path))
        return (Types.File3D(path),)

    @classmethod
    def IS_CHANGED(cls, model_path):
        path = str(model_path).strip().strip('"').strip("'")
        try:
            return str(os.path.getmtime(path))
        except OSError:
            return float("nan")


class GeekatplayOpenInMeshwright:
    """Shows where the model landed and offers to open it in the desktop app."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_path": ("STRING", {
                    "forceInput": True,
                    "tooltip": "Path of the model to hand over to Meshwright.",
                }),
            },
            "optional": {
                "meshwright_folder": ("STRING", {
                    "default": "",
                    "tooltip": "Where Meshwright is installed. Leave empty to search MESHWRIGHT_HOME "
                               "and the config its ComfyUI installer writes.",
                }),
            },
        }

    CATEGORY = BRIDGE_CATEGORY
    DESCRIPTION = (
        "Reports the finished model's path and adds buttons to reveal it on disk or "
        "launch Meshwright. Meshwright opens with an empty viewport, so load the shown "
        "file once it is up. Download: " + MESHWRIGHT_URL
    )

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("model_path",)
    FUNCTION = "announce"
    OUTPUT_NODE = True

    def announce(self, model_path, meshwright_folder=""):
        path = str(model_path).strip().strip('"').strip("'")
        exists = os.path.isfile(path)
        root = locate_meshwright(meshwright_folder)

        return {
            "ui": {
                "meshwright": [{
                    "model_path": path,
                    "exists": exists,
                    "meshwright_root": root or "",
                    "download_url": MESHWRIGHT_URL,
                }]
            },
            "result": (path,),
        }


# ---------------------------------------------------------------- server route

def _reveal(path):
    """Open the host file manager with the file selected."""
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])


def _launch(root):
    """Start the Meshwright desktop app from its own interpreter."""
    venv_python = os.path.join(root, ".venv", "Scripts", "python.exe")
    if not os.path.isfile(venv_python):
        venv_python = os.path.join(root, ".venv", "bin", "python")
    if not os.path.isfile(venv_python):
        raise FileNotFoundError(
            "Meshwright is present at {} but has not been installed yet - "
            "run its install script first.".format(root)
        )
    subprocess.Popen([venv_python, os.path.join(root, "app.py")], cwd=root)


def register_routes():
    """Expose the buttons' actions. A no-op when ComfyUI's server is not running."""
    try:
        from aiohttp import web
        from server import PromptServer
    except ImportError:  # pragma: no cover - importable outside ComfyUI
        return

    instance = getattr(PromptServer, "instance", None)
    if instance is None:  # pragma: no cover
        return

    @instance.routes.post("/geekatplay/meshwright/open")
    async def _open(request):
        payload = await request.json()
        action = payload.get("action", "reveal")
        path = str(payload.get("model_path", "")).strip()

        try:
            if action == "reveal":
                if not os.path.isfile(path):
                    return web.json_response({"ok": False, "error": "No file at {}".format(path)})
                # Only ever reveal something this ComfyUI produced.
                output_root = os.path.abspath(folder_paths.get_output_directory())
                if os.path.commonpath([output_root, os.path.abspath(path)]) != output_root:
                    return web.json_response(
                        {"ok": False, "error": "Only files in the output folder can be revealed."}
                    )
                _reveal(path)
                return web.json_response({"ok": True, "message": "Shown in file manager."})

            if action == "launch":
                root = locate_meshwright(payload.get("meshwright_folder", ""))
                if not root:
                    return web.json_response({
                        "ok": False,
                        "error": "Meshwright was not found. Set its folder on the node, "
                                 "or install it from " + MESHWRIGHT_URL,
                    })
                _launch(root)
                return web.json_response({"ok": True, "message": "Meshwright is starting."})

            return web.json_response({"ok": False, "error": "Unknown action."})
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)})


NODE_CLASS_MAPPINGS = {
    "GeekatplayMeshToFile": GeekatplayMeshToFile,
    "GeekatplayFileToModel3D": GeekatplayFileToModel3D,
    "GeekatplayOpenInMeshwright": GeekatplayOpenInMeshwright,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GeekatplayMeshToFile": "Mesh to File (Meshwright bridge)",
    "GeekatplayFileToModel3D": "File to 3D Model (Meshwright bridge)",
    "GeekatplayOpenInMeshwright": "Open in Meshwright",
}
