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
    const pixels = Boolean(IMAGE_MODELS.hc_native[model]) || externalModel || (!aistars && !model.startsWith("T香蕉") && (model.startsWith("s-") || find(node,"size_mode")?.value === "pixels" || (IMAGE_MODELS.sync[model] && !IMAGE_MODELS.sync[model].auto)));
    visibility(node,["width"],pixels && !linked("width_input"));
    visibility(node,["height"],pixels && !linked("height_input"));
    for (const name of ["width","height"]) {
        const w=find(node,name);
        if (w) { w.options.min=(externalModel || model.startsWith("s-") || IMAGE_MODELS.hc_native[model])?1:16; w.options.max=(externalModel || model.startsWith("s-") || IMAGE_MODELS.hc_native[model])?32768:3840; w.options.step=(externalModel || model.startsWith("s-") || IMAGE_MODELS.hc_native[model])?10:160; }
    }
    visibility(node,["quality"],advanced && (externalModel || (!aistars && !model.startsWith("T香蕉"))));
    visibility(node,["reference_urls"],aistars || (advanced && (externalModel || (!IMAGE_MODELS.sync[model] && !model.startsWith("T香蕉")))));
    const native=IMAGE_MODELS.hc_native[model];
    visibility(node,['background','output_format'],Boolean(native));
    if(native){const format=find(node,'output_format');if(format){format.options.values=['',...native.formats];if(!format.options.values.includes(format.value))format.value='';}}
    node.setSize([node.size[0],node.computeSize()[1]]);
    node.setDirtyCanvas(true,true);
}

export function autoImageCount(node) {
    const model = find(node,"model")?.value || "";
    const externalModel=node.inputs?.some(i => i.name === "model_input" && i.link != null);
    const max = externalModel ? 16 : IMAGE_MODELS.aistars[model] ? IMAGE_MODELS.aistars[model].references : model.startsWith("T香蕉") ? 14 : (model.startsWith("s-") || IMAGE_MODELS.hc_native[model]) ? 15 : 16;
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
    visibility(node,["wait_seconds"],false);
    const timeout=find(node,"request_timeout");
    if(timeout)timeout.label="单次请求超时（秒）";
    const history=find(node,"include_history");
    if(history)history.label="包含历史结果（会重复输出）";
    const source=find(node,"tasks_json");
    const text=String(source?.value || "").trim();
    const record=!text || text.startsWith("{") || text.startsWith("[") || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(text) || text.includes("::seed=") || /^(simple|async|query|import)-[0-9a-f]+$/i.test(text);
    visibility(node,["model"],!record);
    const model=find(node,"model");
    if(model)model.label="手动任务号对应模型";
    if(source){source.label="单独任务（可选，留空处理队列待办）";if(source.inputEl)source.inputEl.placeholder="通常留空：按queue_key处理尚未完成或尚未输出的任务。仅单独获取旧报告或平台任务号时填写。";}
    node.setSize?.([node.size?.[0] || 500,node.computeSize?.()[1] || 400]);
    node.setDirtyCanvas?.(true,true);
}

export function submissionTitle(mode,acknowledged,expected,referenceFailed=0){
 if(mode==='restored_existing')return 'CanvasPro · 复用旧批次（本次未新建）';
 if(!acknowledged && referenceFailed>0)return 'CanvasPro · 参考图上传失败（未提交生图）';
 if(!acknowledged)return 'CanvasPro · 未取得平台任务号，请查看报告';
 return `CanvasPro · 平台返回任务号 ${acknowledged}/${expected}（非生成完成）`;
}

export function applyExecutionStatus(node,message){
 const submission=message?.canvaspro_submission?.[0];
 const query=message?.canvaspro_query?.[0];
 if(submission)node.title=submissionTitle(submission.mode,submission.acknowledged,submission.expected,submission.reference_failed);
 else if(query){
  const c=query.counts || {};
  node.title=query.query_skipped?'CanvasPro · 提交阶段，未查询':`CanvasPro · 当前状态 | 排队 ${c.queued || 0} · 处理中 ${c.processing || 0} · 完成 ${c.succeeded || 0} · 失败 ${c.failed || 0} · 待确认 ${(c.submit_unknown || 0)+(c.unknown || 0)+(c.prepared || 0)+(c.sending || 0)}`;
  if(!query.query_skipped && Number.isInteger(query.progress) && query.progress>=0 && query.progress<=100)node.title+=` · 上游进度 ${query.progress}%`;
  if(!query.query_skipped && query.output_count!=null)node.title+=` · 本次出图 ${query.output_count} · 跳过历史 ${query.skipped || 0}`;
 }else return;
 node.setDirtyCanvas?.(true,true);
}
