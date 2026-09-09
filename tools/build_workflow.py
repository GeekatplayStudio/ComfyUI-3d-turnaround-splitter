"""
Workflow builder - Geekatplay 3D Multiview
Geekatplay Studio - Vladimir Chopine  |  https://www.geekatplay.com

Rewrites the stock Pixal3D multiview workflow into the Geekatplay variant.

Everything downstream of the preprocessing block is left exactly as it was; only
the front of the graph changes:

  LoadImage + four ImageCropV2   ->   Turnaround Splitter + four Fit & Resize

Keeping this as a script rather than a hand-edited JSON means the variant can be
regenerated whenever the upstream template moves on.

    python tools/build_workflow.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SOURCE = os.path.join(ROOT, "3d_pixal3d_multi_views.json")
TARGET = os.path.join(ROOT, "workflows", "3d_geekatplay_turnaround_multiview.json")

LOADER_ID = 364
SPLITTER_ID = 400

# Each stock crop node, the view it feeds, and the Fit & Resize node replacing it.
# The order is the left-to-right order of the panels on the sheet.
REPLACEMENTS = [
    {"crop": 338, "fit": 401, "view": "front", "order": 13},
    {"crop": 341, "fit": 402, "view": "left", "order": 14},
    {"crop": 342, "fit": 403, "view": "back", "order": 15},
    {"crop": 345, "fit": 404, "view": "right", "order": 16},
]

OUTPUT_WIDTH = 512
OUTPUT_HEIGHT = 512

NOTE_ID = 374
NOTE_TEXT = (
    "This workflow builds a 3D model from a single turnaround reference sheet.\n\n"
    "**Turnaround Splitter (Geekatplay)** loads the sheet and cuts it into the four "
    "views. Drag the three coloured guides across the preview inside the node to set "
    "where the cuts fall. The guides are held as fractions of the sheet width, so they "
    "stay put when you swap in a sheet of a different size, and each view reports its "
    "own width and height.\n\n"
    "**Fit & Resize (Geekatplay)** brings each view to the exact size set in the node. "
    "It first extends the canvas with matching background until the proportions line up, "
    "then scales the whole thing down, so a tall narrow panel is never stretched or "
    "cropped to fit a square.\n\n"
    "Geekatplay Studio - Vladimir Chopine | https://www.geekatplay.com"
)


def node_by_id(graph, node_id):
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node
    raise KeyError("node {} is not in the workflow".format(node_id))


def build_splitter(loader):
    """The splitter stands where the loader stood, so the graph keeps its shape."""
    guides = [0.305, 0.48, 0.7735]  # the gaps between the four figures on the bundled demo sheet
    image_name = (loader.get("widgets_values") or ["", "image"])[0]

    outputs = []
    for index in range(1, 5):
        outputs.append({"name": "image_{}".format(index), "type": "IMAGE", "links": []})
        outputs.append({"name": "width_{}".format(index), "type": "INT", "links": None})
        outputs.append({"name": "height_{}".format(index), "type": "INT", "links": None})

    return {
        "id": SPLITTER_ID,
        "type": "GeekatplayTurnaroundSplitter",
        "pos": list(loader["pos"]),
        "size": [520, 640],
        "flags": {},
        "order": loader.get("order", 9),
        "mode": 0,
        "inputs": [],
        "outputs": outputs,
        "title": "Turnaround Splitter (Geekatplay)",
        "properties": {"Node name for S&R": "GeekatplayTurnaroundSplitter"},
        # The frontend appends its own upload button to the image picker, which
        # shifts every following index. The named form is what the node reads back.
        "widgets_values": [image_name] + guides + ["image"],
        "widgets_values_named": {
            "image": image_name,
            "guide_1": guides[0],
            "guide_2": guides[1],
            "guide_3": guides[2],
            "upload": "image",
        },
    }


def build_fit(crop, spec):
    """A Fit & Resize node inheriting the crop node's position and outgoing links."""
    downstream = list(crop["outputs"][0].get("links") or [])
    return {
        "id": spec["fit"],
        "type": "GeekatplayFitResize",
        "pos": list(crop["pos"]),
        "size": [270, 200],
        "flags": {},
        "order": spec["order"],
        "mode": 0,
        "inputs": [{"name": "image", "type": "IMAGE", "link": None}],
        "outputs": [
            {"name": "image", "type": "IMAGE", "links": downstream},
            {"name": "width", "type": "INT", "links": None},
            {"name": "height", "type": "INT", "links": None},
        ],
        "title": "Fit & Resize ({})".format(spec["view"]),
        "properties": {"Node name for S&R": "GeekatplayFitResize"},
        "widgets_values": [
            OUTPUT_WIDTH,
            OUTPUT_HEIGHT,
            "auto (sample edges)",
            "#000000",
            "center",
            "lanczos",
        ],
        "widgets_values_named": {
            "width": OUTPUT_WIDTH,
            "height": OUTPUT_HEIGHT,
            "background_source": "auto (sample edges)",
            "background_color": "#000000",
            "alignment": "center",
            "resize_method": "lanczos",
        },
    }


def main():
    with open(SOURCE, "r", encoding="utf-8") as handle:
        graph = json.load(handle)

    loader = node_by_id(graph, LOADER_ID)
    crops = {spec["crop"]: node_by_id(graph, spec["crop"]) for spec in REPLACEMENTS}

    splitter = build_splitter(loader)
    fits = [build_fit(crops[spec["crop"]], spec) for spec in REPLACEMENTS]

    # --- swap the nodes in place, keeping list order readable -----------------
    replaced = {LOADER_ID: splitter}
    for spec, fit in zip(REPLACEMENTS, fits):
        replaced[spec["crop"]] = fit
    graph["nodes"] = [replaced.get(node["id"], node) for node in graph["nodes"]]

    # --- drop the loader-to-crop links, they are re-made below ----------------
    retired = set()
    for crop in crops.values():
        link_id = crop["inputs"][0].get("link")
        if link_id is not None:
            retired.add(link_id)
    graph["links"] = [link for link in graph["links"] if link[0] not in retired]

    # --- point every downstream link at its Fit & Resize node -----------------
    origin_for_crop = {spec["crop"]: spec["fit"] for spec in REPLACEMENTS}
    for link in graph["links"]:
        if link[1] in origin_for_crop:
            link[1] = origin_for_crop[link[1]]
            link[2] = 0  # the image output is the first slot on the new node

    # --- wire splitter -> fit ------------------------------------------------
    next_link = graph["last_link_id"]
    for index, fit in enumerate(fits):
        next_link += 1
        image_slot = index * 3  # image_1, image_2, ... skipping width/height
        graph["links"].append([next_link, SPLITTER_ID, image_slot, fit["id"], 0, "IMAGE"])
        splitter["outputs"][image_slot]["links"] = [next_link]
        fit["inputs"][0]["link"] = next_link

    graph["last_link_id"] = next_link
    graph["last_node_id"] = max(graph["last_node_id"], SPLITTER_ID, *[f["id"] for f in fits])

    # --- refresh the explanatory note ----------------------------------------
    node_by_id(graph, NOTE_ID)["widgets_values"] = [NOTE_TEXT]

    graph["id"] = "8f2c41d6-5b7a-4e93-9c10-2ad7e6b4f085"

    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8") as handle:
        json.dump(graph, handle, indent=2, ensure_ascii=False)

    print("wrote {}".format(TARGET))
    print("  nodes: {}   links: {}".format(len(graph["nodes"]), len(graph["links"])))


if __name__ == "__main__":
    main()
