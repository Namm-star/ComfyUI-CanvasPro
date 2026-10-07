const find = (node, name) => node.widgets?.find(w => w.name === name);

export function visibility(node, names, visible) {
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

export function syncTaskPorts(node) {
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

export function syncTaskAdvanced(node) {
    const advanced = Boolean(find(node,"advanced")?.value);
    const model = find(node,"model")?.value || "";
    visibility(node,["reference_count", "pixel_size"],false);
    const pixels = !model.startsWith("T香蕉") && (model.startsWith("s-") || find(node,"size_mode")?.value === "pixels");
    visibility(node,["width", "height"],pixels);
    for (const name of ["width","height"]) {
        const w=find(node,name);
        if (w) { w.options.min=model.startsWith("s-")?1:16; w.options.max=model.startsWith("s-")?32768:3840; w.options.step=model.startsWith("s-")?10:160; }
    }
    visibility(node,["quality"],advanced && !model.startsWith("T香蕉"));
    visibility(node,["reference_urls"],advanced && !model.startsWith("T香蕉"));
    node.setSize([node.size[0],node.computeSize()[1]]);
    node.setDirtyCanvas(true,true);
}

export function autoImageCount(node) {
    const model = find(node,"model")?.value || "";
    const max = model.startsWith("T香蕉") ? 14 : model.startsWith("s-") ? 15 : 16;
    const highest = Math.max(1,...(node.inputs || []).filter(i => /^image_\d+$/.test(i.name) && i.link != null).map(i => Number(i.name.slice(6))));
    find(node,"reference_count").value = Math.min(max,highest+1);
}


export function migrateTaskDimensions(values) {
    if (!Array.isArray(values)) return values;
    const match = /^(\d+)x(\d+)$/.exec(String(values[4] || ""));
    if (!match || ![10,12].includes(values.length)) return values;
    const migrated = [...values];
    migrated.splice(4,1);
    if (values.length === 10) migrated.push(Number(match[1]),Number(match[2]));
    return migrated;
}
