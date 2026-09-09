import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

/**
 * Turnaround Splitter - Geekatplay 3D Multiview
 * Geekatplay Studio - Vladimir Chopine | https://www.geekatplay.com
 *
 * Draws the loaded reference sheet inside the node and lets the three cut guides
 * be dragged across it. The guides are stored as fractions of the sheet width, so
 * swapping in a sheet of a different size keeps the cuts where they look right
 * instead of stranding them at stale pixel offsets.
 */

const NODE_CLASS = "GeekatplayTurnaroundSplitter";
const GUIDE_WIDGETS = ["guide_1", "guide_2", "guide_3"];
const GUIDE_COLORS = ["#00E5FF", "#00FF66", "#FF9900"];
const SLICE_TINTS = [
    "rgba(0, 153, 255, 0.10)",
    "rgba(0, 255, 102, 0.10)",
    "rgba(255, 153, 0, 0.10)",
    "rgba(200, 0, 255, 0.10)",
];

const PAD = 10;
const HEADER_H = 20;
const TOOLBAR_H = 26;
const LEGEND_H = 18;
const GAP = 8;
const CHROME_H = PAD * 2 + HEADER_H + TOOLBAR_H + LEGEND_H + GAP * 3;

const GRAB_PX = 10;      // how close the pointer must be to catch a guide
const MIN_GAP = 0.002;   // keeps two guides from collapsing onto each other

function findWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

/** Build a /view URL from a widget value, which may carry a "[input]" annotation. */
function viewUrl(value) {
    let filename = String(value ?? "");
    let type = "input";

    const annotated = /^(.*)\s+\[(\w+)\]$/.exec(filename);
    if (annotated) {
        filename = annotated[1];
        type = annotated[2];
    }

    let subfolder = "";
    const cut = filename.lastIndexOf("/");
    if (cut > -1) {
        subfolder = filename.substring(0, cut);
        filename = filename.substring(cut + 1);
    }

    return api.apiURL(
        `/view?filename=${encodeURIComponent(filename)}` +
        `&type=${encodeURIComponent(type)}` +
        `&subfolder=${encodeURIComponent(subfolder)}` +
        `&rand=${Math.random()}`
    );
}

function loadImage(url) {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => reject(new Error(`could not load ${url}`));
        img.src = url;
    });
}

function styleButton(button, background) {
    Object.assign(button.style, {
        background,
        color: "#FFFFFF",
        border: "none",
        borderRadius: "4px",
        padding: "3px 8px",
        fontSize: "10px",
        fontWeight: "600",
        cursor: "pointer",
        whiteSpace: "nowrap",
    });
    return button;
}

/** Match the backing store to the CSS box so lines stay crisp on any display. */
function syncCanvasSize(canvas, ctx) {
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
    const height = Math.max(1, Math.round(canvas.clientHeight * ratio));
    if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
    }
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    return { width: canvas.clientWidth, height: canvas.clientHeight };
}

app.registerExtension({
    name: "Geekatplay.TurnaroundSplitter",

    async nodeCreated(node) {
        if (node.comfyClass !== NODE_CLASS) return;

        let sheet = null;
        let sheetError = false;
        let loading = false;
        let disposed = false;
        let rafId = null;
        let activeGuide = null;
        let hoverGuide = null;
        let imageRect = { x: 0, y: 0, w: 0, h: 0 };

        // ------------------------------------------------------------- panel
        const container = document.createElement("div");
        Object.assign(container.style, {
            display: "flex",
            flexDirection: "column",
            gap: `${GAP}px`,
            padding: `${PAD}px`,
            boxSizing: "border-box",
            width: "100%",
            height: "100%",
            background: "#12141C",
            borderRadius: "8px",
            fontFamily: "sans-serif",
        });

        const header = document.createElement("div");
        Object.assign(header.style, {
            display: "flex",
            alignItems: "center",
            gap: "6px",
            height: `${HEADER_H}px`,
            flex: "0 0 auto",
        });
        const title = document.createElement("span");
        Object.assign(title.style, { fontSize: "10px", fontWeight: "700", color: "#E6E8F0" });
        title.innerText = "Geekatplay | Turnaround Splitter";
        const status = document.createElement("span");
        Object.assign(status.style, {
            marginLeft: "auto",
            fontSize: "9px",
            fontWeight: "700",
            padding: "2px 6px",
            borderRadius: "3px",
        });
        header.append(title, status);
        container.appendChild(header);

        function setStatus(text, color, background) {
            status.innerText = text;
            status.style.color = color;
            status.style.background = background;
        }
        setStatus("NO SHEET", "#FF9900", "#2A2315");

        // ----------------------------------------------------------- toolbar
        const toolbar = document.createElement("div");
        Object.assign(toolbar.style, {
            display: "flex",
            alignItems: "center",
            gap: "6px",
            height: `${TOOLBAR_H}px`,
            flex: "0 0 auto",
        });

        const evenBtn = styleButton(document.createElement("button"), "#0066FF");
        evenBtn.innerText = "Even quarters";
        evenBtn.title = "Place the three guides at 25% / 50% / 75%";
        evenBtn.onclick = () => setGuides([0.25, 0.5, 0.75]);

        const reloadBtn = styleButton(document.createElement("button"), "#3A3F53");
        reloadBtn.innerText = "Reload";
        reloadBtn.title = "Re-read the reference sheet from the input folder";
        reloadBtn.onclick = () => refreshSheet();

        const sizeLabel = document.createElement("span");
        Object.assign(sizeLabel.style, {
            marginLeft: "auto",
            fontSize: "9px",
            color: "#8A90A6",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
        });

        toolbar.append(evenBtn, reloadBtn, sizeLabel);
        container.appendChild(toolbar);

        // ------------------------------------------------------------ canvas
        const canvasBox = document.createElement("div");
        Object.assign(canvasBox.style, {
            position: "relative",
            flex: "1 1 auto",
            minHeight: "0",
            borderRadius: "6px",
            overflow: "hidden",
            border: "1px solid #0099FF",
            background: "#0B0D14",
        });
        const canvas = document.createElement("canvas");
        Object.assign(canvas.style, {
            display: "block",
            width: "100%",
            height: "100%",
            cursor: "default",
        });
        canvasBox.appendChild(canvas);
        container.appendChild(canvasBox);
        const ctx = canvas.getContext("2d");

        // ------------------------------------------------------------ legend
        const legend = document.createElement("div");
        Object.assign(legend.style, {
            display: "flex",
            alignItems: "center",
            gap: "10px",
            height: `${LEGEND_H}px`,
            flex: "0 0 auto",
            fontSize: "9px",
            color: "#8A90A6",
            overflow: "hidden",
            whiteSpace: "nowrap",
        });
        container.appendChild(legend);

        // ------------------------------------------------------------ guides
        function readGuides() {
            return GUIDE_WIDGETS.map((name, index) => {
                const widget = findWidget(node, name);
                const value = Number(widget?.value);
                return Number.isFinite(value) ? Math.min(Math.max(value, 0), 1) : 0.25 * (index + 1);
            });
        }

        function setGuides(values) {
            const sorted = [...values].sort((a, b) => a - b);
            GUIDE_WIDGETS.forEach((name, index) => {
                const widget = findWidget(node, name);
                if (!widget) return;
                const next = Number(sorted[index].toFixed(4));
                if (widget.value !== next) {
                    widget.value = next;
                    widget.callback?.(next);
                }
            });
            node.setDirtyCanvas?.(true, true);
        }

        // ----------------------------------------------------------- loading
        async function refreshSheet() {
            if (loading || disposed) return;
            const name = findWidget(node, "image")?.value;
            if (!name) {
                sheet = null;
                sheetError = false;
                setStatus("NO SHEET", "#FF9900", "#2A2315");
                sizeLabel.innerText = "";
                return;
            }

            loading = true;
            try {
                const loaded = await loadImage(viewUrl(name));
                if (disposed) return;
                sheet = loaded;
                sheetError = false;
                setStatus("SHEET LOADED", "#00FF66", "#152A17");
                sizeLabel.innerText = `${loaded.naturalWidth} x ${loaded.naturalHeight} px`;
                node.setSize?.(node.computeSize());
            } catch (error) {
                if (disposed) return;
                sheet = null;
                sheetError = true;
                setStatus("CANNOT READ", "#FF4444", "#2A1515");
                sizeLabel.innerText = "";
                console.warn("[Geekatplay] turnaround sheet could not be loaded:", error);
            } finally {
                loading = false;
            }
        }

        const imageWidget = findWidget(node, "image");
        if (imageWidget) {
            const original = imageWidget.callback;
            imageWidget.callback = function (value, ...rest) {
                const result = original?.apply(this, [value, ...rest]);
                refreshSheet();
                return result;
            };
        }

        // ------------------------------------------------------- interaction
        function layout(width, height) {
            if (!sheet?.naturalWidth) return { x: 0, y: 0, w: width, h: height };
            const scale = Math.min(width / sheet.naturalWidth, height / sheet.naturalHeight);
            const w = sheet.naturalWidth * scale;
            const h = sheet.naturalHeight * scale;
            return { x: (width - w) / 2, y: (height - h) / 2, w, h };
        }

        function pointerFraction(event) {
            const rect = canvas.getBoundingClientRect();
            if (!rect.width || !imageRect.w) return null;
            const x = (event.clientX - rect.left) * (canvas.clientWidth / rect.width);
            return Math.min(Math.max((x - imageRect.x) / imageRect.w, 0), 1);
        }

        function guideAt(event) {
            const fraction = pointerFraction(event);
            if (fraction === null) return null;
            const tolerance = GRAB_PX / imageRect.w;
            const guides = readGuides();

            let best = null;
            let bestDistance = tolerance;
            guides.forEach((guide, index) => {
                const distance = Math.abs(guide - fraction);
                if (distance <= bestDistance) {
                    best = index;
                    bestDistance = distance;
                }
            });
            return best;
        }

        canvas.addEventListener("pointerdown", (event) => {
            const index = guideAt(event);
            if (index === null) return;
            event.stopPropagation();
            event.preventDefault();
            activeGuide = index;
            canvas.setPointerCapture?.(event.pointerId);
            canvas.style.cursor = "ew-resize";
        });

        canvas.addEventListener("pointermove", (event) => {
            if (activeGuide === null) {
                const hovered = guideAt(event);
                if (hovered !== hoverGuide) {
                    hoverGuide = hovered;
                    canvas.style.cursor = hovered === null ? "default" : "ew-resize";
                }
                return;
            }

            event.stopPropagation();
            const fraction = pointerFraction(event);
            if (fraction === null) return;

            // Hold the moving guide between its neighbours so the four slices keep
            // their left-to-right order while the pointer is dragged past them.
            const guides = readGuides();
            const lower = activeGuide === 0 ? 0 : guides[activeGuide - 1] + MIN_GAP;
            const upper = activeGuide === guides.length - 1 ? 1 : guides[activeGuide + 1] - MIN_GAP;
            guides[activeGuide] = Math.min(Math.max(fraction, lower), upper);
            setGuides(guides);
        });

        function endDrag(event) {
            if (activeGuide === null) return;
            activeGuide = null;
            hoverGuide = null;
            canvas.style.cursor = "default";
            canvas.releasePointerCapture?.(event.pointerId);
        }
        canvas.addEventListener("pointerup", endDrag);
        canvas.addEventListener("pointercancel", endDrag);
        canvas.addEventListener("pointerleave", () => {
            if (activeGuide === null) canvas.style.cursor = "default";
        });

        // --------------------------------------------------------- rendering
        function sliceWidths(guides) {
            if (!sheet?.naturalWidth) return null;
            const width = sheet.naturalWidth;
            const bounds = [0, ...guides.map((g) => Math.round(g * width)), width];
            const widths = [];
            for (let i = 0; i < 4; i += 1) {
                widths.push(Math.max(0, bounds[i + 1] - bounds[i]));
            }
            return widths;
        }

        function renderLegend(guides) {
            const widths = sliceWidths(guides);
            const height = sheet?.naturalHeight ?? 0;
            legend.replaceChildren();

            if (!widths) {
                const hint = document.createElement("span");
                hint.innerText = "load a turnaround sheet, then drag the guides";
                legend.appendChild(hint);
                return;
            }

            widths.forEach((width, index) => {
                const item = document.createElement("span");
                Object.assign(item.style, { display: "inline-flex", alignItems: "center", gap: "4px" });
                const dot = document.createElement("span");
                Object.assign(dot.style, {
                    width: "8px",
                    height: "8px",
                    borderRadius: "2px",
                    background: GUIDE_COLORS[index % GUIDE_COLORS.length],
                });
                const label = document.createElement("span");
                label.innerText = `${index + 1}: ${width}x${height}`;
                item.append(dot, label);
                legend.appendChild(item);
            });
        }

        function draw() {
            if (disposed || !canvas.isConnected) return;
            const { width, height } = syncCanvasSize(canvas, ctx);
            ctx.clearRect(0, 0, width, height);

            ctx.fillStyle = "#0B0D14";
            ctx.fillRect(0, 0, width, height);

            if (!sheet?.naturalWidth) {
                ctx.fillStyle = sheetError ? "#FF6666" : "#5A6076";
                ctx.font = "600 11px sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(
                    sheetError ? "reference sheet could not be read" : "no reference sheet loaded",
                    width / 2,
                    height / 2
                );
                renderLegend([]);
                return;
            }

            imageRect = layout(width, height);
            ctx.drawImage(sheet, imageRect.x, imageRect.y, imageRect.w, imageRect.h);

            const guides = readGuides();
            const edges = [0, ...guides, 1];

            // Alternating tint so the four outgoing views read at a glance.
            for (let i = 0; i < 4; i += 1) {
                const left = imageRect.x + edges[i] * imageRect.w;
                const right = imageRect.x + edges[i + 1] * imageRect.w;
                ctx.fillStyle = SLICE_TINTS[i];
                ctx.fillRect(left, imageRect.y, right - left, imageRect.h);
            }

            // Slice numbers.
            ctx.font = "700 12px sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            for (let i = 0; i < 4; i += 1) {
                const left = imageRect.x + edges[i] * imageRect.w;
                const right = imageRect.x + edges[i + 1] * imageRect.w;
                if (right - left < 16) continue;
                const cx = (left + right) / 2;
                ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
                ctx.fillRect(cx - 10, imageRect.y + 4, 20, 16);
                ctx.fillStyle = "#FFFFFF";
                ctx.fillText(String(i + 1), cx, imageRect.y + 6);
            }

            // Guides plus their grab tabs.
            guides.forEach((guide, index) => {
                const x = imageRect.x + guide * imageRect.w;
                const color = GUIDE_COLORS[index % GUIDE_COLORS.length];
                const active = activeGuide === index || hoverGuide === index;

                ctx.strokeStyle = color;
                ctx.lineWidth = active ? 3 : 2;
                ctx.beginPath();
                ctx.moveTo(x, imageRect.y);
                ctx.lineTo(x, imageRect.y + imageRect.h);
                ctx.stroke();

                const tabH = 26;
                const tabW = 9;
                const tabY = imageRect.y + imageRect.h / 2 - tabH / 2;
                ctx.fillStyle = color;
                ctx.fillRect(x - tabW / 2, tabY, tabW, tabH);
                ctx.strokeStyle = "#0B0D14";
                ctx.lineWidth = 1;
                ctx.strokeRect(x - tabW / 2, tabY, tabW, tabH);

                const pixels = Math.round(guide * sheet.naturalWidth);
                ctx.font = "700 9px sans-serif";
                ctx.textAlign = "center";
                ctx.textBaseline = "bottom";
                const text = `${pixels}px`;
                const textWidth = ctx.measureText(text).width + 6;
                ctx.fillStyle = "rgba(0, 0, 0, 0.65)";
                ctx.fillRect(x - textWidth / 2, imageRect.y + imageRect.h - 15, textWidth, 13);
                ctx.fillStyle = color;
                ctx.fillText(text, x, imageRect.y + imageRect.h - 3);
            });

            renderLegend(guides);
        }

        let lastFrame = 0;
        function drawLoop(timestamp) {
            if (disposed) return;
            rafId = requestAnimationFrame(drawLoop);
            if (timestamp - lastFrame < 33) return;
            lastFrame = timestamp;
            if (node.flags?.collapsed) return;
            draw();
        }

        // --------------------------------------------------------- lifecycle
        const widget = node.addDOMWidget("splitter_preview", "geekatplay_splitter", container, {
            getValue: () => "",
            setValue: () => {},
        });
        // Frontend 1.4x reads widget.serialize as an own property and ignores the
        // options bag, so an unsuppressed preview widget would lengthen
        // widgets_values and wipe every saved field on reload.
        widget.serialize = false;

        widget.computeSize = function (width) {
            const panelW = Math.max(360, width || 520);
            const canvasW = panelW - PAD * 2;
            const aspect = sheet?.naturalWidth
                ? sheet.naturalWidth / sheet.naturalHeight
                : 16 / 9;
            const canvasH = Math.min(Math.max(canvasW / aspect, 150), 460);
            return [panelW, Math.round(canvasH + CHROME_H)];
        };

        const originalOnConfigure = node.onConfigure;
        node.onConfigure = function (info) {
            const result = originalOnConfigure?.apply(this, arguments);
            // widgets_values is positional, and the upload button the frontend
            // injects for the image picker shifts those positions. When the saved
            // node carries the named form, trust it over the index order.
            const named = info?.widgets_values_named;
            if (named && typeof named === "object") {
                for (const [name, value] of Object.entries(named)) {
                    const target = findWidget(this, name);
                    if (target && value !== undefined && value !== null) target.value = value;
                }
            }
            refreshSheet();
            return result;
        };

        const originalOnRemoved = node.onRemoved;
        node.onRemoved = function () {
            disposed = true;
            if (rafId) cancelAnimationFrame(rafId);
            resizeObserver?.disconnect();
            return originalOnRemoved?.apply(this, arguments);
        };

        const resizeObserver = typeof ResizeObserver !== "undefined"
            ? new ResizeObserver(() => {
                  if (!disposed) draw();
              })
            : null;
        resizeObserver?.observe(canvasBox);

        node.setSize(node.computeSize());
        refreshSheet();
        rafId = requestAnimationFrame(drawLoop);
    },
});
