import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from .client import ClientError
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
                 files=(), urls=(), reference_mode="shared", concurrency=3, interrupt=lambda: None, progress=lambda n, total: None):
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
    batch, created = store.create(job_key, fingerprint, client.base, model, len(prompts))
    if not created:
        return batch  # Never replay a saved submit, including unknown/prepared records.

    def worker(index, cancel):
        if cancel.is_set() or not store.claim(batch, index):
            return
        path, payload, uploads = requests[index]
        try:
            task_id = client.submit(path, payload, uploads)
            store.update(batch, index, status="queued", task_id=task_id, detail="")
        except ClientError as error:
            store.update(batch, index, status="submit_unknown", detail=str(error))
        except Exception:
            store.update(batch, index, status="submit_unknown", detail="submit_local_error_outcome_unknown")
    run_parallel(list(range(len(prompts))), worker, concurrency, interrupt, progress)
    return batch


def query_batch(store, client, batch, wait_seconds, poll_interval, concurrency, interrupt=lambda: None, progress=lambda n, total: None):
    meta, tasks = store.read(batch)
    if meta["base"] != client.base:
        raise ValueError("Saved task service differs from current settings")
    deadline = time.monotonic() + max(1, wait_seconds)
    query_once = wait_seconds == 0
    if query_once:
        deadline = time.monotonic() + client.timeout * 3 + 4

    def worker(task, cancel):
        if not task["task_id"] or task["status"] == "failed":
            return
        interval = max(0.2, poll_interval)
        while not cancel.is_set() and time.monotonic() < deadline:
            try:
                body = client.query(query_path(meta["model"], task["task_id"]), cancel, deadline)
                if body.get("task_id") != task["task_id"]:
                    raise ClientError("query_task_id_mismatch")
                status = body["status"]
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
            cancel.wait(min(interval, max(0, deadline-time.monotonic())))
            interval = min(interval * 1.5, 15)
        store.update(batch, task["position"], detail="wait_cancelled" if cancel.is_set() else "wait_timeout_query_again")
    run_parallel(tasks, worker, concurrency, interrupt, progress)
    return batch


def report(store, batch):
    _, tasks = store.read(batch)
    counts = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    return json.dumps({"batch_id": batch, "counts": counts, "items": [
        {"index": t["position"], "status": t["status"], "detail": t["detail"]} for t in tasks]}, ensure_ascii=False)
