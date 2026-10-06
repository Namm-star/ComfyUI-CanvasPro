"""Invoke an existing ComfyUI's real loader without installing into custom_nodes."""
import asyncio
import os
from pathlib import Path
import sys
import json
import tempfile
import threading

plugin = Path(__file__).resolve().parents[1]
comfy_root = Path(sys.argv[1]).resolve()
sys.argv = ["comfy_load_check", "--cpu"]
sys.path.insert(0, str(comfy_root))
os.chdir(comfy_root)
import comfy.options
comfy.options.enable_args_parsing()
import nodes

async def main():
    assert await nodes.load_custom_node(str(plugin))
    names = [name for name in nodes.NODE_CLASS_MAPPINGS if name.startswith("CanvasPro")]
    assert len(names) == 11, names
    for name in names:
        cls = nodes.NODE_CLASS_MAPPINGS[name]
        inputs = cls.INPUT_TYPES()
        assert "api_key" not in inputs.get("required", {})  # optional direct entry on batch node
        assert hasattr(cls, cls.FUNCTION)
        assert len(cls.RETURN_TYPES) == len(cls.RETURN_NAMES)
    print("REAL COMFYUI LOADER PASSED:", ", ".join(names))
    import execution
    for example in (plugin / "examples").glob("*api.json"):
        example_prompt = json.loads(example.read_text(encoding="utf-8"))
        valid, error, _, errors = await execution.validate_prompt("canvaspro-check", example_prompt, None)
        assert valid, (example.name, error, errors)
    prompt = json.loads((plugin / "examples/optimized-api.json").read_text(encoding="utf-8"))
    valid, error, outputs, errors = await execution.validate_prompt("canvaspro-check", prompt, None)
    assert valid, (error, errors)
    sys.path.insert(0, str(plugin / "tests"))
    from test_integration import Service
    service = Service()
    thread = threading.Thread(target=service.serve_forever, daemon=True)
    thread.start()
    with tempfile.TemporaryDirectory() as temp:
        os.environ.update(CANVASPRO_DATA_DIR=temp, CANVASPRO_API_KEY="fake-secret", CANVASPRO_BASE_URL=service.base, CANVASPRO_ALLOW_LOCAL_TEST="1")
        try:
            async def invoke(name, values):
                output, ui, subgraph, pending = await execution.get_output_data("canvaspro-check", name,
                    nodes.NODE_CLASS_MAPPINGS[name](), {k: [v] for k, v in values.items()})
                assert not subgraph and not pending
                return output
            first = await invoke("CanvasProPromptTask", prompt["5"]["inputs"])
            second = await invoke("CanvasProPromptTask", {**prompt["6"]["inputs"], "model":"T香蕉2"})
            fetched = await invoke("CanvasProBatchExecute", {"task_1":first[0][0], "task_2":second[0][0],
                "job_key":"real-mixed", "concurrency":3, "advanced":False, "wait_seconds":5})
            assert len(fetched[0]) == 2
            assert fetched[0][0].shape != fetched[0][1].shape
            import folder_paths
            original_output = folder_paths.get_output_directory()
            folder_paths.set_output_directory(str(Path(temp) / "output"))
            try:
                output, ui, _, _ = await execution.get_output_data("canvaspro-check", "save",
                    nodes.NODE_CLASS_MAPPINGS["SaveImage"](), {"images": fetched[0], "filename_prefix": ["mock"]})
                assert len(ui["images"]) == 2
            finally:
                folder_paths.set_output_directory(original_output)
            assert len(service.posts) == 2
            print("REAL COMFYUI VALIDATION + NODE LIST EXECUTION + SaveImage PASSED (2 differently sized images)")
        finally:
            service.shutdown()
            service.server_close()
            thread.join()

asyncio.run(main())
