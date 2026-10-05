import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";
import { installModelUI, restoreModelUI, syncModelUI } from "./model_ui.mjs";
import { syncTaskPorts, syncTaskAdvanced, autoImageCount } from "./batch_ui.mjs";

app.registerExtension({
    name: "CanvasPro.ModelInputs",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const task = nodeData.name === "CanvasProPromptTask";
        const batch = nodeData.name === "CanvasProBatchExecute";
        if (!batch && !task && nodeData.name !== "CanvasProModelBatchSubmit") return;
        const notify = message => window.alert(message);
        const refresh = node => {
            if (batch) syncTaskPorts(node);
            else if (task) { autoImageCount(node); syncModelUI(node,notify,true); syncTaskAdvanced(node); }
        };
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = created?.apply(this,args);
            if (!batch) installModelUI(this,notify);
            if (task || batch) {
                const advanced = this.widgets?.find(w => w.name === "advanced");
                const callback = advanced?.callback;
                if (advanced) advanced.callback = (...args) => { callback?.apply(advanced,args); refresh(this); };
                if (task) for (const name of ["model","size_mode"]) {
                    const w = this.widgets.find(w => w.name === name);
                    const cb = w.callback;
                    const thisNode = this;
                    w.callback = function (...args) { const result=cb?.apply(this,args); syncTaskAdvanced(thisNode); return result; };
                }
                refresh(this);
            }
            return result;
        };
        const configure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (...args) {
            const result = configure?.apply(this,args);
            if (!batch) restoreModelUI(this,notify);
            refresh(this);
            return result;
        };
        const connections = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function (...args) {
            const result = connections?.apply(this,args);
            if ((task || batch) && !this.canvasproSyncPending) {
                this.canvasproSyncPending = true;
                queueMicrotask(() => { this.canvasproSyncPending=false; refresh(this); });
            }
            return result;
        };
    },
});

api.addEventListener("canvaspro.batch_status", event => {
    const { node_id, phase, counts } = event.detail;
    const node = app.graph?.getNodeById(node_id);
    if (!node || node.comfyClass !== "CanvasProBatchExecute") return;
    const queued = (counts.prepared || 0) + (counts.sending || 0) + (counts.queued || 0);
    node.title = `CanvasPro · ${phase} | 排队 ${queued} · 处理中 ${counts.processing || 0} · 成功 ${counts.succeeded || 0} · 失败 ${counts.failed || 0}`;
    if (counts.submit_unknown) node.title += ` · 待确认 ${counts.submit_unknown}`;
    node.setDirtyCanvas(true,true);
});
