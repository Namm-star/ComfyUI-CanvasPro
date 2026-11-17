import { IMAGE_MODELS } from "./image_models.mjs";

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
    visibility(node, ["wait_seconds", "request_timeout", "sync_timeout"], Boolean(find(node,"advanced")?.value));
    node.setSize([node.size[0],node.computeSize()[1]]);
    node.setDirtyCanvas(true,true);
}

export function syncTaskAdvanced(node) {
    const advanced = Boolean(find(node,"advanced")?.value);
    const model = find(node,"model")?.value || "";
    const aistars = Boolean(IMAGE_MODELS.aistars[model]);
    const linked = name => node.inputs?.some(i => i.name === name && i.link != null);
    const externalModel = linked("model_input");
    visibility(node,["model"],!externalModel);
    visibility(node,["reference_count", "pixel_size"],false);
    const pixels = externalModel || (!aistars && !model.startsWith("T香蕉") && (model.startsWith("s-") || find(node,"size_mode")?.value === "pixels" || (IMAGE_MODELS.sync[model] && !IMAGE_MODELS.sync[model].auto)));
    visibility(node,["width"],pixels && !linked("width_input"));
    visibility(node,["height"],pixels && !linked("height_input"));
    for (const name of ["width","height"]) {
        const w=find(node,name);
        if (w) { w.options.min=externalModel || model.startsWith("s-")?1:16; w.options.max=externalModel || model.startsWith("s-")?32768:3840; w.options.step=externalModel || model.startsWith("s-")?10:160; }
    }
    visibility(node,["quality"],advanced && (externalModel || (!aistars && !model.startsWith("T香蕉"))));
    visibility(node,["reference_urls"],aistars || (advanced && (externalModel || (!IMAGE_MODELS.sync[model] && !model.startsWith("T香蕉")))));
    node.setSize([node.size[0],node.computeSize()[1]]);
    node.setDirtyCanvas(true,true);
}

export function autoImageCount(node) {
    const model = find(node,"model")?.value || "";
    const externalModel=node.inputs?.some(i => i.name === "model_input" && i.link != null);
    const max = externalModel ? 16 : IMAGE_MODELS.aistars[model] ? IMAGE_MODELS.aistars[model].references : model.startsWith("T香蕉") ? 14 : model.startsWith("s-") ? 15 : 16;
    const highest = Math.max(1,...(node.inputs || []).filter(i => /^image_\d+$/.test(i.name) && i.link != null).map(i => Number(i.name.slice(6))));
    find(node,"reference_count").value = Math.max(1,Math.min(max,highest+1));
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


export function syncQueryUI(node) {
    const source=find(node,"tasks_json");
    const text=String(source?.value || "").trim();
    const record=!text || text.startsWith("{") || text.startsWith("[") || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(text) || text.includes("::seed=") || /^(simple|async|query|import)-[0-9a-f]+$/i.test(text);
    visibility(node,["model"],!record);
    const model=find(node,"model");
    if(model)model.label="手动任务号对应模型";
    if(source){source.label="单独任务（可选，留空查询整个队列）";if(source.inputEl)source.inputEl.placeholder="通常留空：按queue_key自动查询队列内所有模型。仅查询单份报告或平台任务号时填写。";}
    node.setSize?.([node.size?.[0] || 500,node.computeSize?.()[1] || 400]);
    node.setDirtyCanvas?.(true,true);
}

export function submissionTitle(mode,acknowledged,expected){
 if(mode==='restored_existing')return 'CanvasPro · 复用旧批次（本次未新建）';
 if(!acknowledged)return 'CanvasPro · 未取得平台任务号，请查看报告';
 return `CanvasPro · 平台返回任务号 ${acknowledged}/${expected}（非生成完成）`;
}
