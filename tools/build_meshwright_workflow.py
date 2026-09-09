"""
Meshwright workflow builder - Geekatplay 3D Multiview
Geekatplay Studio - Vladimir Chopine  |  https://www.geekatplay.com

Takes the turnaround workflow and bolts a mesh cleanup stage onto the end.

The generated model leaves ComfyUI as a GLB, goes through Meshwright's repair
and reduction nodes, and comes back as a 3D file socket so the cleaned result
can be previewed and saved next to the original.

    python tools/build_meshwright_workflow.py
"""

import copy
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SOURCE = os.path.join(ROOT, "workflows", "3d_geekatplay_turnaround_multiview.json")
TARGET = os.path.join(ROOT, "workflows", "3d_geekatplay_turnaround_meshwright.json")

# The last node of the stock graph holding the finished, textured mesh.
FINAL_MESH_NODE = 260          # MeshSmoothNormals
PREVIEW_3D_TEMPLATE = 323      # Preview3DAdvanced, copied for its socket shape
PREVIEW_IMAGE_TEMPLATE = 262   # PreviewImage, same reason

# LiteGraph node modes.
ALWAYS = 0
BYPASS = 4

MESHWRIGHT_URL = "https://github.com/GeekatplayStudio/Meshwright"

NOTE_TEXT = (
    "## Mesh cleanup - Meshwright\n\n"
    "The model generated on the left is watertight only by luck. This stage sends it "
    "through **Meshwright**, which diagnoses the mesh, repairs holes, flipped normals "
    "and non-manifold edges, and reports a print-readiness score before and after.\n\n"
    "### This stage needs Meshwright installed\n\n"
    "Download: " + MESHWRIGHT_URL + "\n\n"
    "Install it, then run its `scripts/install_comfyui_nodes.py` to add the Meshwright "
    "nodes to ComfyUI. Without them the seven `Meshwright ...` nodes below will show as "
    "missing and the rest of the workflow still runs normally.\n\n"
    "### Reduce Mesh is bypassed on purpose\n\n"
    "Repair alone gives the best-looking result. Enable **Meshwright Reduce Mesh** "
    "(right-click, Mode, Always) only when you want a lighter mesh for a game engine.\n\n"
    "Reduction needs `fast_simplification` in ComfyUI's own Python. Without it the node "
    "returns the mesh untouched and reports 0%. Install it with:\n\n"
    "```\n"
    "python_embeded\\python.exe -m pip install fast_simplification pymeshfix\n"
    "```\n\n"
    "### Opening the result in the desktop app\n\n"
    "**Open in Meshwright** shows where the cleaned model was written and can reveal it "
    "on disk or start the app. Meshwright opens on an empty viewport, so load the shown "
    "file once it is up.\n\n"
    "Geekatplay Studio - Vladimir Chopine | https://www.geekatplay.com"
)


def node_by_id(graph, node_id):
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node
    raise KeyError("node {} is not in the workflow".format(node_id))


class Builder:
    """Small helper that hands out node and link ids and records the wiring."""

    def __init__(self, graph):
        self.graph = graph
        self.next_node = max(500, graph["last_node_id"] + 1)
        self.next_link = graph["last_link_id"] + 1

    def add(self, node_type, pos, size, inputs, outputs, widgets=None,
            title=None, mode=ALWAYS, properties=None):
        node = {
            "id": self.next_node,
            "type": node_type,
            "pos": list(pos),
            "size": list(size),
            "flags": {},
            "order": 0,
            "mode": mode,
            "inputs": copy.deepcopy(inputs),
            "outputs": copy.deepcopy(outputs),
            "properties": properties or {"Node name for S&R": node_type},
        }
        if title:
            node["title"] = title
        if widgets is not None:
            node["widgets_values"] = list(widgets)
        self.next_node += 1
        self.graph["nodes"].append(node)
        return node

    def link(self, origin, origin_slot, target, target_slot, link_type):
        link_id = self.next_link
        self.next_link += 1
        self.graph["links"].append(
            [link_id, origin["id"], origin_slot, target["id"], target_slot, link_type]
        )
        out = origin["outputs"][origin_slot]
        out["links"] = (out.get("links") or []) + [link_id]
        target["inputs"][target_slot]["link"] = link_id
        return link_id

    def link_from_existing(self, origin_node, origin_slot, target, target_slot, link_type):
        """Tap an output that already exists in the stock graph."""
        link_id = self.next_link
        self.next_link += 1
        self.graph["links"].append(
            [link_id, origin_node["id"], origin_slot, target["id"], target_slot, link_type]
        )
        out = origin_node["outputs"][origin_slot]
        out["links"] = (out.get("links") or []) + [link_id]
        target["inputs"][target_slot]["link"] = link_id
        return link_id

    def finish(self):
        self.graph["last_node_id"] = self.next_node - 1
        self.graph["last_link_id"] = self.next_link - 1


def widget_input(name, socket_type):
    """An input that started life as a widget, the way the editor writes it."""
    return {"name": name, "type": socket_type, "widget": {"name": name}, "link": None}


def plain_input(name, socket_type, optional=False):
    entry = {"name": name, "type": socket_type, "link": None}
    if optional:
        entry["shape"] = 7
    return entry


def out(name, socket_type):
    return {"name": name, "type": socket_type, "links": []}


def main():
    with open(SOURCE, "r", encoding="utf-8") as handle:
        graph = json.load(handle)

    final_mesh = node_by_id(graph, FINAL_MESH_NODE)
    preview3d_template = node_by_id(graph, PREVIEW_3D_TEMPLATE)
    preview_img_template = node_by_id(graph, PREVIEW_IMAGE_TEMPLATE)

    build = Builder(graph)

    # ---------------------------------------------------------------- out of ComfyUI
    to_file = build.add(
        "GeekatplayMeshToFile", (4400, 1030), (300, 130),
        [plain_input("mesh", "MESH")],
        [out("model_path", "STRING")],
        widgets=["meshwright/turnaround_raw", True],
        title="Mesh to File (to Meshwright)",
    )
    build.link_from_existing(final_mesh, 0, to_file, 0, "MESH")

    # ---------------------------------------------------------------- Meshwright
    load_model = build.add(
        "MeshwrightLoadModel", (4750, 1030), (330, 110),
        [widget_input("file_path", "STRING")],
        [out("mesh", "MESH"), out("diagnostics", "STRING")],
        widgets=[""],
    )
    build.link(to_file, 0, load_model, 0, "STRING")

    fix = build.add(
        "MeshwrightFixMesh", (5130, 1030), (330, 220),
        [plain_input("mesh", "MESH")],
        [out("mesh", "MESH"), out("report", "STRING"),
         out("summary", "STRING"), out("is_watertight", "BOOLEAN")],
        widgets=[True, False, 1.0, 0.0, 3, False],
    )
    build.link(load_model, 0, fix, 0, "MESH")

    reduce_mesh = build.add(
        "MeshwrightReduceMesh", (5510, 1030), (330, 170),
        [plain_input("mesh", "MESH")],
        [out("mesh", "MESH"), out("report", "STRING"), out("reduction_pct", "FLOAT")],
        widgets=["decimate", 0.5, 0, True],
        title="Meshwright Reduce Mesh (bypassed - enable to lighten)",
        mode=BYPASS,
    )
    build.link(fix, 0, reduce_mesh, 0, "MESH")

    # ---------------------------------------------------------------- before / after
    compare = build.add(
        "MeshwrightCompareMesh", (5890, 1030), (330, 110),
        [plain_input("mesh_before", "MESH"), plain_input("mesh_after", "MESH")],
        [out("report", "STRING"), out("score_before", "INT"),
         out("score_after", "INT"), out("comparison_image", "IMAGE")],
    )
    build.link(load_model, 0, compare, 0, "MESH")
    build.link(reduce_mesh, 0, compare, 1, "MESH")

    comparison_preview = build.add(
        "PreviewImage", (6270, 1030), (380, 350),
        [plain_input("images", "IMAGE")], [],
        properties=copy.deepcopy(preview_img_template.get("properties", {})),
        title="Before / After",
    )
    build.link(compare, 3, comparison_preview, 0, "IMAGE")

    fix_report = build.add(
        "MeshwrightTextDisplay", (5130, 1320), (330, 200),
        [plain_input("text", "STRING")],
        [out("text", "STRING")],
        title="Repair report",
    )
    build.link(fix, 1, fix_report, 0, "STRING")

    # ---------------------------------------------------------------- back to ComfyUI
    save_mesh = build.add(
        "MeshwrightSaveMesh", (5510, 1320), (330, 180),
        [plain_input("mesh", "MESH")],
        [out("file_path", "STRING"), out("solidity_status", "STRING")],
        widgets=["Meshwright/turnaround_fixed", "glb", "mm", True],
    )
    build.link(reduce_mesh, 0, save_mesh, 0, "MESH")

    to_model = build.add(
        "GeekatplayFileToModel3D", (5890, 1320), (330, 90),
        [widget_input("model_path", "STRING")],
        [out("model_3d", "FILE_3D")],
        widgets=[""],
        title="File to 3D Model (from Meshwright)",
    )
    build.link(save_mesh, 0, to_model, 0, "STRING")

    cleaned_preview = build.add(
        "Preview3DAdvanced",
        (6270, 1430), (380, 480),
        copy.deepcopy(preview3d_template["inputs"]),
        copy.deepcopy(preview3d_template["outputs"]),
        widgets=copy.deepcopy(preview3d_template.get("widgets_values")),
        properties=copy.deepcopy(preview3d_template.get("properties", {})),
        title="Cleaned model",
    )
    for entry in cleaned_preview["inputs"]:
        entry["link"] = None
    for entry in cleaned_preview["outputs"]:
        entry["links"] = []
    build.link(to_model, 0, cleaned_preview, 0, "FILE_3D")

    open_app = build.add(
        "GeekatplayOpenInMeshwright", (5890, 1500), (330, 230),
        [plain_input("model_path", "STRING"), widget_input("meshwright_folder", "STRING")],
        [out("model_path", "STRING")],
        widgets=[""],
    )
    build.link(save_mesh, 0, open_app, 0, "STRING")

    # ---------------------------------------------------------------- note + group
    note = build.add(
        "MarkdownNote", (4400, 1230), (620, 700), [], [],
        widgets=[NOTE_TEXT],
        title="Mesh cleanup - read me",
        properties={},
    )
    note["color"] = "#432"
    note["bgcolor"] = "#653"

    build.finish()

    graph["groups"].append({
        "id": max((g["id"] for g in graph["groups"]), default=0) + 1,
        "title": "Mesh Cleanup - Meshwright",
        "bounding": [4340, 940, 2360, 1010],
        "color": "#3f789e",
        "flags": {},
    })

    graph["id"] = "b7d31c95-4a62-4f18-8e05-91c7ad4e6b23"

    with open(TARGET, "w", encoding="utf-8") as handle:
        json.dump(graph, handle, indent=2, ensure_ascii=False)

    print("wrote {}".format(TARGET))
    print("  nodes: {}   links: {}".format(len(graph["nodes"]), len(graph["links"])))


if __name__ == "__main__":
    main()
