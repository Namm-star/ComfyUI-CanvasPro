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
class Task {
    constructor(){
        const values={model:"gpt-image-2",reference_count:2,size_mode:"pixels",pixel_size:"1024x1024",aspect_ratio:"1:1",quality:"",image_size:"1K",reference_urls:"",advanced:false};
        this.widgets=Object.entries(values).map(([name,value])=>({name,value,type:"combo",options:{}}));
        this.inputs=Array.from({length:16},(_,i)=>({name:`image_${i+1}`,type:"IMAGE",link:null})); this.size=[350,600];
    }
    addInput(name,type){this.inputs.push({name,type,link:null});this.onConnectionsChange?.();}
    removeInput(i){this.inputs.splice(i,1);this.onConnectionsChange?.();}
    computeSize(){return [350,300];} setSize(s){this.size=s;} setDirtyCanvas(){}
}
const widget=(n,name)=>n.widgets.find(w=>w.name===name);
test("registered task hooks grow ports, preserve load links and keep advanced hidden",async()=>{
    await extension.beforeRegisterNodeDef(Task,{name:"CanvasProPromptTask"});
    const n=new Task(); n.onNodeCreated(); await Promise.resolve(); await Promise.resolve();
    assert.equal(n.inputs.length,2); assert.equal(widget(n,"quality").hidden,true);
    n.inputs[1].link=55; n.onConnectionsChange(); await Promise.resolve(); await Promise.resolve();
    assert.equal(n.inputs.length,3); assert.equal(widget(n,"reference_count").value,3);
    widget(n,"advanced").value=true; widget(n,"advanced").callback(true); assert.equal(widget(n,"quality").hidden,false);
    widget(n,"model").value="T香蕉2"; widget(n,"model").callback("T香蕉2"); assert.equal(widget(n,"quality").hidden,true);
    n.onConfigure(); await Promise.resolve(); assert.equal(n.inputs.find(i=>i.name==="image_2").link,55);
});
