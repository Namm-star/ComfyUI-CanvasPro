import test from "node:test";
import assert from "node:assert/strict";
import { installModelUI, restoreModelUI } from "../web/model_ui.mjs";

function fixture() {
    const values = { model: "gpt-image-2", reference_count: 2, size_mode: "pixels", pixel_size: "1024x1024", aspect_ratio: "1:1", quality: "", image_size: "1K", reference_urls: "" };
    return {
        widgets: Object.entries(values).map(([name, value]) => ({ name, value, type: "combo", options: {}, inputEl: { style: {} } })),
        inputs: Array.from({length: 16}, (_, i) => ({name: `image_${i+1}`, type: "IMAGE", link: null})),
        size: [350, 600], addInput(name, type) { this.inputs.push({name, type, link: null}); },
        removeInput(index) { this.inputs.splice(index, 1); },
        computeSize() { return [350, 300 + this.inputs.length*20]; },
        setSize(size) { this.size = size; }, setDirtyCanvas() {},
    };
}
const widget = (n, name) => n.widgets.find(w => w.name === name);
function change(n, name, value) { const w = widget(n, name); w.value = value; w.callback?.(value); }
const shown = (n, name) => !widget(n, name).hidden;

test("Banana 2.1 uses ratio/tier controls and fourteen reference ports",()=>{
    const n=fixture(); installModelUI(n,()=>{});
    change(n,'model','T香蕉2.1');
    assert(shown(n,'aspect_ratio'));assert(shown(n,'image_size'));
    for(const name of ['quality','reference_urls','size_mode','pixel_size'])assert(!shown(n,name));
    change(n,'reference_count',16);
    assert.equal(n.inputs.length,14);
});

test("URL references must be cleared before switching to Banana", () => {
    const n=fixture(); installModelUI(n,()=>{});
    widget(n,"reference_urls").value="https://example.com/reference.png";
    change(n,"model","T香蕉2");
    assert.equal(widget(n,"model").value,"gpt-image-2");
    assert.equal(widget(n,"reference_urls").value,"https://example.com/reference.png");
});

test("model parameters, quality choices and reference port ceilings", () => {
    const n=fixture(); installModelUI(n, ()=>{});
    assert.deepEqual(n.inputs.map(i=>i.name), ["image_1", "image_2"]);
    assert(shown(n,"pixel_size")); assert(!shown(n,"image_size"));
    change(n,"size_mode","ratio");
    assert(!shown(n,"pixel_size")); assert(shown(n,"aspect_ratio")); assert(shown(n,"image_size"));
    change(n,"model","T香蕉pro");
    assert(!shown(n,"quality")); assert(!shown(n,"reference_urls")); assert(!shown(n,"size_mode"));
    assert(shown(n,"aspect_ratio")); assert(shown(n,"image_size"));
    assert.equal(widget(n,"reference_count").options.max,14);
    change(n,"reference_count",16); assert.equal(n.inputs.length,14);
    change(n,"model","s-gpt-image-2.5-flare");
    assert.equal(widget(n,"reference_count").options.max,15);
    assert(shown(n,"quality")); assert(shown(n,"pixel_size")); assert(!shown(n,"image_size"));
    assert(widget(n,"quality").options.values.includes("max"));
    change(n,"quality","max"); change(n,"model","gpt-image-2");
    assert.equal(widget(n,"quality").value,"");
    assert(!widget(n,"quality").options.values.includes("max"));
});

test("changing model or count never silently disconnects a linked image", () => {
    const n=fixture(), messages=[]; installModelUI(n,m=>messages.push(m));
    change(n,"reference_count",16); n.inputs[15].link=123;
    change(n,"model","T香蕉2");
    assert.equal(widget(n,"model").value,"gpt-image-2");
    assert.equal(n.inputs[15].link,123); assert.equal(n.inputs.length,16);
    change(n,"reference_count",2);
    assert.equal(widget(n,"reference_count").value,16); assert.equal(messages.length,2);
});

test("reload restores saved selection, count, links and widget values", () => {
    const n=fixture(); installModelUI(n,()=>{});
    widget(n,"model").value="T香蕉2"; widget(n,"reference_count").value=4;
    widget(n,"aspect_ratio").value="16:9"; restoreModelUI(n,()=>{});
    n.inputs[1].link=45;
    assert.equal(n.inputs.length,4); assert.equal(widget(n,"aspect_ratio").value,"16:9");
    change(n,"model","gpt-image-2"); change(n,"reference_count",1);
    assert.equal(widget(n,"reference_count").value,4); assert.equal(n.inputs[1].link,45);
});

test("incompatible connected parameter blocks model switch", () => {
    const n=fixture(); installModelUI(n,()=>{});
    n.inputs.push({name:"quality",type:"STRING",link:777});
    change(n,"model","T香蕉2");
    assert.equal(widget(n,"model").value,"gpt-image-2");
    assert.equal(n.inputs.find(i=>i.name==="quality").link,777);
});


test("numeric dimension nodes never reveal legacy pixel size on model refresh", () => {
    const n=fixture();
    for(const name of ["width","height"]) n.widgets.push({name,value:1024,type:"number",options:{}});
    installModelUI(n,()=>{});
    assert(!shown(n,"pixel_size")); assert(shown(n,"width"));
    change(n,"model","s-gpt-image-2");
    assert(!shown(n,"pixel_size")); assert(shown(n,"width")); assert(shown(n,"height"));
    restoreModelUI(n,()=>{}); assert(!shown(n,"pixel_size"));
    change(n,"model","T香蕉2"); assert(!shown(n,"width")); assert(!shown(n,"pixel_size"));
    change(n,"model","gpt-image-2"); change(n,"size_mode","ratio");
    assert(!shown(n,"pixel_size")); assert(!shown(n,"width"));
});
