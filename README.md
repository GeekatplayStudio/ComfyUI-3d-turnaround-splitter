# ComfyUI 3D Turnaround Splitter

**Geekatplay Studio — Vladimir Chopine** · [geekatplay.com](https://www.geekatplay.com)

Turn a single character turnaround sheet into a finished, clean 3D model.

![The splitter with its three guides over a turnaround sheet](docs/images/splitter-guides.png)

Load one turnaround sheet, drag three lines to say where the views split, and
run. No cropping by hand, no re-typing pixel offsets when you change reference.

---

## Contents

- [What this is based on](#what-this-is-based-on)
- [What this pack improves](#what-this-pack-improves)
- [Installation, step by step](#installation-step-by-step)
- [Running the workflow](#running-the-workflow)
- [Turnaround Splitter](#turnaround-splitter)
- [Fit & Resize](#fit--resize)
- [Mesh cleanup with Meshwright](#mesh-cleanup-with-meshwright)
- [Getting better hands and anatomy](#getting-better-hands-and-anatomy)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

---

## What this is based on

This pack is built on the official ComfyUI template **"Pixal3D: Multi Views to
3D"** (`3d_pixal3d_multi_views`), which ships in the
[Comfy-Org/workflow_templates](https://github.com/Comfy-Org/workflow_templates)
package.

| | |
| --- | --- |
| Upstream template | `3d_pixal3d_multi_views` — *Pixal3D: Multi Views to 3D* |
| Template package | `comfyui_workflow_templates` 0.11.57 |
| Minimum ComfyUI | 0.35.0 |
| Model family | Pixal3D Multi-View (Trellis2 lineage) |

The unmodified original is kept in this repo as
[`workflows/3d_pixal3d_multi_views.json`](workflows/3d_pixal3d_multi_views.json)
so you can diff it against our version and see exactly what changed.

**Everything downstream of the image preparation is untouched.** Background
removal, conditioning, the three samplers, mesh generation, UV unwrapping and
texture baking are the upstream graph, node for node. We only replaced the front
of the pipeline and added an optional tail.

---

## What this pack improves

### 1. One splitter instead of a loader and four crop nodes

The upstream template asks you to load an image and then crop it four times with
`ImageCropV2`, typing pixel offsets into each. Those offsets are **absolute
pixels baked into the workflow**, and they belong to whatever sheet the template
author used.

We hit this immediately: the shipped template carried crop offsets running out
to `x = 4728`, sized for a 6336 × 2688 sheet. Our reference sheet is 1774 × 887,
so three of the four crops were reaching **past the right edge of the image**
and returning nothing useful. Loading any sheet of a different size silently
breaks the template.

The **Turnaround Splitter** replaces all five nodes. It stores cuts as
*fractions* of the sheet width, so swapping in a sheet of a different size keeps
the cuts where they look right instead of stranding them off-canvas. And you
place them by dragging lines over a live preview rather than guessing numbers.

### 2. Views are fitted, not stretched or cropped

![Plain resize and crop against Fit and Resize](docs/images/fit-resize.png)

`ImageCropV2` resizes each crop straight to the target size. A turnaround panel
is a tall, narrow strip, so a plain resize to 512 × 512 **squashes the
character** — and cropping to a square throws away the head and the feet.

**Fit & Resize** extends the canvas with background-coloured margin until the
proportions match, *then* scales. The subject keeps its shape and nothing is cut
off. The margin colour is sampled from the image borders automatically.

### 3. Per-view dimensions are reported

The four panels of a real sheet are rarely equal. On the bundled demo sheet they
come out **541, 311, 520 and 402** pixels wide. The splitter reports each view's
own width and height instead of assuming a clean quarter each.

### 4. An optional mesh cleanup stage

The upstream template ends at a generated mesh, which is rarely watertight. The
second workflow adds a repair stage built on **Meshwright**, our desktop mesh
tool, with a bridge that works around a real incompatibility between the two
mesh formats (see [below](#mesh-cleanup-with-meshwright)).

### 5. Demo assets included and preloaded

Two turnaround sheets ship with the pack and are copied into your ComfyUI
`input` folder on first start, so the workflows run immediately instead of
opening with a missing-file error.

### Summary

| | Upstream template | This pack |
| --- | --- | --- |
| Splitting a sheet | 4 × `ImageCropV2`, absolute pixel offsets | 1 splitter, draggable guides, stored as fractions |
| Changing reference size | offsets break silently | cuts scale automatically |
| Placing the cuts | type numbers, run, check, repeat | drag lines on a live preview |
| Fitting to model size | stretches or crops | pads, then scales |
| Per-view dimensions | not available | reported per view |
| Mesh repair | none | optional Meshwright stage |
| Demo asset | download separately | bundled and preloaded |

---

## Installation, step by step

### Before you start

You need:

- **ComfyUI 0.35.0 or newer.** Check under the ComfyUI logo, or in
  `ComfyUI/comfyui_version.py`. Older versions do not have the Pixal3D nodes
  this workflow needs.
- **About 9 GB of free disk space** for the models.
- A GPU with **12 GB VRAM or more** is comfortable. Less will work but slowly.

No extra Python packages are required. The nodes use `torch`, `numpy` and
`Pillow`, all of which ComfyUI already installs.

---

### Step 1 — Find your ComfyUI folder

You need the folder that contains `main.py` and a `custom_nodes` subfolder.

| Installation type | Typical location |
| --- | --- |
| Windows portable (`.7z` release) | `C:\ComfyUI_windows_portable\ComfyUI\` |
| Manual `git clone` | wherever you cloned it, e.g. `C:\dev\ComfyUI\` |
| ComfyUI Desktop (Windows) | `%APPDATA%\ComfyUI\` — check **Settings → About** for the exact path |
| ComfyUI Desktop (macOS) | `~/Library/Application Support/ComfyUI/` |
| Linux | wherever you cloned it, e.g. `~/ComfyUI/` |

Open that folder. You should see `main.py`, `models/` and `custom_nodes/`. If
you don't, you are one level too high or too low.

---

### Step 2 — Install the nodes

Pick **one** of these three methods.

#### Method A — Git (recommended, easy to update)

Open a terminal **inside the `custom_nodes` folder** and run:

```bash
git clone https://github.com/GeekatplayStudio/ComfyUI-3d-turnaround-splitter.git
```

On Windows, the quickest way to get a terminal in the right place is to open
`custom_nodes` in File Explorer, type `cmd` in the address bar, and press Enter.

To update later:

```bash
cd ComfyUI-3d-turnaround-splitter
git pull
```

#### Method B — Download a ZIP (no Git required)

1. Go to <https://github.com/GeekatplayStudio/ComfyUI-3d-turnaround-splitter>
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP
4. Move the extracted folder into `ComfyUI/custom_nodes/`
5. **Rename it** so the `-main` suffix is gone — GitHub names the folder
   `ComfyUI-3d-turnaround-splitter-main`, and it should be
   `ComfyUI-3d-turnaround-splitter`

#### Method C — ComfyUI Manager

If you have ComfyUI Manager installed, open **Manager → Install via Git URL**
and paste:

```
https://github.com/GeekatplayStudio/ComfyUI-3d-turnaround-splitter.git
```

#### Check the folder is right

Whichever method you used, you should now have:

```
ComfyUI/
└── custom_nodes/
    └── ComfyUI-3d-turnaround-splitter/
        ├── __init__.py          <-- this file must be directly inside
        ├── nodes/
        ├── web/
        └── workflows/
```

If you see a **doubled folder** —
`ComfyUI-3d-turnaround-splitter/ComfyUI-3d-turnaround-splitter/__init__.py` —
move the inner folder up one level. This is the single most common install
mistake.

---

### Step 3 — Restart ComfyUI

Fully close and restart it. Reloading the browser tab is **not** enough; custom
nodes are only loaded when the server starts.

Watch the console as it starts. You should see no errors mentioning
`ComfyUI-3d-turnaround-splitter`.

---

### Step 4 — Confirm the nodes are there

In the ComfyUI canvas, double-click on empty space and type `turnaround`. You
should see:

- **Turnaround Splitter (Geekatplay)**
- **Fit & Resize (Geekatplay)**

They also live in the right-click **Add Node** menu under
**Geekatplay Studio → 3D Multiview**.

If nothing appears, jump to [Troubleshooting](#troubleshooting).

---

### Step 5 — Download the models

These are the models the **upstream Pixal3D template** needs. They are not part
of this pack, and this is by far the longest step — about **8.7 GB** total.

Create the folders if they don't exist, and put each file in the folder shown:

| File | Goes in | Size |
| --- | --- | --- |
| [`pixal3d_multiview_int8_convrot.safetensors`](https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/diffusion_models/pixal3d_multiview_int8_convrot.safetensors) | `models/diffusion_models/` | 5.20 GB |
| [`trellis_2_shape_vae_bf16.safetensors`](https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/vae/trellis_2_shape_vae_bf16.safetensors) | `models/vae/` | 1.02 GB |
| [`trellis_2_texture_vae_bf16.safetensors`](https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/vae/trellis_2_texture_vae_bf16.safetensors) | `models/vae/` | 0.88 GB |
| [`dino_v3_L_naf_fp32.safetensors`](https://huggingface.co/Comfy-Org/Pixal3D/resolve/main/clip_vision/dino_v3_L_naf_fp32.safetensors) | `models/clip_vision/` | 1.13 GB |
| [`birefnet.safetensors`](https://huggingface.co/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors) | `models/background_removal/` | 0.41 GB |

The finished layout:

```
ComfyUI/
└── models/
    ├── diffusion_models/
    │   └── pixal3d_multiview_int8_convrot.safetensors
    ├── vae/
    │   ├── trellis_2_shape_vae_bf16.safetensors
    │   └── trellis_2_texture_vae_bf16.safetensors
    ├── clip_vision/
    │   └── dino_v3_L_naf_fp32.safetensors
    └── background_removal/
        └── birefnet.safetensors
```

> **Note on the CLIP Vision file.** It must be the **`_naf_`** build. A plain
> DINOv3 checkpoint is missing the NAF upsampler weights, and the shape and
> texture stages will fail with a channel-count error part way through the run.

`models/background_removal/` usually does not exist yet — create it.

Restart ComfyUI once more after adding models so it picks them up.

---

### Step 6 — Load a workflow

The workflows are in the pack you just installed, at
`ComfyUI/custom_nodes/ComfyUI-3d-turnaround-splitter/workflows/`.

Drag the `.json` file straight onto the ComfyUI canvas, or use
**Workflow → Open** and browse to it.

| File | What it does |
| --- | --- |
| `3d_geekatplay_turnaround_multiview.json` | **Start here.** Sheet → four views → textured 3D model. |
| `3d_geekatplay_turnaround_meshwright.json` | The same, plus the mesh repair stage. Needs Meshwright. |
| `3d_pixal3d_multi_views.json` | The unmodified upstream original, for reference. |

The demo sheet is already selected in the splitter, and the guides are already
placed, so you can press Run straight away.

---

## Running the workflow

1. **Pick your sheet.** In the Turnaround Splitter, use the `image` picker, or
   the upload button to bring in your own.
2. **Place the guides.** Drag the three coloured lines into the gaps between the
   four views. The panels tint and number themselves as you drag, and each guide
   shows its pixel position. **Even quarters** snaps them back to 25/50/75%.
3. **Check the view order.** Outputs map left-to-right: `image_1` → front,
   `image_2` → left, `image_3` → back, `image_4` → right. If your sheet is in a
   different order, rewire the four Fit & Resize nodes — the splitter does not
   care what is on each panel.
4. **Run.** The first run loads about 9 GB of models and will take a while.
   Later runs reuse them.

---

## Turnaround Splitter

Loads one turnaround sheet and cuts it into four view images.

The sheet is drawn inside the node with three coloured guides over it. Drag a
guide to move a cut. The four panels are tinted and numbered, and each guide
shows its position in pixels, so you can see what each output will contain
before running anything.

Guides are stored as **fractions of the sheet width**, so they survive swapping
in a sheet of a different size.

| Widget | Meaning |
| --- | --- |
| `image` | The turnaround sheet, picked or uploaded like any other image input. |
| `guide_1` `guide_2` `guide_3` | Cut positions, `0.0`–`1.0` across the sheet. Set by dragging, or typed for an exact value. |

**Outputs** — for each of the four views, the image and its measured size:

```
image_1  width_1  height_1
image_2  width_2  height_2
image_3  width_3  height_3
image_4  width_4  height_4
```

Guides are sorted before the cut, so they can be dragged past one another
without scrambling the output order, and every slice is kept at least one pixel
wide.

**Buttons** — **Even quarters** resets the guides to 25/50/75%. **Reload**
re-reads the sheet from disk, for when the file has been replaced.

---

## Fit & Resize

Brings an image to an exact size **without stretching or cropping it**:

1. **Extend** the canvas with background-coloured margin until the image matches
   the requested proportions.
2. **Scale** the whole padded canvas to the exact output size.

A `1024 × 400` strip headed for `512 × 512` first becomes `1024 × 1024`, then
scales down. Nothing is squashed and nothing is cut off.

| Widget | Meaning |
| --- | --- |
| `width` `height` | Exact size of the image leaving the node. |
| `background_source` | `auto (sample edges)` reads the margin colour from the image borders; `custom color` uses the field below. |
| `background_color` | Hex colour for the margin, e.g. `#000000`. Used only in `custom color` mode. |
| `alignment` | Where the original sits once the canvas grows — `center`, or pushed to one side (`start` / `end`). |
| `resize_method` | `lanczos`, `bicubic`, `bilinear`, `area` or `nearest-exact`. |

**Outputs:** `image`, plus the `width` and `height` it was rendered at.

`auto` takes the **median** colour of the four borders rather than the average,
so a subject running up against one edge barely tints the margin.

---

## Mesh cleanup with Meshwright

![How the two workflows fit together](docs/images/pipeline.png)

A mesh straight out of a generative 3D model is rarely watertight. **Meshwright**
is Geekatplay Studio's desktop tool for exactly that — it diagnoses a mesh,
repairs holes, flipped normals and non-manifold edges, and scores how ready the
result is to print.

**Download: <https://github.com/GeekatplayStudio/Meshwright>**

### Installing the Meshwright side

1. Clone or download Meshwright.
2. Run its `install.bat` (Windows) or `install.ps1`. This builds its own `.venv`.
3. Run `python scripts/install_comfyui_nodes.py` from the Meshwright folder to
   copy its nodes into ComfyUI and write the config that links them back.
4. Restart ComfyUI.

Without this, the six `Meshwright ...` nodes in the cleanup workflow show as
missing. The rest of the workflow still runs normally.

### Why this pack ships a bridge

ComfyUI's mesh sockets and Meshwright's mesh sockets are **both named `MESH`**,
so the editor is happy to let you draw a link straight between them. They do not
carry the same thing — ComfyUI passes batched torch tensors, Meshwright expects a
`trimesh` object. Wired directly, the graph looks correct and then fails the
moment you press Run:

```
TypeError: Unsupported 3D mesh data type:
           <class 'comfy_api.latest._util.geometry_types.MESH'>
```

The two bridge nodes route around this through a file on disk, which both sides
already understand and which the desktop app can open too:

```
ComfyUI mesh  ->  Mesh to File (bridge)  ->  Meshwright Load 3D Model
                        ...repair, reduce, compare...
Meshwright Save 3D Mesh  ->  File to 3D Model (bridge)  ->  Preview 3D / Save 3D
```

### Opening a result in the desktop app

**Open in Meshwright** shows where the cleaned model was written and offers to
reveal it on disk or start the app. It finds Meshwright through the
`MESHWRIGHT_HOME` environment variable, the config its installer writes, or a
folder you type into the node.

Meshwright opens on an empty viewport — it takes no file argument — so the node
shows the full path with a one-click copy.

### Two things to know before running it

**Reduce Mesh ships bypassed.** Repair alone gives the best-looking result;
decimation is there for when you want a lighter mesh for a game engine. Enable
it with right-click → **Mode** → **Always**.

**Reduction needs one extra library.** Meshwright's heavy engines live in its own
virtual environment, and ComfyUI cannot borrow them — the two run different
Python versions, so the compiled modules will not load across. Without
`fast_simplification` in ComfyUI's own Python, Reduce Mesh returns the mesh
untouched and reports `0%` **without raising an error**. Install it where
ComfyUI can see it:

```
# Windows portable
python_embeded\python.exe -m pip install fast_simplification pymeshfix

# manual install, with your ComfyUI environment active
pip install fast_simplification pymeshfix
```

Repair itself works without them, falling back to Meshwright's own cleanup.

---

## Getting better hands and anatomy

If your model comes out with extra fingers or two thumbs on a hand, this is
worth reading. It is a known characteristic of how the Pixal3D multi-view
conditioning fuses views, not something wrong with your reference sheet.

**What happens.** The conditioning back-projects every view onto every voxel and
averages them at exactly `1/N`, with **no occlusion test** — a voxel samples the
back view's image whether or not it is visible from behind. For a hand, the front
view says "thumb on this side" and the back view says "thumb on the other side",
and the average can resolve as a hand with both. There is no per-view weight
exposed anywhere to bias this.

**What actually helps:**

1. **Raise the Fit & Resize size to 1024 × 1024.** This is the biggest and
   cheapest win. The downstream crop node upscales to 1024 anyway, so leaving
   Fit & Resize at 512 throws away half the detail and then re-inflates it. On
   the demo sheet that is the difference between roughly **19 px and 38 px of
   real detail per finger**. Source panels are ~887 px tall, so 1024 is the
   sweet spot — higher just costs time.
2. **Disconnect the `back` view** in the conditioning node when hands matter
   more than the back surface. The view inputs are optional and the node
   re-weights automatically (three views become `1/3` each). Keep `front`
   connected — it defines the mesh's pose.
3. **Give the hands room on the sheet.** Hands held away from the body, in a
   consistent pose across all four panels, leave the averaging far less to
   disagree about.

**What will not help:** Meshwright repairs *topology*, not anatomy — a
six-fingered hand that is watertight stays six-fingered. CFG and RescaleCFG are
global strength, not per-view. Feeding the same image into two view inputs would
place it at the wrong camera angle and make things worse.

---

## Troubleshooting

**The nodes don't appear after restarting.**
Check for a doubled folder (see [Step 2](#check-the-folder-is-right)). Then read
the ComfyUI console from the top — a Python error during import is printed there
and the node is skipped silently in the UI.

**The splitter shows "no reference sheet loaded".**
The image is not in `ComfyUI/input`. Use the upload button on the node, or copy
the file there and press **Reload**.

**The splitter preview is blank but the sheet is selected.**
Hard-refresh the browser (`Ctrl+Shift+R`). The node's JavaScript is cached by
the browser and a stale copy can survive a server restart.

**"Value not in list" or every widget reset to defaults after reloading a saved
workflow.**
Hard-refresh as above. If it persists, re-select the image in the picker and
save again.

**Red node: `Pixal3DMultiViewConditioning` or another `Pixal3D`/`Trellis2` node
is missing.**
Your ComfyUI is older than 0.35.0. Update it.

**Channel-count error during the shape or texture stage.**
Wrong CLIP Vision file — it must be the `_naf_` build. See
[Step 5](#step-5--download-the-models).

**Out of memory.**
Lower the `Texture Resolution` node from 2048 to 1024, and start ComfyUI with
`--lowvram`.

**The four views come out in the wrong order.**
Rewire the Fit & Resize nodes. `image_1`..`image_4` are simply left-to-right on
your sheet; which is "front" depends on how the sheet was drawn.

**Guides won't drag.**
Grab the coloured tab in the middle of the line, or the line itself. If the
whole node moves instead, you missed the line — the grab zone is about 10 px
wide.

---

## Node reference

| Node | In | Out |
| --- | --- | --- |
| **Turnaround Splitter** | a turnaround sheet | 4 × (image, width, height) |
| **Fit & Resize** | image | image, width, height |
| **Mesh to File** (bridge) | ComfyUI mesh | path to a GLB |
| **File to 3D Model** (bridge) | path | 3D model socket |
| **Open in Meshwright** | path | path, plus the buttons |

All appear under **Geekatplay Studio → 3D Multiview**.

---

## Development

The workflows and the figures in this README are generated, not hand-edited, so
they cannot drift away from the code:

```bash
python tools/build_workflow.py             # the turnaround workflow
python tools/build_meshwright_workflow.py  # ...plus the cleanup stage
python tools/build_docs_images.py          # the figures above
```

`workflows/3d_pixal3d_multi_views.json` is the stock template these are derived
from. When it moves on upstream, drop in the new copy and re-run the builders.

The Fit & Resize figure is rendered by calling the real node, so if the fitting
maths ever changes, the documentation changes with it.

---

## Credits

**Geekatplay Studio — Vladimir Chopine**
[geekatplay.com](https://www.geekatplay.com)

Built on the ComfyUI *Pixal3D: Multi Views to 3D* template by Comfy-Org. The
demo turnaround sheets ship with the pack for testing.

Licensed under the [MIT License](LICENSE).
