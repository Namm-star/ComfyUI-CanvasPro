export function modelPolicy(model, mode = "pixels") {
    const banana = model.startsWith("T香蕉");
    const hc = model.startsWith("s-");
    return {
        max: banana ? 14 : hc ? 15 : 16,
        visible: new Set([
            "reference_count",
            ...(!banana && !hc ? ["size_mode"] : []),
            ...(hc || (!banana && mode === "pixels") ? ["pixel_size", "width", "height"] : []),
            ...(banana || (!hc && mode === "ratio") ? ["aspect_ratio", "image_size"] : []),
            ...(!banana ? ["quality", "reference_urls"] : []),
        ]),
        qualities: ["", "auto", "low", "medium", "high", ...(hc && model !== "s-gpt-image-2" ? ["xhigh", "max"] : [])],
    };
}

const parameters = ["size_mode", "pixel_size", "width", "height", "aspect_ratio", "quality", "image_size", "reference_urls"];
const widget = (node, name) => node.widgets?.find(w => w.name === name);

export function syncModelUI(node, notify = () => {}, restoring = false) {
    const model = widget(node, "model").value;
    const policy = modelPolicy(model, widget(node, "size_mode")?.value);
    // New task nodes use numeric dimensions. Hide the compatibility field at
    // the base policy level, so later model/UI refreshes cannot reveal it.
    if (widget(node, "width") && widget(node, "height")) policy.visible.delete("pixel_size");
    if (!restoring && model.startsWith("T香蕉") && widget(node, "reference_urls")?.value?.trim()) {
        notify("香蕉不支持 URL 参考图，请先清空 reference_urls，再切换模型；原内容已保留。");
        return false;
    }
    const countWidget = widget(node, "reference_count");
    const count = Math.max(1, Math.min(policy.max, Math.round(Number(countWidget.value) || 2)));
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
    countWidget.value = count;
    countWidget.options.max = policy.max;
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

export function installModelUI(node, notify) {
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

export function restoreModelUI(node, notify) {
    syncModelUI(node, notify, true);
    for (const name of ["model", "size_mode", "reference_count"]) widget(node, name).canvasproRemember?.();
}
