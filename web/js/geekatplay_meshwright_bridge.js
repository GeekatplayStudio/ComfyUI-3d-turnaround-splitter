import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

/**
 * Open in Meshwright - Geekatplay 3D Multiview
 * Geekatplay Studio - Vladimir Chopine | https://www.geekatplay.com
 *
 * Shows where the finished model was written and offers to reveal it on disk or
 * start the Meshwright desktop app. Meshwright opens on an empty viewport, so
 * the path is displayed in full and can be copied in one click.
 */

const NODE_CLASS = "GeekatplayOpenInMeshwright";
const DOWNLOAD_URL = "https://github.com/GeekatplayStudio/Meshwright";

function findWidget(node, name) {
    return node.widgets?.find((w) => w.name === name);
}

function styleButton(button, background) {
    Object.assign(button.style, {
        background,
        color: "#FFFFFF",
        border: "none",
        borderRadius: "4px",
        padding: "5px 9px",
        fontSize: "10px",
        fontWeight: "600",
        cursor: "pointer",
        whiteSpace: "nowrap",
        flex: "1 1 auto",
    });
    return button;
}

app.registerExtension({
    name: "Geekatplay.OpenInMeshwright",

    async nodeCreated(node) {
        if (node.comfyClass !== NODE_CLASS) return;

        let modelPath = "";
        let meshwrightRoot = "";

        const container = document.createElement("div");
        Object.assign(container.style, {
            display: "flex",
            flexDirection: "column",
            gap: "6px",
            padding: "10px",
            boxSizing: "border-box",
            width: "100%",
            height: "100%",
            background: "#12141C",
            borderRadius: "8px",
            fontFamily: "sans-serif",
        });

        const header = document.createElement("div");
        Object.assign(header.style, {
            fontSize: "10px",
            fontWeight: "700",
            color: "#E6E8F0",
            flex: "0 0 auto",
        });
        header.innerText = "Geekatplay | Meshwright";
        container.appendChild(header);

        const pathBox = document.createElement("div");
        Object.assign(pathBox.style, {
            flex: "1 1 auto",
            minHeight: "34px",
            fontSize: "9px",
            fontFamily: "monospace",
            color: "#8A90A6",
            background: "#0B0D14",
            border: "1px solid #232838",
            borderRadius: "4px",
            padding: "6px",
            overflow: "auto",
            wordBreak: "break-all",
        });
        pathBox.innerText = "run the graph to produce a model";
        container.appendChild(pathBox);

        const buttons = document.createElement("div");
        Object.assign(buttons.style, { display: "flex", gap: "5px", flex: "0 0 auto" });

        const revealBtn = styleButton(document.createElement("button"), "#0066FF");
        revealBtn.innerText = "Show file";
        revealBtn.title = "Open the folder with this model selected";

        const launchBtn = styleButton(document.createElement("button"), "#00A05A");
        launchBtn.innerText = "Open Meshwright";
        launchBtn.title = "Start the Meshwright desktop app";

        const copyBtn = styleButton(document.createElement("button"), "#3A3F53");
        copyBtn.innerText = "Copy path";

        buttons.append(revealBtn, launchBtn, copyBtn);
        container.appendChild(buttons);

        const status = document.createElement("div");
        Object.assign(status.style, {
            fontSize: "9px",
            color: "#8A90A6",
            flex: "0 0 auto",
            minHeight: "12px",
        });
        container.appendChild(status);

        function setStatus(text, color) {
            status.innerText = text;
            status.style.color = color || "#8A90A6";
        }

        async function call(action) {
            if (!modelPath) {
                setStatus("Run the graph first - there is no model yet.", "#FF9900");
                return;
            }
            setStatus("Working...");
            try {
                const response = await api.fetchApi("/geekatplay/meshwright/open", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        action,
                        model_path: modelPath,
                        meshwright_folder: findWidget(node, "meshwright_folder")?.value ?? "",
                    }),
                });
                const result = await response.json();
                setStatus(result.ok ? result.message : result.error, result.ok ? "#00FF66" : "#FF6666");
            } catch (error) {
                setStatus(String(error), "#FF6666");
            }
        }

        revealBtn.onclick = () => call("reveal");
        launchBtn.onclick = () => call("launch");
        copyBtn.onclick = async () => {
            if (!modelPath) {
                setStatus("Run the graph first - there is no model yet.", "#FF9900");
                return;
            }
            try {
                await navigator.clipboard.writeText(modelPath);
                setStatus("Path copied.", "#00FF66");
            } catch (error) {
                setStatus("Could not reach the clipboard.", "#FF6666");
            }
        };

        const link = document.createElement("a");
        Object.assign(link.style, { fontSize: "9px", color: "#00A5FF", flex: "0 0 auto" });
        link.href = DOWNLOAD_URL;
        link.target = "_blank";
        link.rel = "noopener";
        link.innerText = "Get Meshwright";
        container.appendChild(link);

        const widget = node.addDOMWidget("meshwright_panel", "geekatplay_meshwright", container, {
            getValue: () => "",
            setValue: () => {},
        });
        // Presentation only. Left serializable it would lengthen widgets_values and
        // wipe the node's real fields on reload.
        widget.serialize = false;

        widget.computeSize = function (width) {
            return [Math.max(300, width || 340), 150];
        };

        const originalOnExecuted = node.onExecuted;
        node.onExecuted = function (message) {
            const result = originalOnExecuted?.apply(this, arguments);
            const info = message?.meshwright?.[0];
            if (info) {
                modelPath = info.model_path || "";
                meshwrightRoot = info.meshwright_root || "";
                pathBox.innerText = modelPath || "no model path reported";
                if (!info.exists) {
                    setStatus("The file is not on disk.", "#FF9900");
                } else if (meshwrightRoot) {
                    setStatus(`Meshwright found at ${meshwrightRoot}`, "#00FF66");
                } else {
                    setStatus("Meshwright not found - set its folder below, or install it.", "#FF9900");
                }
            }
            return result;
        };

        node.setSize(node.computeSize());
    },
});
