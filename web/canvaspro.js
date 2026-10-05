import { app } from "/scripts/app.js";
import { installModelUI, restoreModelUI } from "./model_ui.mjs";

app.registerExtension({
    name: "CanvasPro.ModelInputs",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "CanvasProModelBatchSubmit") return;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = created?.apply(this, args);
            installModelUI(this, message => window.alert(message));
            return result;
        };
        const configure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (...args) {
            const result = configure?.apply(this, args);
            restoreModelUI(this, message => window.alert(message));
            return result;
        };
    },
});
