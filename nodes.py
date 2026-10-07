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
from .protocol import MODELS, family
from .batch import submit_batch, submit_tasks, query_batch, run_parallel, report


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
            "aspect_ratio": (["1:1", "3:4", "4:3", "9:16", "16:9"],),
            "quality": (["", "auto", "low", "medium", "high", "xhigh", "max"],),
            "image_size": (["1K", "2K", "4K"],),
            "reference_urls": ("STRING", {"multiline": True, "default": ""})}
        optional.update({f"image_{i}": ("IMAGE",) for i in range(1, 17)})
        return {"required": required, "optional": optional}

    def execute(self, job_key, model, prompts, reference_mode, concurrency, request_timeout,
                reference_count=2, size_mode="pixels", pixel_size="1024x1024", aspect_ratio="1:1",
                quality="", image_size="1K", reference_urls="", **images):
        f = family(model)
        maximum = {"kr": 16, "hc": 15, "gemini": 14}[f]
        if not 1 <= reference_count <= maximum:
            raise ValueError(f"Selected model supports at most {maximum} reference ports")
        files = []
        for i in range(1, 17):
            image = images.get(f"image_{i}")
            if image is not None:
                if i > reference_count:
                    raise ValueError("Connected image exceeds active reference_count/model limit")
                files.extend(encode_images(image))
        if f == "gemini":
            if reference_urls.strip():
                raise ValueError("Banana requires image ports; URL references unsupported")
            size, quality, image_size = aspect_ratio, "", image_size
        elif f == "hc":
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
        schema["required"] = {"model": schema["required"]["model"],
            "prompt": ("STRING", {"multiline": True, "default": "", "tooltip": "One complete task; all line breaks are preserved."})}
        schema["optional"]["advanced"] = ("BOOLEAN", {"default": False})
        note = "像素模式：1K 正方形填 1024×1024；2K 正方形填 2048×2048；4K 横图可填 3840×2160，竖图填 2160×3840。GPT 宽高须为16倍数、单边≤3840、总像素≤8294400；不能填4096×4096。比例模式可直接选1K/2K/4K。"
        schema["optional"]["width"] = ("INT", {"default": 1024, "min": 1, "max": 32768, "tooltip": "宽度（像素）。" + note})
        schema["optional"]["height"] = ("INT", {"default": 1024, "min": 1, "max": 32768, "tooltip": "高度（像素）。" + note})
        return schema

    def execute(self, model, prompt, reference_count=2, size_mode="pixels", pixel_size="1024x1024",
                aspect_ratio="1:1", quality="", image_size="1K", reference_urls="", advanced=False, width=None, height=None, **images):
        if width is not None or height is not None:
            if width is None or height is None or type(width) is not int or type(height) is not int:
                raise ValueError("Width and height must both be integer pixel values")
            pixel_size = f"{width}x{height}"
        maximum = {"kr": 16, "hc": 15, "gemini": 14}[family(model)]
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
        if f == "gemini":
            size, quality = aspect_ratio, ""
        elif f == "hc" or size_mode == "pixels":
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
        build_request(model, prompt, size, quality, image_size, files, item["urls"])
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

    def execute(self, tasks_json, concurrency, request_timeout, api_key=""):
        store, client = runtime(request_timeout, api_key) if api_key else runtime(request_timeout)
        batch = store.resolve(tasks_json)
        meta, tasks = store.read(batch)
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
                for url in task["urls"]:
                    if cancel.is_set():
                        raise ClientError("download_cancelled")
                    blob = client.download(url)
                    with Image.open(io.BytesIO(blob)) as im:
                        im = ImageOps.exif_transpose(im).convert("RGB")
                        tensor = torch.from_numpy(np.array(im).astype(np.float32) / 255.0).unsqueeze(0)
                    tensors.append(tensor)
                results[index] = tensors
                details[index] = {"index": index, "status": "downloaded", "sizes": [[t.shape[2], t.shape[1]] for t in tensors]}
            except ClientError as error:
                details[index] = {"index": index, "status": "download_failed", "detail": str(error)}
            except Exception:
                details[index] = {"index": index, "status": "download_failed", "detail": "invalid_image_or_local_decode_error"}
        run_parallel(tasks, worker, concurrency, interrupt, progress())
        images = [tensor for index in sorted(results) for tensor in results[index]]
        info = json.dumps({"batch_id": batch, "items": [details[i] for i in sorted(details)],
            "output_indices": [i for i in sorted(results) for _ in results[i]]}, ensure_ascii=False)
        return {"ui": {"text": [info]}, "result": (images, info)}


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
            "job_key": ("STRING", {"default": "batch-001", "tooltip": "Same name resumes saved tasks. Use a new name to submit changed tasks."}),
            "concurrency": ("INT", {"default": 3, "min": 1, "max": 8}),
            "advanced": ("BOOLEAN", {"default": False})},
            "optional": {"wait_seconds": ("INT", {"default": 600, "min": 0, "max": 86400}),
                "request_timeout": ("INT", {"default": 30, "min": 1, "max": 120}),
                "api_key": ("STRING", {"default": "", "multiline": False, "tooltip": "Enter your CanvasPro API Key here. Saved workflows may contain it; remove before sharing."}),
                **{f"task_{i}": ("CANVASPRO_TASKS",) for i in range(2, 257)}},
            "hidden": {"unique_id": "UNIQUE_ID"}}

    def execute(self, task_1, job_key, concurrency=3, advanced=False, wait_seconds=600, request_timeout=30, unique_id=None, api_key="", **ports):
        items = list(task_1)
        for i in range(2, 257):
            if ports.get(f"task_{i}") is not None:
                items.extend(ports[f"task_{i}"])
        store, client = runtime(request_timeout, api_key) if api_key else runtime(request_timeout)
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
            payload = {"node_id": str(unique_id), "phase": phase, "counts": counts}
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
        batch = submit_tasks(store, client, job_key, items, concurrency, check, progress())
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
        info = json.dumps({"query": json.loads(report(store, batch)), "download": json.loads(download_report)}, ensure_ascii=False)
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
