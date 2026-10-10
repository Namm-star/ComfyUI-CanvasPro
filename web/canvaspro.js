import { app } from "/scripts/app.js";
import { api } from "/scripts/api.js";

// Self-contained entry: helper code cannot load from a stale module cache.
const IMAGE_MODELS = {
  "aistars": {
    "即梦-55-gpt-image-2": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 9
    },
    "即梦-55-gpt-image-2.5-flare": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-55-gpt-image-2.5-sunburst": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-66-gpt-image-2.5-flare": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-66-gpt-image-2.5-sunburst": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-67-gpt-image-2.5-flare": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-67-gpt-image-2.5-sunburst": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-52-gpt-image-2": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 9
    },
    "即梦-52-gpt-image-2.5-flare": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-52-gpt-image-2.5-sunburst": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-46-gpt-image-2": {
      "ratios": [
        "1:1",
        "4:3",
        "3:2",
        "16:9",
        "21:9",
        "3:4",
        "2:3",
        "9:16"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-46-gpt-image-2.5-flare": {
      "ratios": [
        "1:1",
        "9:16",
        "16:9",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-46-gpt-image-2.5-sunburst": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4",
        "21:9"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 6
    },
    "即梦-23-gemini-3-pro-image-preview": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 7
    },
    "即梦-23-gemini-3.1-flash-image-preview": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4"
      ],
      "resolutions": [
        "1K",
        "2K",
        "4K"
      ],
      "references": 7
    },
    "即梦-65-seedream-5-pro": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4"
      ],
      "resolutions": [
        "1K",
        "2K"
      ],
      "references": 6
    },
    "即梦-65-seedream-5-lite": {
      "ratios": [
        "16:9",
        "9:16",
        "1:1",
        "4:3",
        "3:4"
      ],
      "resolutions": [
        "4K"
      ],
      "references": 6
    }
  },
  "banana_ratios": {
    "T香蕉pro": [
      "1:1",
      "2:3",
      "3:2",
      "3:4",
      "4:3",
      "4:5",
      "5:4",
      "9:16",
      "16:9",
      "21:9"
    ],
    "T香蕉2": [
      "1:1",
      "2:3",
      "3:2",
      "3:4",
      "4:3",
      "4:5",
      "5:4",
      "9:16",
      "16:9",
      "21:9",
      "1:4",
      "4:1",
      "1:8",
      "8:1"
    ],
    "T香蕉2.1": [
      "1:1",
      "2:3",
      "3:2",
      "3:4",
      "4:3",
      "4:5",
      "5:4",
      "9:16",
      "16:9",
      "21:9",
      "1:4",
      "4:1",
      "1:8",
      "8:1"
    ]
  }
};

function modelPolicy(model, mode = "pixels") {
    const banana = model.startsWith("T香蕉");
    const hc = model.startsWith("s-");
    const aistars = IMAGE_MODELS.aistars[model];
    return {
        max: aistars ? 0 : banana ? 14 : hc ? 15 : 16,
        ratios: aistars?.ratios || IMAGE_MODELS.banana_ratios[model] || ["1:1","3:4","4:3","9:16","16:9"],
        resolutions: aistars?.resolutions || ["1K","2K","4K"],
        visible: new Set([
            "reference_count",
            ...(!aistars && !banana && !hc ? ["size_mode"] : []),
            ...(!aistars && (hc || (!banana && mode === "pixels")) ? ["pixel_size", "width", "height"] : []),
            ...(aistars || banana || (!hc && mode === "ratio") ? ["aspect_ratio", "image_size"] : []),
            ...(aistars ? ["reference_urls"] : !banana ? ["quality", "reference_urls"] : []),
        ]),
        qualities: ["", "auto", "low", "medium", "high", ...(hc && model !== "s-gpt-image-2" ? ["xhigh", "max"] : [])],
    };
}

const parameters = ["size_mode", "pixel_size", "width", "height", "aspect_ratio", "quality", "image_size", "reference_urls"];
const widget = (node, name) => node.widgets?.find(w => w.name === name);

function syncModelUI(node, notify = () => {}, restoring = false) {
    const model = widget(node, "model").value;
    const policy = modelPolicy(model, widget(node, "size_mode")?.value);
    // Linked models can be computed upstream. Keep their parameter choices
    // available until backend validation resolves the actual model.
    if (node.inputs?.some(i => i.name === "model_input" && i.link != null)) {
        policy.max = 16;
        for (const name of parameters) policy.visible.add(name);
        policy.qualities = ["", "auto", "low", "medium", "high", "xhigh", "max"];
        policy.ratios = [...new Set(Object.values(IMAGE_MODELS.banana_ratios).flat())];
        policy.resolutions = ["1K","2K","4K"];
    }
    // New task nodes use numeric dimensions. Hide the compatibility field at
    // the base policy level, so later model/UI refreshes cannot reveal it.
    if (widget(node, "width") && widget(node, "height")) policy.visible.delete("pixel_size");
    if (!restoring && model.startsWith("T香蕉") && widget(node, "reference_urls")?.value?.trim()) {
        notify("香蕉不支持 URL 参考图，请先清空 reference_urls，再切换模型；原内容已保留。");
        return false;
    }
    const countWidget = widget(node, "reference_count");
    const count = Math.max(0, Math.min(policy.max, Math.round(Number(countWidget.value) || 2)));
    const removed = (node.inputs || []).filter(input => {
        const m = /^image_(\d+)$/.exec(input.name);
        return m ? Number(m[1]) > count : parameters.includes(input.name) && !policy.visible.has(input.name);
    });
    // Refuse a switch that would discard wiring. During load preserve links and
    // let backend validation identify the incompatible workflow instead.
    if (removed.some(input => input.link != null)) {
        if (!restoring) {
            notify("请先断开不兼容的图片/参数连线，再切换模型或减少参考图端口；现有连线已保留。");
            return false;
        }
    }
    for (let i = (node.inputs?.length || 0) - 1; i >= 0; i--) {
        if (removed.includes(node.inputs[i]) && node.inputs[i].link == null) node.removeInput(i);
    }
    for (let i = 1; i <= count; i++) {
        if (!node.inputs?.some(input => input.name === `image_${i}`)) node.addInput(`image_${i}`, "IMAGE");
    }
    countWidget.value = Math.max(1,count);
    countWidget.options.max = Math.max(1,policy.max);
    for(const [name,values] of [["aspect_ratio",policy.ratios],["image_size",policy.resolutions]]) {
        const w=widget(node,name);
        if(w) {w.options.values=values;if(!values.includes(w.value))w.value=values.includes("1:1")?"1:1":values[0];}
    }
    for (const name of parameters) {
        const w = widget(node, name);
        if (!w) continue;
        if (!w.canvasproOriginal) w.canvasproOriginal = { type: w.type, computeSize: w.computeSize, draw: w.draw };
        const visible = policy.visible.has(name);
        w.type = visible ? w.canvasproOriginal.type : "converted-widget";
        w.hidden = !visible;
        w.draw = visible ? w.canvasproOriginal.draw : () => {};
        w.computeSize = visible ? w.canvasproOriginal.computeSize : () => [0, -4];
        // DOM-backed multiline widgets need their element hidden as well.
        if (w.inputEl) w.inputEl.style.display = visible ? "" : "none";
        if (w.element) w.element.style.display = visible ? "" : "none";
    }
    const quality = widget(node, "quality");
    quality.options.values = policy.qualities;
    if (!policy.qualities.includes(quality.value)) quality.value = "";
    node.setSize([node.size[0], node.computeSize()[1]]);
    node.setDirtyCanvas(true, true);
    return true;
}

function installModelUI(node, notify) {
    for (const name of ["model", "size_mode", "reference_count"]) {
        const w = widget(node, name);
        const callback = w.callback;
        let previous = w.value;
        w.callback = function (value, ...args) {
            if (!syncModelUI(node, notify)) {
                w.value = previous;
                return;
            }
            previous = w.value;
            return callback?.call(this, w.value, ...args);
        };
        // Restored widgets may replace initial values without firing callback.
        w.canvasproRemember = () => { previous = w.value; };
    }
    syncModelUI(node, notify, true);
}

function restoreModelUI(node, notify) {
    syncModelUI(node, notify, true);
    for (const name of ["model", "size_mode", "reference_count"]) widget(node, name).canvasproRemember?.();
}

const find = (node, name) => node.widgets?.find(w => w.name === name);

function visibility(node, names, visible) {
    for (const name of names) {
        const w = find(node, name);
        if (!w) continue;
        const original = w.canvasproOriginal || (w.canvasproOriginal = {type:w.type, computeSize:w.computeSize, draw:w.draw});
        w.type = visible ? original.type : "converted-widget";
        w.hidden = !visible;
        w.draw = visible ? original.draw : () => {};
        w.computeSize = visible ? original.computeSize : () => [0,-4];
        if (w.inputEl) w.inputEl.style.display = visible ? "" : "none";
        if (w.element) w.element.style.display = visible ? "" : "none";
    }
}

function syncTaskPorts(node) {
    const connected = (node.inputs || []).filter(i => /^task_\d+$/.test(i.name) && i.link != null);
    const highest = Math.max(1, ...connected.map(i => Number(i.name.slice(5))));
    const count = Math.min(256, highest + 1);
    for (let i = (node.inputs?.length || 0)-1; i >= 0; i--) {
        const input = node.inputs[i];
        if (/^task_\d+$/.test(input.name) && Number(input.name.slice(5)) > count && input.link == null) node.removeInput(i);
    }
    for (let i=1; i<=count; i++) {
        if (!node.inputs?.some(input => input.name === `task_${i}`)) node.addInput(`task_${i}`, "CANVASPRO_TASKS");
    }
    visibility(node, ["wait_seconds", "request_timeout"], Boolean(find(node,"advanced")?.value));
    node.setSize([node.size[0],node.computeSize()[1]]);
    node.setDirtyCanvas(true,true);
}

function syncTaskAdvanced(node) {
    const advanced = Boolean(find(node,"advanced")?.value);
    const model = find(node,"model")?.value || "";
    const aistars = Boolean(IMAGE_MODELS.aistars[model]);
    const linked = name => node.inputs?.some(i => i.name === name && i.link != null);
    const externalModel = linked("model_input");
    visibility(node,["model"],!externalModel);
    visibility(node,["reference_count", "pixel_size"],false);
    const pixels = externalModel || (!aistars && !model.startsWith("T香蕉") && (model.startsWith("s-") || find(node,"size_mode")?.value === "pixels"));
    visibility(node,["width"],pixels && !linked("width_input"));
    visibility(node,["height"],pixels && !linked("height_input"));
    for (const name of ["width","height"]) {
        const w=find(node,name);
        if (w) { w.options.min=externalModel || model.startsWith("s-")?1:16; w.options.max=externalModel || model.startsWith("s-")?32768:3840; w.options.step=externalModel || model.startsWith("s-")?10:160; }
    }
    visibility(node,["quality"],advanced && (externalModel || (!aistars && !model.startsWith("T香蕉"))));
    visibility(node,["reference_urls"],aistars || (advanced && (externalModel || !model.startsWith("T香蕉"))));
    node.setSize([node.size[0],node.computeSize()[1]]);
    node.setDirtyCanvas(true,true);
}

function autoImageCount(node) {
    const model = find(node,"model")?.value || "";
    const externalModel=node.inputs?.some(i => i.name === "model_input" && i.link != null);
    const max = externalModel ? 16 : IMAGE_MODELS.aistars[model] ? 0 : model.startsWith("T香蕉") ? 14 : model.startsWith("s-") ? 15 : 16;
    const highest = Math.max(1,...(node.inputs || []).filter(i => /^image_\d+$/.test(i.name) && i.link != null).map(i => Number(i.name.slice(6))));
    find(node,"reference_count").value = Math.max(1,Math.min(max,highest+1));
}


function migrateTaskDimensions(values) {
    if (!Array.isArray(values)) return values;
    const match = /^(\d+)x(\d+)$/.exec(String(values[4] || ""));
    if (!match || ![10,12].includes(values.length)) return values;
    const migrated = [...values];
    migrated.splice(4,1);
    if (values.length === 10) migrated.push(Number(match[1]),Number(match[2]));
    return migrated;
}

app.registerExtension({
    name: "CanvasPro.ModelInputs",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const task = nodeData.name === "CanvasProPromptTask";
        const batch = nodeData.name === "CanvasProBatchExecute";
        if (!batch && !task && nodeData.name !== "CanvasProModelBatchSubmit") return;
        // Trim frontend definitions before ComfyUI constructs the node. The
        // backend retains every supported input for API validation/execution.
        if (task || batch) {
            const pattern = batch ? /^task_(\d+)$/ : /^image_(\d+)$/;
            const optional = nodeData.input?.optional;
            if (optional) for (const name of Object.keys(optional)) {
                const match = pattern.exec(name);
                if (match && Number(match[1]) > 2) delete optional[name];
            }
        }
        const notify = message => window.alert(message);
        const refresh = node => {
            if (batch) syncTaskPorts(node);
            else if (task) { autoImageCount(node); syncModelUI(node,notify,true); syncTaskAdvanced(node); }
        };
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = created?.apply(this,args);
            if (batch) {
                const old = this.widgets?.find(w => w.name === "api_key");
                if (old && this.addDOMWidget && typeof document !== "undefined") {
                    const index = this.widgets.indexOf(old);
                    const input = document.createElement("input");
                    input.type = "password";
                    input.placeholder = "填写 CanvasPro API Key";
                    input.autocomplete = "off";
                    input.style.cssText = "width:100%;box-sizing:border-box;background:#222;color:#ddd;border:1px solid #555;padding:6px";
                    input.value = old.value || "";
                    const key = this.addDOMWidget("api_key", "STRING", input, {
                        getValue: () => input.value,
                        setValue: value => { input.value = value || ""; },
                    });
                    key.value = input.value;
                    key.computeSize = width => [width,32];
                    this.widgets.splice(this.widgets.indexOf(key),1);
                    this.widgets.splice(index,1,key);
                }
            }
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
            if (task && args[0]?.widgets_values) {
                const values = migrateTaskDimensions(args[0].widgets_values);
                if (values !== args[0].widgets_values) {
                    args[0].widgets_values = values;
                    for (let i=0;i<values.length;i++) if(this.widgets[i]) this.widgets[i].value=values[i];
                }
            }
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
