import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

let extension;
globalThis.canvasproTestApp = {registerExtension(value){extension=value;}};
globalThis.canvasproTestApi = {addEventListener(){}};
globalThis.window = {alert(){}};
const source = (await readFile(new URL("../web/canvaspro.js",import.meta.url),"utf8"))
    .replace('import { app } from "/scripts/app.js";','const app=globalThis.canvasproTestApp;')
    .replace('import { api } from "/scripts/api.js";','const api=globalThis.canvasproTestApi;')
    .replace('"./model_ui.mjs"',JSON.stringify(new URL("../web/model_ui.mjs",import.meta.url).href))
    .replace('"./batch_ui.mjs"',JSON.stringify(new URL("../web/batch_ui.mjs",import.meta.url).href));
await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
test("entry is self-contained and frontend definitions expose only two initial ports",async()=>{
    assert.doesNotMatch(source,/from\s+["']\.\//);
    for(const [name,prefix,max] of [["CanvasProPromptTask","image",16],["CanvasProBatchExecute","task",256]]) {
        class Node {}
        const optional=Object.fromEntries(Array.from({length:max},(_,i)=>[`${prefix}_${i+1}`,["IMAGE"]]));
        optional.width=["INT",{default:1024}];
        await extension.beforeRegisterNodeDef(Node,{name,input:{optional}});
        assert.deepEqual(Object.keys(optional),[`${prefix}_1`,`${prefix}_2`,"width"]);
    }
});
class Task {
    constructor(){
        const values={model:"gpt-image-2",reference_count:2,size_mode:"pixels",pixel_size:"1024x1024",aspect_ratio:"1:1",quality:"",image_size:"1K",reference_urls:"",advanced:false,width:1024,height:1024};
        this.widgets=Object.entries(values).map(([name,value])=>({name,value,type:"combo",options:{}}));
        this.inputs=Array.from({length:16},(_,i)=>({name:`image_${i+1}`,type:"IMAGE",link:null}));
        for(const name of ['model_input','width_input','height_input'])this.inputs.push({name,type:name==='model_input'?'STRING':'INT',link:null});
        this.size=[350,600];
    }
    addInput(name,type){this.inputs.push({name,type,link:null});this.onConnectionsChange?.();}
    removeInput(i){this.inputs.splice(i,1);this.onConnectionsChange?.();}
    computeSize(){return [350,300];} setSize(s){this.size=s;} setDirtyCanvas(){}
}
const widget=(n,name)=>n.widgets.find(w=>w.name===name);
test("registered task hooks grow ports, preserve load links and keep advanced hidden",async()=>{
    await extension.beforeRegisterNodeDef(Task,{name:"CanvasProPromptTask"});
    const n=new Task(); n.onNodeCreated(); await Promise.resolve(); await Promise.resolve();
    assert.equal(n.inputs.filter(i=>i.type==='IMAGE').length,2); assert.equal(widget(n,"quality").hidden,true);
    n.inputs[1].link=55; n.onConnectionsChange(); await Promise.resolve(); await Promise.resolve();
    assert.equal(n.inputs.filter(i=>i.type==='IMAGE').length,3); assert.equal(widget(n,"reference_count").value,3);
    widget(n,"advanced").value=true; widget(n,"advanced").callback(true); assert.equal(widget(n,"quality").hidden,false);
    widget(n,"model").value="T香蕉2"; widget(n,"model").callback("T香蕉2"); assert.equal(widget(n,"quality").hidden,true);
    n.onConfigure(); await Promise.resolve(); assert.equal(n.inputs.find(i=>i.name==="image_2").link,55);
    widget(n,"model").value="gpt-image-2"; widget(n,"model").callback("gpt-image-2");
    assert.equal(widget(n,"pixel_size").hidden,true);assert.equal(widget(n,"width").hidden,false);
});

test("wired parameter ports survive refresh and hide overridden widgets",async()=>{
    const n=new Task();n.onNodeCreated();await Promise.resolve();
    for(const name of ['model_input','width_input','height_input']) n.inputs.find(i=>i.name===name).link=100;
    n.onConnectionsChange();await Promise.resolve();await Promise.resolve();
    for(const name of ['model','width','height']) assert.equal(widget(n,name).hidden,true);
    assert.equal(widget(n,'image_size').hidden,false);
    assert.equal(n.inputs.filter(i=>/_input$/.test(i.name)).length,3);
    for(const i of n.inputs.filter(i=>/_input$/.test(i.name)))i.link=null;
    n.onConnectionsChange();await Promise.resolve();await Promise.resolve();
    for(const name of ['model','width','height']) assert.equal(widget(n,name).hidden,false);
});

test("AIStars registered task exposes URLs and model-specific tiers with temporary IMAGE ports",async()=>{
    const n=new Task();n.onNodeCreated();await Promise.resolve();
    widget(n,'model').value='即梦-65-seedream-5-lite';widget(n,'model').callback('即梦-65-seedream-5-lite');
    await Promise.resolve();await Promise.resolve();
    assert.equal(n.inputs.filter(i=>i.type==='IMAGE').length,2);
    assert.equal(widget(n,'reference_urls').hidden,false);
    assert.equal(widget(n,'width').hidden,true);assert.equal(widget(n,'height').hidden,true);
    assert.equal(widget(n,'quality').hidden,true);assert.equal(widget(n,'image_size').value,'2K');
});

test("batch key uses password DOM widget and retains parameter positions",async()=>{
    globalThis.document={createElement(){return {value:"",style:{}};}};
    class Batch extends Task {
        onNodeCreated(){} onConfigure(){} onConnectionsChange(){}
        constructor(){super();this.inputs=[{name:"task_1",type:"CANVASPRO_TASKS",link:null}];this.widgets=[['job_key','batch'],['concurrency',3],['advanced',false],['wait_seconds',600],['request_timeout',30],['api_key','test-key'],['seed',123],['control_after_generate','randomize']].map(([name,value])=>({name,value,type:'text',options:{}}));}
        addDOMWidget(name,type,input,options){const w={name,type,inputEl:input};Object.defineProperty(w,'value',{get:options.getValue,set:options.setValue});this.widgets.push(w);return w;}
    }
    await extension.beforeRegisterNodeDef(Batch,{name:"CanvasProBatchExecute"});
    const n=new Batch();n.onNodeCreated();await Promise.resolve();
    const key=widget(n,'api_key');assert.equal(key.inputEl.type,'password');assert.equal(key.value,'test-key');
    key.value='changed-key';assert.equal(key.inputEl.value,'changed-key');assert.equal(n.widgets[3].name,'wait_seconds');assert.equal(n.widgets[5].name,'api_key');
    assert.equal(n.widgets[6].name,'seed');assert.equal(n.widgets[6].value,123);assert.equal(n.widgets[7].value,'randomize');
    delete globalThis.document;
});

test("registered SR node shows numeric dimensions even after switching from Banana",async()=>{
 await extension.beforeRegisterNodeDef(Task,{name:'CanvasProPromptTask',input:{optional:{}}});
 const n=new Task(); n.onNodeCreated();
 for(const model of ['T香蕉2.1','gpt-image-2.6-SR']) {widget(n,'model').value=model;widget(n,'model').callback(model);}
 assert.equal(widget(n,'width').hidden,false);assert.equal(widget(n,'height').hidden,false);
 assert.equal(widget(n,'size_mode').hidden,true);assert.equal(widget(n,'image_size').hidden,true);
 assert.equal(widget(n,'reference_urls').hidden,true);
 widget(n,'advanced').value=true;widget(n,'advanced').callback(true);
 assert.equal(widget(n,'quality').hidden,false);assert(widget(n,'quality').options.values.includes('max'));
});

test("recovery node masks API key without needing task inputs",async()=>{
 globalThis.document={createElement:()=>({style:{}})};
 class Recovery {
  constructor(){this.widgets=[{name:'recovery',value:'batch-id'},{name:'api_key',value:'test-key'}];}
  addDOMWidget(name,type,input,options){const w={name,type,inputEl:input};Object.defineProperty(w,'value',{get:options.getValue,set:options.setValue});this.widgets.push(w);return w;}
 }
 await extension.beforeRegisterNodeDef(Recovery,{name:'CanvasProRecoverResults'});
 const n=new Recovery();n.onNodeCreated();assert.equal(widget(n,'api_key').inputEl.type,'password');assert.equal(widget(n,'recovery').value,'batch-id');
 delete globalThis.document;
});

test("simple generation has automatic image ports and model parameters",async()=>{
 class Simple extends Task{constructor(){super();for(const [name,value] of [['api_key',''],['seed',123],['count',2],['concurrency',3],['wait_seconds',600],['request_timeout',30],['sync_timeout',600]])this.widgets.push({name,value,type:'text',options:{}});}}
 const optional=Object.fromEntries(Array.from({length:16},(_,i)=>[`image_${i+1}`,['IMAGE']]));
 await extension.beforeRegisterNodeDef(Simple,{name:'CanvasProImageGenerate',input:{optional}});
 assert.deepEqual(Object.keys(optional),['image_1','image_2']);
 const n=new Simple();n.onNodeCreated();assert.equal(n.inputs.filter(i=>i.type==='IMAGE').length,2);assert.equal(widget(n,'concurrency').hidden,true);assert.equal(widget(n,'count').value,2);
 widget(n,'model').value='T香蕉2.1';widget(n,'model').callback('T香蕉2.1');assert.equal(widget(n,'width').hidden,true);assert.equal(widget(n,'image_size').hidden,false);
 widget(n,'advanced').value=true;widget(n,'advanced').callback(true);assert.equal(widget(n,'concurrency').hidden,false);
});

test("simple generation masks direct CanvasPro key",async()=>{
 globalThis.document={createElement:()=>({style:{}})};
 class Simple extends Task{constructor(){super();this.widgets.push({name:'api_key',value:'simple-test-key',options:{}});}
 addDOMWidget(name,type,input,options){const w={name,type,inputEl:input};Object.defineProperty(w,'value',{get:options.getValue,set:options.setValue});this.widgets.push(w);return w;}}
 await extension.beforeRegisterNodeDef(Simple,{name:'CanvasProImageGenerate',input:{optional:{}}});
 const n=new Simple();n.onNodeCreated();assert.equal(widget(n,'api_key').inputEl.type,'password');assert.equal(widget(n,'api_key').value,'simple-test-key');
 delete globalThis.document;
});

test("async submit gets simple reference ports",async()=>{
 class Submit extends Task{}
 const optional=Object.fromEntries(Array.from({length:16},(_,i)=>[`image_${i+1}`,['IMAGE']]));
 await extension.beforeRegisterNodeDef(Submit,{name:'CanvasProAsyncSubmit',input:{optional}});
 assert.deepEqual(Object.keys(optional),['image_1','image_2']);const n=new Submit();n.onNodeCreated();assert.equal(n.inputs.filter(i=>i.type==='IMAGE').length,2);
});

test("async query masks key independently of submission",async()=>{
 globalThis.document={createElement:()=>({style:{}})};
 class Query{constructor(){this.widgets=[{name:'queue_key',value:'queue-001'},{name:'api_key',value:'test-key'}];}addDOMWidget(name,type,input,options){const w={name,type,inputEl:input};Object.defineProperty(w,'value',{get:options.getValue,set:options.setValue});this.widgets.push(w);return w;}}
 await extension.beforeRegisterNodeDef(Query,{name:'CanvasProAsyncQuery'});const n=new Query();n.onNodeCreated();assert.equal(widget(n,'api_key').inputEl.type,'password');delete globalThis.document;
});

test("registered queue query hides misleading model after creation, edits and reload",async()=>{
 class Query extends Task{constructor(){super();this.widgets.push({name:'tasks_json',value:'',options:{}});}}
 await extension.beforeRegisterNodeDef(Query,{name:'CanvasProAsyncQuery'});const n=new Query();n.onNodeCreated();assert.equal(widget(n,'model').hidden,true);
 const text=widget(n,'tasks_json');text.value='task_123';text.callback('task_123');assert.equal(widget(n,'model').hidden,false);
 text.value='{"batch_id":"123"}';text.callback(text.value);assert.equal(widget(n,'model').hidden,true);
 text.value='';n.onConfigure({});assert.equal(widget(n,'model').hidden,true);
});
