import test from "node:test";
import assert from "node:assert/strict";
import { syncTaskPorts, syncTaskAdvanced, autoImageCount, migrateTaskDimensions } from "../web/batch_ui.mjs";
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
