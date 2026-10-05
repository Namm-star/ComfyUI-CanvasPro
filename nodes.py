import hashlib
import io
import json
import numpy as np
import torch
from PIL import Image, ImageOps
from .config import settings
from .client import Client, ClientError
from .store import Store
from .protocol import MODELS, family
from .batch import submit_batch, query_batch, run_parallel, report


def runtime(timeout=30):
    base, key = settings()
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

    def execute(self, tasks_json, concurrency, request_timeout):
        store, client = runtime(request_timeout)
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
    "CanvasProBatchFetch": Fetch, "CanvasProRestoreBatch": Restore, "CanvasProImportTasks": ImportTasks}
NODE_DISPLAY_NAME_MAPPINGS = {"CanvasProBatchSubmit": "CanvasPro · 批量提交 (新批次收费)",
    "CanvasProBatchWait": "CanvasPro · 批量查询 / 等待", "CanvasProBatchFetch": "CanvasPro · 批量获取图片",
    "CanvasProRestoreBatch": "CanvasPro · 恢复本地批次", "CanvasProImportTasks": "CanvasPro · 导入已有任务号"}
