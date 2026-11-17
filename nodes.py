import hashlib
import io
import json
import time
import numpy as np
import torch
from PIL import Image, ImageOps
from .config import settings
from .client import Client, ClientError
from .store import Store
from .protocol import MODELS, family, reference_limit, IMAGE_MODELS
from .batch import submit_batch, submit_tasks, query_batch, run_parallel, report


def image_output(images):
    if images:
        return images
    try:
        from comfy_execution.graph_utils import ExecutionBlocker
    except ImportError:
        from comfy_execution.graph import ExecutionBlocker
    # Never pass [] into ComfyUI list mapping: it indexes the final element.
    # Block only IMAGE consumers; report and task handles must still execute.
    return [ExecutionBlocker(None)]


def runtime(timeout=30, api_key=""):
    base, key = settings(api_key)
    return Store(), Client(base, key, timeout)


def interrupt():
    import comfy.model_management
    comfy.model_management.throw_exception_if_processing_interrupted()


def progress():
    from comfy.utils import ProgressBar
    bar = ProgressBar(1)
    return lambda n, total: bar.update_absolute(n, total)


def encode_images(images):
    if images is None:
        return []
    if images.ndim != 4 or images.shape[-1] not in (3, 4) or images.shape[0] > 256:
        raise ValueError("Expected IMAGE batch with 3/4 channels and <=256 images")
    result = []
    for tensor in images:
        array = (tensor.detach().cpu().numpy().clip(0, 1) * 255).round().astype(np.uint8)
        buffer = io.BytesIO()
        Image.fromarray(array).save(buffer, format="PNG")
        result.append(buffer.getvalue())
    return result


class Submit:
    CATEGORY = "CanvasPro"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("tasks_json", "report")
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "job_key": ("STRING", {"default": "batch-001", "tooltip": "Same key restores the original batch. Change key ONLY for a new paid batch."}),
            "model": (list(MODELS),),
            "prompts": ("STRING", {"multiline": True, "default": "一只蓝色小鸟\n一只橙色小猫", "tooltip": "One prompt per nonempty line; or a JSON string array for multiline prompts."}),
            "size": ("STRING", {"default": "", "tooltip": "KR/HC: pixel dimensions; Banana: 1:1/3:4/4:3/9:16/16:9. Blank omits field."}),
            "quality": (["", "auto", "low", "medium", "high", "xhigh", "max"],),
            "image_size": (["", "1K", "2K", "4K"],),
            "reference_mode": (["shared", "paired"],),
            "concurrency": ("INT", {"default": 3, "min": 1, "max": 8}),
            "request_timeout": ("INT", {"default": 30, "min": 1, "max": 120})},
            "optional": {"images": ("IMAGE",), "reference_urls": ("STRING", {"multiline": True, "default": ""})}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def execute(self, job_key, model, prompts, size, quality, image_size, reference_mode, concurrency, request_timeout, images=None, reference_urls=""):
        values = json.loads(prompts) if prompts.lstrip().startswith("[") else [s.strip() for s in prompts.splitlines() if s.strip()]
        if not isinstance(values, list) or any(not isinstance(s, str) for s in values):
            raise ValueError("Prompts must be a JSON string array or nonempty lines")
        store, client = runtime(request_timeout)
        batch = submit_batch(store, client, job_key, model, values, size, quality, image_size,
            encode_images(images), [s.strip() for s in reference_urls.splitlines() if s.strip()],
            reference_mode, concurrency, interrupt, progress())
        return {"ui": {"text": [report(store, batch)]}, "result": (store.handle(batch), report(store, batch))}


class ModelSubmit(Submit):
    """Model-aware UI, separate image tensors; old Submit remains compatible."""
    @classmethod
    def INPUT_TYPES(cls):
        common = Submit.INPUT_TYPES()["required"]
        required = {k: common[k] for k in ("job_key", "model", "prompts", "reference_mode", "concurrency", "request_timeout")}
        optional = {
            "reference_count": ("INT", {"default": 2, "min": 1, "max": 16}),
            "size_mode": (["pixels", "ratio", "auto"],),
            "pixel_size": ("STRING", {"default": "1024x1024"}),
            "aspect_ratio": (list(dict.fromkeys(r for rs in IMAGE_MODELS["banana_ratios"].values() for r in rs)),),
            "quality": (["", "auto", "low", "medium", "high", "xhigh", "max"],),
            "image_size": (["1K", "2K", "4K"],),
            "reference_urls": ("STRING", {"multiline": True, "default": ""})}
        optional.update({f"image_{i}": ("IMAGE",) for i in range(1, 17)})
        return {"required": required, "optional": optional}

    def execute(self, job_key, model, prompts, reference_mode, concurrency, request_timeout,
                reference_count=2, size_mode="pixels", pixel_size="1024x1024", aspect_ratio="1:1",
                quality="", image_size="1K", reference_urls="", **images):
        f = family(model)
        maximum = reference_limit(model)
        if not 1 <= reference_count <= maximum:
            raise ValueError(f"Selected model supports at most {maximum} reference ports")
        files = []
        for i in range(1, 17):
            image = images.get(f"image_{i}")
            if image is not None:
                if i > reference_count:
                    raise ValueError("Connected image exceeds active reference_count/model limit")
                files.extend(encode_images(image))
        if f == "aistars":
            size, quality = aspect_ratio, ""
        elif f == "gemini":
            if reference_urls.strip():
                raise ValueError("Banana requires image ports; URL references unsupported")
            size, quality, image_size = aspect_ratio, "", image_size
        elif f in ("kr25","sync") and size_mode == "auto":
            size,image_size="auto",""
        elif f in ("hc", "sync","kr25"):
            size, image_size = pixel_size, ""
        elif size_mode == "pixels":
            size, image_size = pixel_size, ""
        elif size_mode == "ratio":
            size = aspect_ratio
        elif size_mode == "auto":
            size, image_size = "auto", ""
        else:
            raise ValueError("Invalid size mode")
        values = json.loads(prompts) if prompts.lstrip().startswith("[") else [s.strip() for s in prompts.splitlines() if s.strip()]
        if not isinstance(values, list) or any(not isinstance(s, str) for s in values):
            raise ValueError("Prompts must be a string array or nonempty lines")
        store, client = runtime(request_timeout)
        batch = submit_batch(store, client, job_key, model, values, size, quality, image_size,
            files, [s.strip() for s in reference_urls.splitlines() if s.strip()], reference_mode,
            concurrency, interrupt, progress())
        return {"ui": {"text": [report(store, batch)]}, "result": (store.handle(batch), report(store, batch))}


class PromptTask(ModelSubmit):
    OUTPUT_NODE = False
    RETURN_TYPES = ("CANVASPRO_TASKS",)
    RETURN_NAMES = ("tasks",)

    @classmethod
    def INPUT_TYPES(cls):
        schema = ModelSubmit.INPUT_TYPES()
        schema["optional"].pop("pixel_size")
        schema["required"] = {"model": schema["required"]["model"],
            "prompt": ("STRING", {"multiline": True, "default": "", "tooltip": "One complete task; all line breaks are preserved."})}
        schema["optional"]["advanced"] = ("BOOLEAN", {"default": False})
        note = "像素模式：1K 正方形填 1024×1024；2K 正方形填 2048×2048；4K 横图可填 3840×2160，竖图填 2160×3840。GPT 宽高须为16倍数、单边≤3840、总像素≤8294400；不能填4096×4096。比例模式可直接选1K/2K/4K。"
        schema["optional"]["width"] = ("INT", {"default": 1024, "min": 1, "max": 32768, "tooltip": "宽度（像素）。" + note})
        schema["optional"]["height"] = ("INT", {"default": 1024, "min": 1, "max": 32768, "tooltip": "高度（像素）。" + note})
        schema["optional"]["model_input"] = ("STRING", {"forceInput": True, "tooltip": "连接上游 STRING 模型名称，优先于 model 下拉；支持本插件已有模型。"})
        schema["optional"]["width_input"] = ("INT", {"forceInput": True, "tooltip": "连接上游 INT 宽度，优先于手填 width；像素模式生效。"})
        schema["optional"]["height_input"] = ("INT", {"forceInput": True, "tooltip": "连接上游 INT 高度，优先于手填 height；像素模式生效。"})
        return schema

    def execute(self, model, prompt, reference_count=2, size_mode="pixels", pixel_size="1024x1024",
                aspect_ratio="1:1", quality="", image_size="1K", reference_urls="", advanced=False, width=None, height=None,
                model_input=None, width_input=None, height_input=None, **images):
        if model_input is not None:
            if not isinstance(model_input, str) or not model_input.strip():
                raise ValueError("model_input 必须是非空模型名称字符串")
            model = model_input.strip()
        if width_input is not None or height_input is not None:
            for name, value in (("width_input", width_input), ("height_input", height_input)):
                if value is not None and (type(value) is not int or value <= 0):
                    raise ValueError(f"{name} 必须是正整数像素值")
            # A single connected dimension can use the manual value of its peer.
            if width is None or height is None:
                pieces = pixel_size.split("x")
                if len(pieces) != 2 or not all(p.isdigit() for p in pieces):
                    raise ValueError("请为未连接的一边填写整数宽高")
                if width is None:
                    width = int(pieces[0])
                if height is None:
                    height = int(pieces[1])
            width = width_input if width_input is not None else width
            height = height_input if height_input is not None else height
        if width is not None or height is not None:
            if width is None or height is None or type(width) is not int or type(height) is not int:
                raise ValueError("Width and height must both be integer pixel values")
            pixel_size = f"{width}x{height}"
        maximum = reference_limit(model)
        if not 1 <= reference_count <= maximum:
            raise ValueError("Reference count exceeds model limit")
        files = []
        for i in range(1, 17):
            image = images.get(f"image_{i}")
            if image is not None:
                if i > reference_count:
                    raise ValueError("Connected image exceeds active reference count")
                files.extend(encode_images(image))
        f = family(model)
        if f in ("gemini", "aistars"):
            size, quality = aspect_ratio, ""
        elif f in ("kr25","sync") and size_mode == "auto":
            size,image_size="auto",""
        elif f in ("hc", "sync","kr25") or size_mode == "pixels":
            size, image_size = pixel_size, ""
        elif size_mode == "ratio":
            size = aspect_ratio
        elif size_mode == "auto":
            size, image_size = "auto", ""
        else:
            raise ValueError("Invalid size mode")
        item = dict(model=model, prompt=prompt, size=size, quality=quality, image_size=image_size,
                    files=files, urls=[s.strip() for s in reference_urls.splitlines() if s.strip()])
        from .protocol import build_request
        build_request(model, prompt, size, quality, image_size, files, item["urls"], defer_upload=True)
        return ([item],)


class MergeTasks:
    CATEGORY = "CanvasPro"
    FUNCTION = "execute"
    RETURN_TYPES = ("CANVASPRO_TASKS",)
    RETURN_NAMES = ("tasks",)

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"tasks_a": ("CANVASPRO_TASKS",), "tasks_b": ("CANVASPRO_TASKS",)}}

    def execute(self, tasks_a, tasks_b):
        items = tasks_a + tasks_b
        if len(items) > 256:
            raise ValueError("Batch supports at most 256 tasks")
        if len({item["model"] for item in items}) != 1:
            raise ValueError("Use separate submission nodes for different models")
        return (items,)


class SubmitTasks(Submit):
    @classmethod
    def INPUT_TYPES(cls):
        common = Submit.INPUT_TYPES()["required"]
        return {"required": {"tasks": ("CANVASPRO_TASKS",), **{k: common[k]
            for k in ("job_key", "concurrency", "request_timeout")}}}

    def execute(self, tasks, job_key, concurrency, request_timeout):
        if not tasks or len(tasks) > 256 or len({item["model"] for item in tasks}) != 1:
            raise ValueError("Expected 1-256 tasks using the same model")
        store, client = runtime(request_timeout)
        batch = submit_batch(store, client, job_key, tasks[0]["model"], [item["prompt"] for item in tasks],
            concurrency=concurrency, interrupt=interrupt, progress=progress(), task_items=tasks)
        return {"ui": {"text": [report(store, batch)]}, "result": (store.handle(batch), report(store, batch))}


class Wait:
    CATEGORY = "CanvasPro"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("tasks_json", "report")
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"tasks_json": ("STRING", {"multiline": True, "forceInput": True}),
            "wait_seconds": ("INT", {"default": 600, "min": 0, "max": 86400, "tooltip": "0: one query per task. Timeout never resubmits."}),
            "poll_interval": ("FLOAT", {"default": 2, "min": 0.2, "max": 60}),
            "concurrency": ("INT", {"default": 3, "min": 1, "max": 8}),
            "request_timeout": ("INT", {"default": 30, "min": 1, "max": 120})}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def execute(self, tasks_json, wait_seconds, poll_interval, concurrency, request_timeout):
        store, client = runtime(request_timeout)
        batch = store.resolve(tasks_json)
        query_batch(store, client, batch, wait_seconds, poll_interval, concurrency, interrupt, progress())
        return {"ui": {"text": [report(store, batch)]}, "result": (store.handle(batch), report(store, batch))}


class Fetch:
    CATEGORY = "CanvasPro"
    FUNCTION = "execute"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "download_report")
    OUTPUT_IS_LIST = (True, False)
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"tasks_json": ("STRING", {"forceInput": True}),
            "concurrency": ("INT", {"default": 3, "min": 1, "max": 8}),
            "request_timeout": ("INT", {"default": 30, "min": 1, "max": 120})}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def execute(self, tasks_json, concurrency, request_timeout, api_key="", positions=None):
        store, client = runtime(request_timeout, api_key) if api_key else runtime(request_timeout)
        batch = store.resolve(tasks_json)
        meta, tasks = store.read(batch,positions=positions)
        if meta["base"] != client.base:
            raise ValueError("Saved task service differs from current settings")
        results, details = {}, {}
        def worker(task, cancel):
            index = task["position"]
            if cancel.is_set():
                details[index] = {"index": index, "status": "download_cancelled"}
                return
            if task["status"] != "succeeded":
                details[index] = {"index": index, "status": task["status"], "detail": task["detail"]}
                return
            tensors = []
            try:
                if task.get("image") is not None:
                    blobs = [task["image"]]
                else:
                    blobs = (client.download(url, authorize=not task["model"].endswith("-W")) for url in task["urls"])
                for blob in blobs:
                    if cancel.is_set():
                        raise ClientError("download_cancelled")
                    with Image.open(io.BytesIO(blob)) as im:
                        im = ImageOps.exif_transpose(im).convert("RGB")
                        tensor = torch.from_numpy(np.array(im).astype(np.float32) / 255.0).unsqueeze(0)
                    if task.get("image") is None:
                        store.update(batch,index,image=blob)
                    tensors.append(tensor)
                results[index] = tensors
                details[index] = {"index": index, "status": "downloaded", "sizes": [[t.shape[2], t.shape[1]] for t in tensors]}
            except ClientError as error:
                details[index] = {"index": index, "status": "download_failed", "detail": str(error)}
            except Exception:
                details[index] = {"index": index, "status": "download_failed", "detail": "invalid_image_or_local_decode_error"}
        run_parallel(tasks, worker, concurrency, interrupt, progress())
        resources={item["index"]:item for item in store.resources(batch,positions=positions)}
        for index,detail in details.items():detail.update(resources[index])
        images = [tensor for index in sorted(results) for tensor in results[index]]
        info = json.dumps({"batch_id": batch, "items": [details[i] for i in sorted(details)],
            "output_indices": [i for i in sorted(results) for _ in results[i]], "no_images": not images}, ensure_ascii=False)
        return {"ui": {"text": [info]}, "result": (image_output(images), info)}


class WaitFetch(Fetch):
    RETURN_NAMES = ("images", "report")

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"tasks_json": ("STRING", {"forceInput": True}),
            "wait_seconds": ("INT", {"default": 600, "min": 0, "max": 86400,
                "tooltip": "Maximum wait in seconds. Run again to continue querying the same tasks; no resubmission."})}}

    def execute(self, tasks_json, wait_seconds=600):
        waited = Wait().execute(tasks_json, wait_seconds, 2.0, 3, 30)
        handle, query_report = waited["result"]
        fetched = Fetch().execute(handle, 3, 30)
        images, download_report = fetched["result"]
        info = json.dumps({"query": json.loads(query_report), "download": json.loads(download_report)}, ensure_ascii=False)
        return {"ui": {"text": [info]}, "result": (images, info)}


class BatchExecute(Fetch):
    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("images", "report", "tasks_json")
    OUTPUT_IS_LIST = (True, False, False)

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "task_1": ("CANVASPRO_TASKS",),
            "job_key": ("STRING", {"default": "batch-001", "tooltip": "批次名称。名称 + seed 标识同一批任务；修改任务后更换 seed。"}),
            "concurrency": ("INT", {"default": 3, "min": 1, "max": 8}),
            "advanced": ("BOOLEAN", {"default": False})},
            "optional": {"wait_seconds": ("INT", {"default": 600, "min": 0, "max": 86400}),
                "request_timeout": ("INT", {"default": 30, "min": 1, "max": 120}),
                "api_key": ("STRING", {"default": "", "multiline": False, "tooltip": "Enter your CanvasPro API Key here. Saved workflows may contain it; remove before sharing."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 9007199254740991, "control_after_generate": True, "tooltip": "批次种子：fixed 保持同一批次，randomize 每次生成新批次（正常计费）；也可 increment/decrement。仅用于区分批次，不是模型的图像随机种子。"}),
                "sync_timeout": ("INT", {"default":600,"min":1,"max":3600,"tooltip":"同步图片请求等待秒数，默认600。超时不自动重新提交。异步查询使用wait_seconds。"}),
                **{f"task_{i}": ("CANVASPRO_TASKS",) for i in range(2, 257)}},
            "hidden": {"unique_id": "UNIQUE_ID"}}

    def execute(self, task_1, job_key, concurrency=3, advanced=False, wait_seconds=600, request_timeout=30, unique_id=None, api_key="", seed=None, imgbb_api_key="", sync_timeout=600, **ports):
        if type(sync_timeout) is not int or not 1 <= sync_timeout <= 3600:
            raise ValueError("sync_timeout must be 1-3600 seconds")
        original_job_key = job_key
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 9007199254740991:
                raise ValueError("批次 seed 必须是 0 到 9007199254740991 之间的整数")
            job_key = f"{job_key}::seed={seed}"
        items = list(task_1)
        for i in range(2, 257):
            if ports.get(f"task_{i}") is not None:
                items.extend(ports[f"task_{i}"])
        store, client = runtime(request_timeout, api_key) if api_key else runtime(request_timeout)
        client.sync_timeout = sync_timeout
        submission={}
        phase = "提交"
        last_sent, last_check = None, 0.0
        def publish():
            nonlocal last_sent, last_check
            if unique_id is None or time.monotonic() - last_check < 0.5:
                return
            last_check = time.monotonic()
            try:
                saved = store.by_key(job_key)
            except ValueError:
                return
            counts = json.loads(report(store, saved))["counts"]
            payload = {"node_id": str(unique_id), "phase": phase, "counts": counts,"submission_mode":submission.get("mode")}
            if payload == last_sent:
                return
            try:
                from server import PromptServer
                PromptServer.instance.send_sync("canvaspro.batch_status", payload)
                last_sent = payload
            except (ImportError, AttributeError, RuntimeError):
                pass
        def check():
            interrupt()
            publish()
        try:
            batch = submit_tasks(store, client, job_key, items, concurrency, check, progress(), imgbb_api_key=imgbb_api_key,run_info=submission)
        except ValueError as error:
            if "job_key already belongs to different inputs" in str(error):
                raise ValueError("该批次名称和 seed 已用于其他输入。请修改 seed，或将生成后控制设为 randomize 后修改 seed，再运行以创建新批次。") from None
            raise
        phase, last_check = "等待", 0.0
        publish()
        query_batch(store, client, batch, wait_seconds, 2.0, concurrency, check, progress())
        phase, last_check = "下载", 0.0
        publish()
        handle = store.handle(batch)
        fetched = Fetch().execute(handle, concurrency, request_timeout, api_key)
        phase, last_check = "本轮结束", 0.0
        publish()
        images, download_report = fetched["result"]
        handle=store.handle(batch)
        info = json.dumps({"submission":submission,"job_key": original_job_key, "seed": seed, "effective_job_key": job_key,
            "query": json.loads(report(store, batch)), "download": json.loads(download_report),
            "guidance": "未取得可保存图片，已跳过保存。结果未知时请核对平台记录，不要自动更换seed重提；已有URL或缓存时保持原job_key和seed，设为fixed再运行可只重试下载。" if json.loads(download_report).get("no_images") else ""}, ensure_ascii=False)
        return {"ui": {"text": [info]}, "result": (images, info, handle)}


class Restore:
    CATEGORY = "CanvasPro"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("tasks_json", "report")
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"job_key": ("STRING", {"default": "batch-001"})}}
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")
    def execute(self, job_key):
        store = Store()
        batch = store.by_key(job_key)
        return store.handle(batch), report(store, batch)


class ImportTasks:
    CATEGORY = "CanvasPro"
    FUNCTION = "execute"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("tasks_json", "report")
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": (list(MODELS),), "task_ids": ("STRING", {"multiline": True})}}
    def execute(self, model, task_ids):
        family(model)
        ids = [s.strip() for s in task_ids.splitlines() if s.strip()]
        if not ids or len(ids) > 256 or any(len(s) > 256 for s in ids):
            raise ValueError("Expected 1-256 existing task IDs")
        store, client = runtime()
        if any(client.key in s or any(c.isspace() for c in s) for s in ids):
            raise ValueError("Invalid task ID")
        fingerprint = hashlib.sha256(json.dumps([client.base, model, ids]).encode()).hexdigest()
        batch, created = store.create("import-" + fingerprint, fingerprint, client.base, model, len(ids))
        # Finish local imports interrupted during a previous process; no HTTP.
        for task in store.read(batch)[1]:
            if not task["task_id"]:
                i = task["position"]
                store.update(batch, i, status="queued", task_id=ids[i])
        return store.handle(batch), report(store, batch)


NODE_CLASS_MAPPINGS = {"CanvasProBatchSubmit": Submit, "CanvasProBatchWait": Wait,
    "CanvasProBatchFetch": Fetch, "CanvasProRestoreBatch": Restore, "CanvasProImportTasks": ImportTasks,
    "CanvasProModelBatchSubmit": ModelSubmit}
NODE_DISPLAY_NAME_MAPPINGS = {"CanvasProBatchSubmit": "CanvasPro · 批量提交 (新批次收费)",
    "CanvasProBatchWait": "CanvasPro · 批量查询 / 等待", "CanvasProBatchFetch": "CanvasPro · 批量获取图片",
    "CanvasProRestoreBatch": "CanvasPro · 恢复本地批次", "CanvasProImportTasks": "CanvasPro · 导入已有任务号",
    "CanvasProModelBatchSubmit": "CanvasPro · 模型自适应 / 多图批量提交"}

NODE_CLASS_MAPPINGS.update(CanvasProPromptTask=PromptTask, CanvasProMergeTasks=MergeTasks, CanvasProSubmitTasks=SubmitTasks)
NODE_DISPLAY_NAME_MAPPINGS.update(CanvasProPromptTask="CanvasPro · 独立任务 / 完整提示词",
    CanvasProMergeTasks="CanvasPro · 合并任务", CanvasProSubmitTasks="CanvasPro · 任务并发提交 (新批次收费)")

NODE_CLASS_MAPPINGS["CanvasProWaitFetch"] = WaitFetch
NODE_DISPLAY_NAME_MAPPINGS["CanvasProWaitFetch"] = "CanvasPro · 等待并获取图片"

NODE_CLASS_MAPPINGS["CanvasProBatchExecute"] = BatchExecute
NODE_DISPLAY_NAME_MAPPINGS["CanvasProBatchExecute"] = "CanvasPro · 批量执行"


class RecoverResults(Fetch):
    RETURN_TYPES=("IMAGE","STRING","STRING")
    RETURN_NAMES=("images","report","tasks_json")
    OUTPUT_IS_LIST=(True,False,False)
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{"recovery":("STRING",{"multiline":True,"default":"","tooltip":"粘贴原report、tasks_json、batch_id或完整effective_job_key。不连接任务提交节点，不会重新生图。"})},
            "optional":{"api_key":("STRING",{"default":""}),"wait_seconds":("INT",{"default":600,"min":0,"max":86400}),
                "request_timeout":("INT",{"default":60,"min":1,"max":120}),"refresh_urls":("BOOLEAN",{"default":False,"tooltip":"异步资源网址过期时，勾选后续查原任务号。不会重新提交；同步接口无查询入口。"})}}
    def execute(self,recovery,api_key="",wait_seconds=600,request_timeout=60,refresh_urls=False):
        store,client=runtime(request_timeout,api_key) if api_key else runtime(request_timeout)
        text=recovery.strip()
        if not text:raise ValueError("请粘贴原report、tasks_json、batch_id或完整effective_job_key")
        if text.startswith("{"):
            try:
                value=json.loads(text)
                batch=value.get("batch_id") or value.get("query",{}).get("batch_id") or value.get("download",{}).get("batch_id")
                if not batch:batch=store.by_key(value["effective_job_key"])
            except (ValueError,KeyError,TypeError,AttributeError):raise ValueError("无法识别恢复记录，请使用完整report或tasks_json") from None
        else:
            try:store.read(text);batch=text
            except ValueError:batch=store.by_key(text)
        store.read(batch)
        query_batch(store,client,batch,wait_seconds,2.0,3,interrupt,progress(),refresh_success=refresh_urls)
        handle=store.handle(batch)
        fetched=Fetch().execute(handle,3,request_timeout,api_key)
        info=json.dumps({"recovery_only":True,"batch_id":batch,"query":json.loads(report(store,batch)),"download":json.loads(fetched["result"][1]),
            "guidance":"只查询和下载原任务，不会重新提交。同步请求若没有保存URL或图片内容，仍需从平台获取原图。资源网址可能需要API Key或有有效期，分享日志前请删除资源网址。"},ensure_ascii=False)
        return {"ui":{"text":[info]},"result":(fetched["result"][0],info,store.handle(batch))}

NODE_CLASS_MAPPINGS["CanvasProRecoverResults"]=RecoverResults
NODE_DISPLAY_NAME_MAPPINGS["CanvasProRecoverResults"]="CanvasPro · 再次获取结果（不重新生图）"


class ImageGenerate(PromptTask):
    """One complete prompt to images, sharing the existing durable executor."""
    RETURN_TYPES=("IMAGE","STRING","STRING")
    RETURN_NAMES=("images","report","tasks_json")
    OUTPUT_IS_LIST=(True,False,False)
    OUTPUT_NODE=True
    @classmethod
    def INPUT_TYPES(cls):
        task=PromptTask.INPUT_TYPES()
        executor=BatchExecute.INPUT_TYPES()
        params=task["optional"]
        optional={"api_key":executor["optional"]["api_key"],"seed":executor["optional"]["seed"],
            "count":("INT",{"default":1,"min":1,"max":8,"tooltip":"出图张数，每张作为独立请求计费；提示词中的换行保持为同一条提示词。"}),
            "advanced":params["advanced"]}
        for name in ("reference_count","size_mode","aspect_ratio","quality","image_size","reference_urls","width","height"):
            optional[name]=params[name]
        for name in ("wait_seconds","request_timeout","sync_timeout"):
            optional[name]=executor["optional"][name]
        optional["concurrency"]=executor["required"]["concurrency"]
        for name,value in params.items():
            if name not in optional:optional[name]=value
        optional["seed"]=("INT",{**optional["seed"][1],"tooltip":"批次标识，不是模型图像种子。fixed且全部输入相同恢复已有结果；改变提示词、模型、参考图、count或seed会创建新收费任务。"})
        return {"required":task["required"],"optional":optional,"hidden":{"unique_id":"UNIQUE_ID"}}
    def execute(self,model,prompt,api_key="",seed=0,count=1,advanced=False,concurrency=3,
                wait_seconds=600,request_timeout=30,sync_timeout=600,unique_id=None,**params):
        if type(count) is not int or not 1<=count<=8:raise ValueError("count必须是1到8之间的整数，每张独立计费")
        items=PromptTask().execute(model,prompt,advanced=advanced,**params)[0]*count
        identity={"node":str(unique_id or "api"),"items":[{**item,"files":[hashlib.sha256(b).hexdigest() for b in item["files"]]} for item in items]}
        job_key="simple-"+hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:40]
        return BatchExecute().execute(items,job_key,concurrency,advanced,wait_seconds,request_timeout,
            unique_id=unique_id,api_key=api_key,seed=seed,sync_timeout=sync_timeout)

NODE_CLASS_MAPPINGS["CanvasProImageGenerate"]=ImageGenerate
NODE_DISPLAY_NAME_MAPPINGS["CanvasProImageGenerate"]="CanvasPro · 简洁生图 / Image Generate"


def async_models():
    return [m for m in MODELS if family(m)!="sync"]


class AsyncSubmit(ImageGenerate):
    RETURN_TYPES=("STRING","STRING","STRING")
    RETURN_NAMES=("tasks_json","report","task_ids")
    OUTPUT_IS_LIST=(False,False,False)
    @classmethod
    def INPUT_TYPES(cls):
        schema=super().INPUT_TYPES()
        schema["required"]["model"]=(async_models(),)
        schema["required"]["queue_key"]=("STRING",{"default":"queue-001","tooltip":"多次提交使用同一队列名；查询节点填写相同名字即可批量查询全部已提交任务。"})
        for name in ("wait_seconds","sync_timeout"):schema["optional"].pop(name,None)
        return schema
    def execute(self,model,prompt,queue_key="queue-001",api_key="",seed=0,count=1,advanced=False,concurrency=3,request_timeout=30,unique_id=None,**params):
        if not isinstance(queue_key,str) or not queue_key.strip() or len(queue_key)>128:raise ValueError("请填写1–128字符队列名称")
        actual=params.get("model_input") or model
        if not isinstance(actual,str):raise ValueError("模型名称必须是字符串")
        if family(actual.strip())=="sync":raise ValueError("此模型为同步接口，不能返回可轮询任务号；请使用简洁生图节点")
        if type(count) is not int or not 1<=count<=8:raise ValueError("count必须是1到8之间的整数")
        if type(seed) is not int or not 0<=seed<=9007199254740991:raise ValueError("无效批次seed")
        items=PromptTask().execute(model,prompt,advanced=advanced,**params)[0]*count
        identity={"node":str(unique_id or "api"),"items":[{**item,"files":[hashlib.sha256(b).hexdigest() for b in item["files"]]} for item in items]}
        job_key="async-"+hashlib.sha256(json.dumps(identity,ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:40]
        effective=f"{job_key}::seed={seed}"
        store,client=runtime(request_timeout,api_key) if api_key else runtime(request_timeout)
        submission={}
        batch=submit_tasks(store,client,effective,items,concurrency,interrupt,progress(),queue_key=queue_key,run_info=submission)
        confirmed=submission.get("new_acknowledged",0)
        if submission["mode"]=="restored_existing":message="本次复用旧批次，没有发送新的生图请求。要再次生成，请使用新seed；旧结果未知时先核对平台记录，避免重复计费。"
        elif confirmed==count:message=f"平台已返回{confirmed}个任务号；这表示提交已受理，不表示生成成功。"
        elif confirmed:message=f"平台返回{confirmed}/{count}个任务号，其余任务未确认；请查看每项状态与提交回执。"
        else:message="本次未取得任何平台任务号，不能认定提交成功。请查看错误与提交回执，勿盲目重复提交。"
        handle=store.handle(batch)
        info=json.dumps({"submission":submission,"submit_only":True,"queue_key":queue_key.strip(),"queue_batches":store.queue_batches(queue_key),"queue_batch_count":len(store.queue_batches(queue_key)),"job_key":job_key,"seed":seed,"effective_job_key":effective,"query":json.loads(report(store,batch)),
            "guidance":message},ensure_ascii=False)
        if unique_id is not None:
            try:
                from server import PromptServer
                PromptServer.instance.send_sync("canvaspro.batch_status",{"node_id":str(unique_id),"submission_only":True,"submission_mode":submission["mode"],"acknowledged":confirmed,"expected":count})
            except (ImportError,AttributeError,RuntimeError):pass
        ids="\n".join(t["task_id"] for t in store.read(batch,include_images=False)[1] if t["task_id"])
        status={"mode":submission["mode"],"acknowledged":confirmed,"expected":count}
        return {"ui":{"text":[info],"canvaspro_submission":[status]},"result":(handle,info,ids)}


class AsyncQuery(RecoverResults):
    @classmethod
    def INPUT_TYPES(cls):
        return {"required":{"queue_key":("STRING",{"default":"queue-001","tooltip":"与提交节点使用相同队列名；默认只处理该队列未完成/未成功输出的任务，支持混合模型，不重新生图。"})},
            "optional":{"api_key":("STRING",{"default":""}),"tasks_json":("STRING",{"multiline":True,"default":"","tooltip":"通常留空：按queue_key处理待办，已输出图片默认跳过。单独获取历史报告或平台任务号时填写。"}),"model":(async_models(),{"tooltip":"仅手动填写不带模型信息的纯任务号时需要选择。队列、完整报告、batch_id查询会自动使用原有型号，此参数不参与筛选。"}),
                "wait_seconds":("INT",{"default":0,"min":0,"max":86400,"tooltip":"旧工作流兼容字段，已停用；本节点始终只查询当前状态，不等待生成完成。"}),
                "request_timeout":("INT",{"default":60,"min":1,"max":120}),"refresh_urls":("BOOLEAN",{"default":False}),
                "include_history":("BOOLEAN",{"default":False,"tooltip":"默认只处理待完成/未成功输出的任务；开启后重新输出历史图片。仅表示图片已由查询节点输出，不代表下游保存成功；保存失败时可开启本项再次获取。"})},"hidden":{"prompt":"PROMPT"}}
    def execute(self,queue_key="queue-001",api_key="",tasks_json="",model="gpt-image-2",wait_seconds=0,request_timeout=60,refresh_urls=False,prompt=None,include_history=False):
        # Ignore legacy wait_seconds values, including 600 saved by old workflows.
        def snapshot_result(info,images,handle):
            counts={}
            queries=[entry["query"] for entry in info["batches"]] if "batches" in info else [info["query"]]
            for query in queries:
                for status,n in query["counts"].items():counts[status]=counts.get(status,0)+n
            info.update(query_mode="snapshot",counts=counts,
                guidance="本次仅查询当前状态，不等待生成完成，不重新提交。排队或处理中可稍后再次运行；已完成图片会下载，下载失败可再次获取。无平台任务号的提交结果未知，不能通过查询补交，请先核对平台记录。")
            if "queue_summary" in info:
                info["guidance"]+=" 默认跳过已输出的图片，下载失败会保留；失败/无任务号仅首次展示详情，历史状态见queue_summary。需要旧图片或完整旧日志时开启include_history，或使用再次获取结果节点。图片输出不等于下游保存成功。"
            text=json.dumps(info,ensure_ascii=False)
            status={"counts":counts}
            if "new_output_count" in info:status.update(output_count=info["new_output_count"],skipped=info["skipped_task_count"])
            return {"ui":{"text":[text],"canvaspro_query":[status]},"result":(images,text,handle)}
        if not tasks_json.strip() and isinstance(prompt,dict):
            active=[node for node in prompt.values() if isinstance(node,dict) and node.get("class_type")=="CanvasProAsyncSubmit" and (node.get("inputs",{}).get("queue_key","queue-001")==queue_key or isinstance(node.get("inputs",{}).get("queue_key"),list))]
            if active:
                info=json.dumps({"queue_key":queue_key,"query_skipped":True,"guidance":"当前是提交阶段：同一队列的提交节点仍启用。可连续提交多次，禁用提交节点后再运行，本查询节点将批量获取累计任务。"},ensure_ascii=False)
                return {"ui":{"text":[info],"canvaspro_query":[{"query_skipped":True}]},"result":(image_output([]),info,json.dumps({"queue_key":queue_key,"batches":[],"query_skipped":True},ensure_ascii=False))}
        text=tasks_json.strip()
        if text.startswith("{"):
            try:
                grouped=json.loads(text)
                if grouped.get("queue_key") and "batches" in grouped:queue_key=grouped["queue_key"];text=""
            except (ValueError,AttributeError):pass
        store,client=runtime(request_timeout,api_key) if api_key else runtime(request_timeout)
        if not text:
            summary=store.queue_summary(queue_key)
            if not summary["total_tasks"]:raise ValueError("此队列没有已提交任务，请先提交或检查队列名称")
            batches=store.queue_work(queue_key,include_history)
            images=[];reports=[];handles=[];output_map=[];notices=[]
            for batch,positions in batches.items():
                interrupt()
                query_batch(store,client,batch,0,2.0,3,interrupt,progress(),refresh_success=refresh_urls,positions=positions)
                fetched=Fetch().execute(store.handle(batch,positions=positions),3,request_timeout,api_key,positions=positions)
                if not json.loads(fetched["result"][1]).get("no_images"):
                    images.extend(fetched["result"][0])
                    output_map.extend({"batch_id":batch,"index":index} for index in json.loads(fetched["result"][1])["output_indices"])
                reports.append({"batch_id":batch,"query":json.loads(report(store,batch,positions=positions)),"download":json.loads(fetched["result"][1])})
                handles.append(json.loads(store.handle(batch,positions=positions)))
                for task in store.read(batch,include_images=False,positions=positions)[1]:
                    if task["status"]=="failed" or not task["task_id"]:notices.append((batch,task["position"],task["status"]))
            interrupt()
            accepted=store.record_queue_run(queue_key,[(item["batch_id"],item["index"]) for item in output_map],notices,include_history)
            selected=[(im,item) for im,item in zip(images,output_map) if (item["batch_id"],item["index"]) in accepted]
            images=[im for im,item in selected];output_map=[item for im,item in selected]
            info={"query_only":True,"query_scope":"all_history" if include_history else "pending","queue_key":queue_key.strip(),
                "batch_count":len(batches),"batches":reports,"output_map":output_map,"new_output_count":len(images),
                "skipped_task_count":summary["total_tasks"]-sum(map(len,batches.values())),"queue_summary":store.queue_summary(queue_key)}
            return snapshot_result(info,image_output(images),json.dumps({"queue_key":queue_key.strip(),"batches":handles},ensure_ascii=False))
        if not text.startswith("{"):
            try:store.read(text,include_images=False)
            except ValueError:
                try:store.by_key(text)
                except ValueError:
                    if family(model)=="sync":raise ValueError("同步模型没有轮询接口")
                    ids=[line.strip() for line in text.splitlines() if line.strip()]
                    if not ids or len(ids)>256 or any(len(x)>256 or any(c.isspace() for c in x) or client.key in x for x in ids):raise ValueError("任务号格式无效")
                    fingerprint=hashlib.sha256(json.dumps([client.base,model,ids]).encode()).hexdigest()
                    batch,_=store.create("query-"+fingerprint,fingerprint,client.base,model,len(ids))
                    for task in store.read(batch,include_images=False)[1]:
                        if not task['task_id']:store.update(batch,task['position'],status='queued',task_id=ids[task['position']])
                    text=store.handle(batch)
        fetched=RecoverResults().execute(text,api_key,0,request_timeout,refresh_urls)["result"]
        return snapshot_result(json.loads(fetched[1]),fetched[0],fetched[2])

NODE_CLASS_MAPPINGS["CanvasProAsyncSubmit"]=AsyncSubmit
NODE_DISPLAY_NAME_MAPPINGS["CanvasProAsyncSubmit"]="CanvasPro · 异步提交 / Async Submit"
NODE_CLASS_MAPPINGS["CanvasProAsyncQuery"]=AsyncQuery
NODE_DISPLAY_NAME_MAPPINGS["CanvasProAsyncQuery"]="CanvasPro · 队列批量查询 / Async Query"
