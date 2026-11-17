import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from .client import ClientError
from .image_host import host_key, upload, UploadError
from .protocol import build_request, query_path


def run_parallel(items, worker, concurrency, interrupt=lambda: None, progress=lambda n, total: None):
    if not 1 <= concurrency <= 8:
        raise ValueError("Concurrency must be 1-8")
    cancel = threading.Event()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(worker, item, cancel) for item in items}
        done_count = 0
        try:
            while futures:
                interrupt()
                done, futures = wait(futures, timeout=0.1, return_when=FIRST_COMPLETED)
                for f in done:
                    f.result()
                    done_count += 1
                    progress(done_count, len(items))
        finally:
            cancel.set()
            for f in futures:
                f.cancel()


def submit_batch(store, client, job_key, model, prompts, size="", quality="", image_size="",
                 files=(), urls=(), reference_mode="shared", concurrency=3, interrupt=lambda: None, progress=lambda n, total: None, task_items=None):
    if not prompts or len(prompts) > 256:
        raise ValueError("Batch requires 1-256 prompts")
    if reference_mode not in ("shared", "paired"):
        raise ValueError("Reference mode must be shared or paired")
    refs = files or urls
    if reference_mode == "paired" and refs and len(refs) != len(prompts):
        raise ValueError("Paired references require exactly one image/URL per prompt")
    if not 1 <= concurrency <= 8:
        raise ValueError("Concurrency must be 1-8")
    # Validate every item before any paid POST or durable batch allocation.
    requests = []
    for i, prompt in enumerate(prompts):
        selected_files = files[i:i+1] if reference_mode == "paired" else files
        selected_urls = urls[i:i+1] if reference_mode == "paired" else urls
        requests.append(build_request(model, prompt, size, quality, image_size, selected_files, selected_urls))
    fingerprint = hashlib.sha256(json.dumps({"model": model, "prompts": prompts, "size": size,
        "quality": quality, "image_size": image_size, "files": [hashlib.sha256(b).hexdigest() for b in files],
        "urls": urls, "reference_mode": reference_mode}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    if task_items is not None:
        if len(task_items) != len(prompts):
            raise ValueError("Task count mismatch")
        requests = [build_request(model, item["prompt"], item["size"], item["quality"],
            item["image_size"], item["files"], item["urls"]) for item in task_items]
        fingerprint = hashlib.sha256(json.dumps({"model": model, "items": [
            {**item, "files": [hashlib.sha256(b).hexdigest() for b in item["files"]]}
            for item in task_items]}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return submit_requests(store, client, job_key, model, requests, fingerprint, concurrency, interrupt, progress)


def submit_tasks(store, client, job_key, items, concurrency=3, interrupt=lambda: None, progress=lambda n, total: None, imgbb_api_key="", queue_key=None, run_info=None):
    if not items or len(items) > 256:
        raise ValueError("Batch requires 1-256 tasks")
    if not 1 <= concurrency <= 8:
        raise ValueError("Concurrency must be 1-8")
    requests = [build_request(item["model"], item["prompt"], item["size"], item["quality"],
        item["image_size"], item["files"], item["urls"], defer_upload=True) for item in items]
    models = [item["model"] for item in items]
    model = models[0] if len(set(models)) == 1 else "mixed"
    fingerprint = hashlib.sha256(json.dumps({"items": [
        {**item, "files": [hashlib.sha256(b).hexdigest() for b in item["files"]]}
        for item in items]}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return submit_requests(store, client, job_key, model, requests, fingerprint, concurrency, interrupt, progress, models, imgbb_api_key, queue_key, run_info)


def submit_requests(store, client, job_key, model, requests, fingerprint, concurrency, interrupt, progress, models=None, imgbb_api_key="", queue_key=None, run_info=None):
    needs_host=any(isinstance(req[2],dict) for req in requests)
    key=""
    if needs_host:
        try: store.by_key(job_key)
        except ValueError: key=host_key(imgbb_api_key)
    batch, created = store.create(job_key, fingerprint, client.base, model, len(requests), models)
    if queue_key is not None:store.add_queue(queue_key,batch)
    if run_info is not None:run_info.update({"mode":"new_batch" if created else "restored_existing","new_post_attempts":0,"new_acknowledged":0})
    if not created:
        return batch  # Never replay a saved submit, including unknown/prepared records.

    host_cache={}
    host_lock=threading.Lock()
    def worker(index, cancel):
        if cancel.is_set() or not store.claim(batch, index):
            return
        path, payload, uploads = requests[index]
        receipt={"endpoint":client.base+path,"post_attempted":False,"http_status":None,"request_id":None,"acknowledgement":"none"}
        try:
            if isinstance(uploads,dict):
                refs=[]
                for blob in uploads["imgbb_files"]:
                    if cancel.is_set(): raise UploadError("reference_upload_cancelled")
                    digest=hashlib.sha256(blob).hexdigest()
                    with host_lock:
                        if digest not in host_cache:host_cache[digest]=upload(blob,key)
                        refs.append(host_cache[digest])
                payload={**payload,"images":refs};uploads=None
                if cancel.is_set():raise UploadError("reference_upload_cancelled")
            receipt.update(post_attempted=True,attempted_at=datetime.now(timezone.utc).isoformat())
            store.update(batch,index,submit_receipt=receipt)
            result = client.submit(path, payload, uploads,receipt=receipt)
            if path in ("/v1/images/generations", "/v1/images/edits"):
                store.update(batch,index,status="succeeded",urls=result["urls"],image=result["image"],detail="sync_completed_no_poll")
            else:
                store.update(batch, index, status="queued", task_id=result, detail="")
        except UploadError as error:
            store.update(batch,index,status="failed",detail="reference_upload_failed_no_generation: "+str(error))
        except ClientError as error:
            receipt["error_code"]=str(error)
            store.update(batch, index, status="submit_unknown", detail=str(error))
        except Exception:
            store.update(batch, index, status="submit_unknown", detail="submit_local_error_outcome_unknown")
        finally:
            store.update(batch,index,submit_receipt=receipt)
    run_parallel(list(range(len(requests))), worker, concurrency, interrupt, progress)
    if run_info is not None:
        receipts=[task["submit_receipt"] for task in store.read(batch,include_images=False)[1]]
        run_info["new_post_attempts"]=sum(bool(x.get("post_attempted")) for x in receipts)
        run_info["new_acknowledged"]=sum(x.get("acknowledgement") in ("task_id_received","sync_image_received") for x in receipts)
    return batch


def query_batch(store, client, batch, wait_seconds, poll_interval, concurrency, interrupt=lambda: None, progress=lambda n, total: None, refresh_success=False):
    meta, tasks = store.read(batch,include_images=False)
    if meta["base"] != client.base:
        raise ValueError("Saved task service differs from current settings")
    deadline = time.monotonic() + max(1, wait_seconds)
    query_once = wait_seconds == 0

    def worker(task, cancel):
        if not task["task_id"] or task["status"] == "failed":
            return
        if task["status"]=="succeeded" and (task.get("image") is not None or (task["urls"] and not refresh_success)):
            return
        interval = max(0.2, poll_interval)
        # Snapshot requests get their own timeout when a worker becomes available.
        # A slow earlier group must not consume later tasks' one query opportunity.
        task_deadline = time.monotonic() + client.timeout if query_once else deadline
        while not cancel.is_set() and time.monotonic() < task_deadline:
            try:
                body = client.query(query_path(task["model"], task["task_id"]), cancel, task_deadline, single_attempt=query_once)
                if body.get("task_id") != task["task_id"]:
                    raise ClientError("query_task_id_mismatch")
                status = body["status"]
                if task["status"]=="succeeded" and task["urls"] and status!="succeeded":
                    store.update(batch,task["position"],detail="refresh_did_not_return_success_original_resource_preserved")
                    return
                urls = []
                if status == "succeeded":
                    data = body.get("data")
                    if not isinstance(data, list) or len(data) != 1 or any(not isinstance(x, dict) or not isinstance(x.get("url"), str) or not x["url"] for x in data):
                        raise ClientError("query_success_missing_image_url")
                    urls = [x["url"] for x in data]
                    if any(client.key in u for u in urls):
                        raise ClientError("query_result_contains_key")
                store.update(batch, task["position"], status=status, urls=urls,
                             detail="server_task_failed" if status == "failed" else "")
                if query_once or status in ("succeeded", "failed"):
                    return
            except ClientError as error:
                store.update(batch, task["position"], detail=str(error))
                if query_once:
                    return
            cancel.wait(min(interval, max(0, task_deadline-time.monotonic())))
            interval = min(interval * 1.5, 15)
        store.update(batch, task["position"], detail="wait_cancelled" if cancel.is_set() else "wait_timeout_query_again")
    run_parallel(tasks, worker, concurrency, interrupt, progress)
    return batch


def report(store, batch):
    _, tasks = store.read(batch,include_images=False)
    counts = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    resources=store.resources(batch)
    return json.dumps({"batch_id": batch, "counts": counts, "items": [
        {**resources[i], "status": t["status"], "detail": t["detail"]} for i,t in enumerate(tasks)]}, ensure_ascii=False)
