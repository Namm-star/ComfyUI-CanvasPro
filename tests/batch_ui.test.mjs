import test from "node:test";
import assert from "node:assert/strict";
import { syncTaskPorts, syncTaskAdvanced, autoImageCount, migrateTaskDimensions, syncQueryUI, submissionTitle, applyExecutionStatus } from "../web/batch_ui.mjs";
const make = () => ({size:[300,200], inputs:[], widgets:["advanced","wait_seconds","request_timeout","reference_count","quality","reference_urls","model"].map(name=>({name,value:name==="model"?"gpt-image-2":false,type:"text",options:{},computeSize:()=>[200,20]})), addInput(name,type){this.inputs.push({name,type,link:null});}, removeInput(i){this.inputs.splice(i,1);},computeSize(){return [300,200];},setSize(s){this.size=s;},setDirtyCanvas(){}});
test("task ports grow beyond two and preserve sparse saved links",()=>{
    const n=make(); syncTaskPorts(n); assert.deepEqual(n.inputs.map(i=>i.name),["task_1","task_2"]);
    n.inputs[1].link=42; syncTaskPorts(n); assert.equal(n.inputs.at(-1).name,"task_3");
    n.addInput("task_8","CANVASPRO_TASKS"); n.inputs.at(-1).link=88; syncTaskPorts(n);
    assert.equal(n.inputs.find(i=>i.name==="task_8").link,88); assert.ok(n.inputs.some(i=>i.name==="task_9"));
});
test("port ceiling and disconnect pruning never remove linked ports",()=>{
    const n=make(); n.addInput("task_256","CANVASPRO_TASKS"); n.inputs[0].link=1; syncTaskPorts(n);
    assert.equal(n.inputs.length,256); assert.ok(!n.inputs.some(i=>i.name==="task_257"));
    n.inputs.find(i=>i.name==="task_256").link=null; syncTaskPorts(n); assert.equal(n.inputs.length,2);
});
test("advanced fields preserve values and follow model capability",()=>{
    const n=make(); const quality=n.widgets.find(w=>w.name==="quality"); quality.value="high";
    syncTaskAdvanced(n); assert.equal(quality.hidden,true); assert.equal(quality.value,"high");
    n.widgets.find(w=>w.name==="advanced").value=true; syncTaskAdvanced(n); assert.equal(quality.hidden,false);
    n.widgets.find(w=>w.name==="model").value="T香蕉2"; syncTaskAdvanced(n); assert.equal(quality.hidden,true);
    syncTaskPorts(n); assert.equal(n.widgets.find(w=>w.name==="wait_seconds").hidden,false);
});
test("image ports add a spare and stop at model limit",()=>{
    const n=make(); n.addInput("image_2","IMAGE"); n.inputs[0].link=3; autoImageCount(n);
    assert.equal(n.widgets.find(w=>w.name==="reference_count").value,3);
    n.widgets.find(w=>w.name==="model").value="T香蕉2"; n.addInput("image_14","IMAGE"); n.inputs.at(-1).link=9;
    autoImageCount(n); assert.equal(n.widgets.find(w=>w.name==="reference_count").value,14);
});


test("removed pixel widget migrates old dimensions without shifting other controls",()=>{
    const old=["gpt-image-2","prompt",2,"pixels","1536x1024","1:1","high","1K","",false];
    assert.deepEqual(migrateTaskDimensions(old),["gpt-image-2","prompt",2,"pixels","1:1","high","1K","",false,1536,1024]);
    assert.deepEqual(migrateTaskDimensions([...old,1280,720]).slice(-2),[1280,720]);
    const current=["gpt-image-2","prompt",2,"pixels","1:1","high","1K","",false,1280,720];
    assert.equal(migrateTaskDimensions(current),current);
});

test("sync timeout stays advanced and preserves configured wait",()=>{
 const n=make();n.widgets.push({name:'sync_timeout',value:900,type:'number',options:{}});
 syncTaskPorts(n);assert.equal(n.widgets.at(-1).hidden,true);
 n.widgets.find(w=>w.name==='advanced').value=true;syncTaskPorts(n);
 assert.equal(n.widgets.at(-1).hidden,false);assert.equal(n.widgets.at(-1).value,900);
});

test("queue query hides model and complete metadata; bare task IDs reveal only manual model",()=>{
 const n=make();n.widgets.push({name:'tasks_json',value:'',options:{},inputEl:{style:{}}});
 const source=n.widgets.at(-1),model=n.widgets.find(w=>w.name==='model');model.value='T香蕉2.1';
 for(const value of ['', '{"query":{"items":[{"model":"T香蕉2.1"},{"model":"gpt-image-2"}]}}','685778df-c714-4c2c-8ddc-993834db33e5','async-abcd::seed=123']){source.value=value;syncQueryUI(n);assert.equal(model.hidden,true);assert.equal(model.value,'T香蕉2.1');}
 source.value='';n.inputs.push({name:'tasks_json',link:123});syncQueryUI(n);assert.equal(model.hidden,true);
 source.value='task_abc\ntask_def';syncQueryUI(n);assert.equal(model.hidden,false);assert.equal(model.label,'手动任务号对应模型');
});

test("submission titles distinguish accepted, unconfirmed and restored",()=>{
 assert.match(submissionTitle('restored_existing',0,1),/本次未新建/);
 assert.match(submissionTitle('new_batch',0,1),/未取得平台任务号/);
 assert.match(submissionTitle('new_batch',0,1,1),/参考图上传失败.*未提交生图/);
 assert.match(submissionTitle('new_batch',1,2),/1\/2.*非生成完成/);
});


test('snapshot query hides legacy wait without shifting stored widgets',()=>{
 const n=make(),wait=n.widgets.find(w=>w.name==='wait_seconds');wait.value=600;
 n.widgets.push({name:'include_history',value:false});
 syncQueryUI(n);assert.equal(wait.hidden,true);assert.equal(wait.value,600);
 assert.equal(n.widgets.at(-1).label,'包含历史结果（会重复输出）');assert.equal(n.widgets.at(-1).value,false);
 assert.equal(n.widgets.find(w=>w.name==='request_timeout').label,'单次请求超时（秒）');
});

test('executed UI preserves unconfirmed submission and snapshot status titles',()=>{
 const n=make();applyExecutionStatus(n,{canvaspro_submission:[{mode:'new_batch',acknowledged:0,expected:1}]});
 assert.match(n.title,/未取得平台任务号/);
 applyExecutionStatus(n,{canvaspro_query:[{counts:{processing:2,succeeded:1,submit_unknown:1},output_count:1,skipped:10}]});
 assert.match(n.title,/处理中 2.*完成 1.*待确认 1/);
 assert.match(n.title,/本次出图 1.*跳过历史 10/);
 applyExecutionStatus(n,{canvaspro_query:[{query_skipped:true}]});assert.match(n.title,/未查询/);
});
