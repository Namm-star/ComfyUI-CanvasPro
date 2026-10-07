"""No production credentials. Real loopback HTTP, SQLite, Pillow and torch."""
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import subprocess
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from email.parser import BytesParser
from email.policy import default

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("canvaspro", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
plugin = importlib.util.module_from_spec(spec)
sys.modules["canvaspro"] = plugin
spec.loader.exec_module(plugin)
from canvaspro.client import Client, origin
from canvaspro.store import Store
from canvaspro.batch import submit_batch, query_batch
from canvaspro.protocol import build_request, MODELS
from canvaspro import nodes
from PIL import Image
import torch


class Service(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server_port}"
        self.lock = threading.Lock()
        self.tasks, self.posts, self.gets, self.auth = {}, [], [], []
        self.active, self.peak, self.download_active, self.download_peak = 0, 0, 0, 0


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def respond(self, code, body, content_type="application/json"):
        blob = json.dumps(body).encode() if isinstance(body, dict) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        try:
            self.wfile.write(blob)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
    def do_POST(self):
        s = self.server
        blob = self.rfile.read(int(self.headers["Content-Length"]))
        if self.headers["Content-Type"].startswith("multipart/"):
            msg = BytesParser(policy=default).parsebytes(("Content-Type: " + self.headers["Content-Type"] + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + blob)
            parts = [(p.get_param("name", header="content-disposition"), p.get_filename(), p.get_payload(decode=True)) for p in msg.iter_parts()]
            body = {name: value.decode() for name, filename, value in parts if not filename}
            body["upload_fields"] = [name for name, filename, value in parts if filename]
            body["uploads"] = [value for name, filename, value in parts if filename]
        else:
            body = json.loads(blob)
        prompt = body.get("prompt") or body["contents"][0]["parts"][0]["text"]
        with s.lock:
            task_id = str(len(s.posts))
            s.posts.append((self.path, body))
            s.active += 1
            s.peak = max(s.peak, s.active)
            s.tasks[task_id] = {"prompt": prompt, "queries": 0}
        try:
            time.sleep(1.3 if prompt == "submit-timeout" else 0.06)
            if prompt == "bad-submit":
                self.respond(503, {"error": "Bearer fake-secret"})
            elif prompt == "missing-id":
                self.respond(200, {"status": "queued"})
            else:
                self.respond(200, {"task_id": task_id, "status": "queued"})
        finally:
            with s.lock:
                s.active -= 1
    def do_GET(self):
        s = self.server
        s.auth.append((self.path, self.headers.get("Authorization")))
        if self.path.startswith("/image/"):
            with s.lock:
                s.download_active += 1
                s.download_peak = max(s.download_peak, s.download_active)
            try:
                time.sleep(0.04)
                index = int(self.path.split("/")[-1])
                image = Image.new("RGB", (16+index, 12+index), (index, 100, 200))
                b = io.BytesIO()
                image.save(b, format="PNG")
                self.respond(200, b.getvalue(), "image/png")
            finally:
                with s.lock:
                    s.download_active -= 1
            return
        task_id = self.path.split("/")[-1]
        with s.lock:
            s.gets.append(self.path)
            t = s.tasks[task_id]
            t["queries"] += 1
        if t["prompt"] == "query-retry" and t["queries"] < 2:
            self.respond(503, {})
            return
        if t["prompt"] == "always-pending":
            status = "processing"
        elif t["queries"] == 1:
            status = "queued"
        else:
            status = "failed" if t["prompt"] == "fail" else "succeeded"
        body = {"task_id": task_id, "status": status}
        if status == "succeeded":
            body["data"] = [{"url": s.base + "/image/" + task_id}]
        if status == "failed":
            body["error"] = {"message": "fake-secret (must not persist)"}
        self.respond(200, body)


class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.service = Service()
        self.thread = threading.Thread(target=self.service.serve_forever, daemon=True)
        self.thread.start()
        self.store = Store(self.root)
        self.client = Client(self.service.base, "fake-secret", 1)
    def test_independent_multiline_tasks(self):
        a = nodes.PromptTask().execute("gpt-image-2", "主体：键盘\n构图：俯拍\n保留文字", image_1=torch.zeros(1,7,11,3))[0]
        b = nodes.PromptTask().execute("gpt-image-2", "主体：小猫\n背景：纯白", image_1=torch.ones(1,13,5,3))[0]
        tasks = nodes.MergeTasks().execute(a,b)[0]
        with patch.object(nodes, "runtime", return_value=(self.store,self.client)), patch.object(nodes,"interrupt"), patch.object(nodes,"progress",return_value=lambda n,t:None):
            result = nodes.SubmitTasks().execute(tasks,"independent",2,1)
            self.assertEqual(result,nodes.SubmitTasks().execute(tasks,"independent",2,1))
            changed = [{**a[0], "prompt":"changed"}, b[0]]
            with self.assertRaises(ValueError):
                nodes.SubmitTasks().execute(changed,"independent",2,1)
        bodies = {body["prompt"]:body for _,body in self.service.posts}
        self.assertEqual(set(bodies),{a[0]["prompt"],b[0]["prompt"]})
        self.assertEqual(Image.open(io.BytesIO(bodies[a[0]["prompt"]]["uploads"][0])).size,(11,7))
        self.assertEqual(Image.open(io.BytesIO(bodies[b[0]["prompt"]]["uploads"][0])).size,(5,13))
        invalid = [{**a[0],"quality":"invalid"}, b[0]]
        with self.assertRaises(ValueError):
            submit_batch(self.store,self.client,"invalid","gpt-image-2",[x["prompt"] for x in invalid],task_items=invalid)
        self.assertEqual(len(self.service.posts),2)
        banana = nodes.PromptTask().execute("T香蕉2","test")[0]
        with self.assertRaises(ValueError):
            nodes.MergeTasks().execute(a,banana)

    def test_combined_wait_fetch_and_resume(self):
        batch = self.submit(["a", "fail", "b"])
        with patch.object(nodes, "runtime", return_value=(self.store,self.client)), patch.object(nodes,"interrupt"), patch.object(nodes,"progress",return_value=lambda n,t:None):
            result = nodes.WaitFetch().execute(self.store.handle(batch), 5)
            images, info = result["result"]
            self.assertEqual(len(images),2)
            self.assertNotEqual(images[0].shape,images[1].shape)
            self.assertEqual(json.loads(info)["download"]["output_indices"],[0,2])
            again = nodes.WaitFetch().execute(self.store.handle(batch),0)
            self.assertEqual(len(again["result"][0]),2)
        self.assertEqual(len(self.service.posts),3)
        pending = submit_batch(self.store,self.client,"pending-combined","gpt-image-2",["always-pending"])
        with patch.object(nodes, "runtime", return_value=(self.store,self.client)), patch.object(nodes,"interrupt"), patch.object(nodes,"progress",return_value=lambda n,t:None):
            images, info = nodes.WaitFetch().execute(self.store.handle(pending),1)["result"]
            self.assertEqual(images,[])
            self.assertIn("wait_timeout_query_again",info)
        self.assertEqual(len(self.service.posts),4)

    def test_mixed_batch_execute_and_process_resume(self):
        bundles = [nodes.PromptTask().execute(model, "完整提示词\n第二行" + str(i))[0]
            for i,model in enumerate(["gpt-image-2", "T香蕉2", "s-gpt-image-2.5-flare"])]
        with patch.object(nodes,"runtime",return_value=(self.store,self.client)), patch.object(nodes,"interrupt"), patch.object(nodes,"progress",return_value=lambda n,t:None):
            result = nodes.BatchExecute().execute(bundles[0], "mixed-batch",3,wait_seconds=5,
                task_2=bundles[1], task_3=bundles[2])
            images, info, handle = result["result"]
            self.assertEqual(len(images),3)
            self.assertEqual(json.loads(info)["download"]["output_indices"],[0,1,2])
            batch = self.store.resolve(handle)
            saved = self.store.read(batch)[1]
            for t in saved:
                from canvaspro.protocol import query_path
                self.assertIn(query_path(t["model"],t["task_id"]),self.service.gets)
            nodes.BatchExecute().execute(bundles[0], "mixed-batch",8,wait_seconds=0,task_2=bundles[1],task_3=bundles[2])
            with self.assertRaises(ValueError):
                nodes.BatchExecute().execute(bundles[0],"mixed-batch",3,wait_seconds=0,task_2=bundles[2],task_3=bundles[1])
        self.assertEqual(len(self.service.posts),3)
        self.assertGreaterEqual(self.service.peak,2)
        script = "import sys; sys.path.insert(0,sys.argv[1]); import test_integration; from canvaspro.store import Store; from canvaspro.client import Client; from canvaspro.batch import query_batch; from pathlib import Path; s=Store(Path(sys.argv[2])); b=s.by_key('mixed-batch'); query_batch(s,Client(sys.argv[3],'fake-secret',1),b,0,.2,3); assert len({t['model'] for t in s.read(b)[1]})==3; print('mixed resume passed')"
        resumed = subprocess.run([sys.executable,"-c",script,str(ROOT/'tests'),str(self.root),self.service.base],capture_output=True,text=True,timeout=30)
        self.assertEqual(resumed.returncode,0,resumed.stderr)
        self.assertEqual(len(self.service.posts),3)

    def test_mixed_preflight_all_tasks_before_post(self):
        good = nodes.PromptTask().execute("gpt-image-2","valid")[0]
        bad = [{**good[0], "model":"T香蕉2", "size":"1024x1024"}]
        with patch.object(nodes,"runtime",return_value=(self.store,self.client)), patch.object(nodes,"interrupt"), patch.object(nodes,"progress",return_value=lambda n,t:None):
            with self.assertRaises(ValueError):
                nodes.BatchExecute().execute(good,"invalid-mixed",task_2=bad)
            with self.assertRaises(ValueError):
                nodes.BatchExecute().execute(good*257,"too-many")
        self.assertEqual(self.service.posts,[])

    def test_legacy_database_migration(self):
        import sqlite3
        legacy = self.root / "legacy"
        legacy.mkdir()
        with sqlite3.connect(legacy / "tasks.sqlite3") as db:
            db.executescript("CREATE TABLE batches (id TEXT PRIMARY KEY,job_key TEXT UNIQUE,fingerprint TEXT,base TEXT,model TEXT,created REAL); CREATE TABLE tasks (batch TEXT,position INTEGER,status TEXT,task_id TEXT,detail TEXT,urls TEXT DEFAULT '[]',PRIMARY KEY(batch,position));")
            db.execute("INSERT INTO batches VALUES ('old','old-key','fp',?,'T香蕉2',0)",(self.service.base,))
            db.execute("INSERT INTO tasks VALUES ('old',0,'queued','existing','','[]')")
        db.close()
        migrated = Store(legacy)
        self.assertEqual(migrated.by_key("old-key"),"old")
        self.assertEqual(migrated.read("old")[1][0]["model"],"T香蕉2")
        self.assertEqual(Store(legacy).handle("old"),migrated.handle("old"))

    def test_batch_status_events(self):
        from types import SimpleNamespace
        events=[]
        fake = SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(send_sync=lambda name,data:events.append((name,data)))))
        task = nodes.PromptTask().execute("gpt-image-2","status")[0]
        with patch.dict(sys.modules, {"server":fake}), patch.object(nodes,"runtime",return_value=(self.store,self.client)), patch.object(nodes,"interrupt"), patch.object(nodes,"progress",return_value=lambda n,t:None):
            result = nodes.BatchExecute().execute(task,"events",wait_seconds=5,unique_id="99")
        self.assertEqual(len(result["result"][0]),1)
        self.assertEqual(events[-1][0],"canvaspro.batch_status")
        self.assertEqual(events[-1][1]["node_id"],"99")
        self.assertEqual(events[-1][1]["counts"]["succeeded"],1)
        self.assertNotIn("fake-secret",json.dumps(events))

    def test_direct_node_key_without_server_configuration(self):
        task = nodes.PromptTask().execute("gpt-image-2","direct key")[0]
        env = dict(CANVASPRO_API_KEY="",CANVASPRO_KEY_FILE=str(self.root/"absent-key"),CANVASPRO_DATA_DIR=str(self.root),CANVASPRO_BASE_URL=self.service.base,CANVASPRO_ALLOW_LOCAL_TEST="1")
        with patch.dict(os.environ,env), patch.object(nodes,"interrupt"), patch.object(nodes,"progress",return_value=lambda n,t:None):
            images, info, handle = nodes.BatchExecute().execute(task,"direct-key",wait_seconds=5,api_key="fake-secret")["result"]
            self.assertEqual(len(images),1)
            self.assertTrue(all(auth=="Bearer fake-secret" for _,auth in self.service.auth))
            self.assertNotIn("fake-secret",info+handle)
            self.assertNotIn(b"fake-secret",(self.root/"tasks.sqlite3").read_bytes())
            from canvaspro.config import settings
            with patch.dict(os.environ,{"CANVASPRO_API_KEY":"other-key"}):
                self.assertEqual(settings("fake-secret")[1],"fake-secret")
            with self.assertRaises(ValueError): settings("bad key")

    def test_separate_width_height_and_legacy_size(self):
        self.assertNotIn("pixel_size",nodes.PromptTask.INPUT_TYPES()["optional"])
        for w,h in [(1024,1024),(2048,2048),(3840,2160),(2160,3840)]:
            item=nodes.PromptTask().execute("gpt-image-2","size",width=w,height=h)[0][0]
            self.assertEqual(item["size"],f"{w}x{h}")
        legacy=nodes.PromptTask().execute("gpt-image-2","old",pixel_size="1536x1024")[0][0]
        self.assertEqual(legacy["size"],"1536x1024")
        ratio=nodes.PromptTask().execute("gpt-image-2","ratio",size_mode="ratio",aspect_ratio="16:9",image_size="4K",width=1024,height=1024)[0][0]
        self.assertEqual((ratio["size"],ratio["image_size"]),("16:9","4K"))
        with self.assertRaises(ValueError):
            nodes.PromptTask().execute("gpt-image-2","invalid",width=4096,height=4096)
        with self.assertRaises(ValueError):
            nodes.PromptTask().execute("gpt-image-2","invalid",width=1024)

    def test_batch_seed_resumes_or_creates_new_paid_batch(self):
        task = nodes.PromptTask().execute("gpt-image-2", "seed test")[0]
        changed = nodes.PromptTask().execute("gpt-image-2", "changed prompt")[0]
        env = dict(CANVASPRO_API_KEY="fake-secret", CANVASPRO_DATA_DIR=str(self.root),
            CANVASPRO_BASE_URL=self.service.base, CANVASPRO_ALLOW_LOCAL_TEST="1")
        with patch.dict(os.environ, env), patch.object(nodes, "interrupt"), patch.object(nodes, "progress", return_value=lambda n,t:None):
            run = nodes.BatchExecute().execute
            first = run(task, "seed-batch", seed=123, wait_seconds=5)["result"]
            resumed = run(task, "seed-batch", seed=123, wait_seconds=5)["result"]
            self.assertEqual(first[2], resumed[2])
            self.assertEqual(len(self.service.posts), 1)
            with self.assertRaisesRegex(ValueError, "seed"):
                run(changed, "seed-batch", seed=123, wait_seconds=5)
            self.assertEqual(len(self.service.posts), 1)
            second = run(changed, "seed-batch", seed=124, wait_seconds=5)["result"]
            self.assertNotEqual(first[2], second[2])
            self.assertEqual(len(self.service.posts), 2)
            self.assertEqual(json.loads(second[1])["effective_job_key"], "seed-batch::seed=124")
            self.assertNotIn("seed", self.service.posts[0][1])
            for bad in [-1, 9007199254740992, 1.5, True]:
                with self.assertRaises(ValueError): run(task, "invalid", seed=bad)
            self.assertEqual(len(self.service.posts), 2)

    def tearDown(self):
        self.service.shutdown()
        self.service.server_close()
        self.thread.join()
        self.tmp.cleanup()
    def submit(self, prompts, **kwargs):
        return submit_batch(self.store, self.client, "batch", "gpt-image-2", prompts, **kwargs)

    def test_order_partial_failure_concurrency_restart_and_no_replay(self):
        batch = self.submit(["a", "fail", "b", "c", "d"], concurrency=2)
        self.assertEqual(self.service.gets, [])
        self.assertEqual(len(self.service.posts), 5)
        self.assertLessEqual(self.service.peak, 2)
        restarted = Store(self.root)
        self.assertEqual(batch, submit_batch(restarted, self.client, "batch", "gpt-image-2", ["a", "fail", "b", "c", "d"]))
        self.assertEqual(len(self.service.posts), 5)
        query_batch(restarted, self.client, batch, 5, .2, 2)
        _, tasks = restarted.read(batch)
        self.assertEqual([t["position"] for t in tasks], list(range(5)))
        self.assertEqual([t["status"] for t in tasks], ["succeeded", "failed", "succeeded", "succeeded", "succeeded"])
        self.assertNotIn("fake-secret", restarted.handle(batch))
        self.assertNotIn(b"fake-secret", restarted.path.read_bytes())

    def test_submit_timeout_http_failure_and_missing_id_not_retried(self):
        batch = self.submit(["submit-timeout", "bad-submit", "missing-id"], concurrency=2)
        self.assertEqual(len(self.service.posts), 3)
        self.assertTrue(all(t["status"] == "submit_unknown" for t in self.store.read(batch)[1]))
        self.submit(["submit-timeout", "bad-submit", "missing-id"])
        query_batch(self.store, self.client, batch, 1, .2, 2)
        self.assertEqual(len(self.service.posts), 3)
        self.assertEqual(self.service.gets, [])

    def test_new_process_restores_without_post(self):
        batch = self.submit(["a", "b"])
        script = """
import sys
sys.path.insert(0, sys.argv[1])
from test_integration import Store, Client, submit_batch, query_batch
from pathlib import Path
store = Store(Path(sys.argv[2]))
client = Client(sys.argv[3], 'fake-secret', 1)
batch = submit_batch(store, client, 'batch', 'gpt-image-2', ['a', 'b'])
query_batch(store, client, batch, 5, .2, 2)
assert all(t['status'] == 'succeeded' for t in store.read(batch)[1])
print(batch)
"""
        result = subprocess.run([sys.executable, "-c", script, str(ROOT / "tests"), str(self.root), self.client.base], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), batch)
        self.assertEqual(len(self.service.posts), 2)

    def test_preflight_and_job_key_conflict(self):
        with self.assertRaises(ValueError):
            self.submit(["ok", ""], concurrency=2)
        self.assertEqual(self.service.posts, [])
        self.submit(["ok"])
        with self.assertRaises(ValueError):
            self.submit(["different"])
        self.assertEqual(len(self.service.posts), 1)

    def test_query_timeout_and_get_retry(self):
        batch = self.submit(["always-pending", "query-retry"])
        query_batch(self.store, self.client, batch, 2, .2, 2)
        tasks = self.store.read(batch)[1]
        self.assertEqual(tasks[0]["detail"], "wait_timeout_query_again")
        self.assertEqual(tasks[1]["status"], "succeeded")
        self.assertEqual(len(self.service.posts), 2)
        query_batch(self.store, self.client, batch, 0, .2, 2)
        self.assertEqual(len(self.service.posts), 2)

    def test_crash_sending_and_prepared_records_never_replayed(self):
        batch, _ = self.store.create("batch", "fingerprint", self.client.base, "gpt-image-2", 2)
        self.store.claim(batch, 0)
        restarted = Store(self.root)
        self.assertEqual(restarted.read(batch)[1][0]["status"], "submit_unknown")
        self.assertEqual(restarted.create("batch", "fingerprint", self.client.base, "gpt-image-2", 2), (batch, False))
        self.assertEqual(self.service.posts, [])

    def test_cancel_wait_preserves_task(self):
        batch = self.submit(["always-pending"])
        start = time.monotonic()
        def interrupt():
            if time.monotonic() - start > .4:
                raise InterruptedError("user cancelled")
        with self.assertRaises(InterruptedError):
            query_batch(self.store, self.client, batch, 30, .2, 1, interrupt=interrupt)
        task = self.store.read(batch)[1][0]
        self.assertEqual(task["detail"], "wait_cancelled")
        self.assertTrue(task["task_id"])
        self.assertEqual(len(self.service.posts), 1)

    def test_all_models_native_paths_and_upload_fields(self):
        b = io.BytesIO()
        Image.new("RGB", (4, 4)).save(b, format="PNG")
        files = [b.getvalue(), b.getvalue()]
        for index, model in enumerate(MODELS):
            submit_batch(self.store, self.client, str(index), model, ["edit"], files=files)
        paths = [p for p, _ in self.service.posts]
        self.assertEqual(paths, ["/kr/v1/images/edits", "/kr/gemini/v1/images/generations", "/kr/gemini/v1/images/generations"] + ["/hc/v1/images/edits/upload"]*3)
        self.assertEqual(self.service.posts[0][1]["upload_fields"], ["image[]"]*2)
        self.assertEqual(self.service.posts[3][1]["upload_fields"], ["image"]*2)
        self.assertEqual(self.service.posts[3][1]["uploads"], files)
        body = self.service.posts[1][1]
        self.assertEqual(len(body["contents"][0]["parts"]), 3)
        self.assertNotIn("size", body)

    def test_url_edit_is_multipart_and_hc_is_json(self):
        submit_batch(self.store, self.client, "kr", "gpt-image-2", ["edit"], urls=["https://example.com/a.png"])
        self.assertEqual(self.service.posts[0][1]["image_url"], "https://example.com/a.png")
        submit_batch(self.store, self.client, "hc", "s-gpt-image-2", ["edit"], urls=["https://example.com/a.png"])
        self.assertEqual(self.service.posts[1][0], "/hc/v1/images/edits")
        self.assertEqual(self.service.posts[1][1]["image"], "https://example.com/a.png")

    def test_nodes_real_images_order_partial_success_and_import(self):
        old_env = dict(os.environ)
        old_interrupt, old_progress = nodes.interrupt, nodes.progress
        try:
            os.environ.update(CANVASPRO_DATA_DIR=str(self.root), CANVASPRO_API_KEY="fake-secret", CANVASPRO_BASE_URL=self.client.base, CANVASPRO_ALLOW_LOCAL_TEST="1")
            nodes.interrupt = lambda: None
            nodes.progress = lambda: lambda n, t: None
            submitted = nodes.Submit().execute("node", "s-gpt-image-2", "a\nfail\nb\nc", "", "", "", "paired", 2, 1, torch.zeros((4, 8, 8, 3)))
            handle = submitted["result"][0]
            waited = nodes.Wait().execute(handle, 5, .2, 2, 1)["result"][0]
            fetched = nodes.Fetch().execute(waited, 2, 1)["result"]
            self.assertEqual(len(fetched[0]), 3)
            indices = json.loads(fetched[1])["output_indices"]
            self.assertEqual(indices, [0, 2, 3])
            self.assertTrue(all(t.ndim == 4 and t.shape[0] == 1 for t in fetched[0]))
            self.assertEqual(len({tuple(t.shape) for t in fetched[0]}), 3)
            self.assertLessEqual(self.service.download_peak, 2)
            restored = nodes.Restore().execute("node")[0]
            self.assertEqual(json.loads(restored)["batch_id"], json.loads(handle)["batch_id"])
            ids = "\n".join(t["task_id"] for t in self.store.read(json.loads(handle)["batch_id"])[1])
            imported = nodes.ImportTasks().execute("s-gpt-image-2", ids)[0]
            self.assertEqual(len(json.loads(imported)["tasks"]), 4)
            self.assertEqual(len(self.service.posts), 4)
            self.assertTrue(all(auth == "Bearer fake-secret" for path, auth in self.service.auth))
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            nodes.interrupt, nodes.progress = old_interrupt, old_progress

    def test_parameter_limits(self):
        bad = [dict(model="s-gpt-image-2", prompt="p", size="1:1"),
               dict(model="s-gpt-image-2", prompt="p", size="2880x2880"),
               dict(model="T香蕉2", prompt="p", quality="high"),
               dict(model="gpt-image-2", prompt="p", files=[b"a"]*17),
               dict(model="gpt-image-2", prompt="😀"*2001),
               dict(model="gpt-image-2", prompt="p", urls=["http://localhost/a"])]
        for args in bad:
            with self.assertRaises(ValueError):
                build_request(**args)

    def test_multiport_preserves_dimensions_and_model_parameter_mapping(self):
        old_env = dict(os.environ)
        old_interrupt, old_progress = nodes.interrupt, nodes.progress
        try:
            os.environ.update(CANVASPRO_DATA_DIR=str(self.root), CANVASPRO_API_KEY="fake-secret", CANVASPRO_BASE_URL=self.client.base, CANVASPRO_ALLOW_LOCAL_TEST="1")
            nodes.interrupt = lambda: None
            nodes.progress = lambda: lambda n,t: None
            submit = nodes.ModelSubmit()
            images = {"image_1": torch.zeros((1,7,11,3)), "image_2": torch.zeros((1,13,5,3))}
            for i,model in enumerate(["gpt-image-2","T香蕉2","s-gpt-image-2.5-flare"]):
                submit.execute(str(i),model,"edit","shared",2,1,quality="high",image_size="2K",aspect_ratio="16:9",**images)
            self.assertEqual([Image.open(io.BytesIO(b)).size for b in self.service.posts[0][1]["uploads"]],[(11,7),(5,13)])
            self.assertNotIn("image_size",self.service.posts[0][1])
            banana=self.service.posts[1][1]
            self.assertEqual(banana["generationConfig"]["imageConfig"],{"aspectRatio":"16:9","imageSize":"2K"})
            self.assertNotIn("quality",banana)
            self.assertNotIn("image_size",self.service.posts[2][1])
            with self.assertRaises(ValueError):
                submit.execute("overflow","T香蕉2","edit","shared",2,1,reference_count=15)
            with self.assertRaises(ValueError):
                submit.execute("hidden","gpt-image-2","edit","shared",2,1,image_3=images["image_1"])
            self.assertEqual(len(self.service.posts),3)
        finally:
            os.environ.clear(); os.environ.update(old_env)
            nodes.interrupt,nodes.progress=old_interrupt,old_progress

    def test_simultaneous_same_job_has_one_submit(self):
        results = []
        def call():
            results.append(self.submit(["a", "b"], concurrency=2))
        threads = [threading.Thread(target=call) for _ in range(4)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(len(self.service.posts), 2)

    def test_download_auth_removed_on_cross_origin_redirect(self):
        class Response:
            def __init__(self, status, headers):
                self.status_code, self.headers = status, headers
            def __enter__(self): return self
            def __exit__(self, *args): self.close()
            def close(self): pass
            def iter_content(self, size): return iter([b"image"])
        responses = [Response(302, {"Location": "https://cdn.example.com/image.png"}), Response(200, {})]
        calls = []
        def get(url, **kwargs):
            calls.append((url, kwargs["headers"]))
            return responses.pop(0)
        with patch("canvaspro.client.requests.get", get):
            self.assertEqual(self.client.download("/protected/image"), b"image")
        self.assertEqual(calls[0][1], {"Authorization": "Bearer fake-secret"})
        self.assertEqual(calls[1][1], {})

    def test_download_failure_preserves_other_images(self):
        old_env = dict(os.environ)
        old_interrupt, old_progress = nodes.interrupt, nodes.progress
        try:
            os.environ.update(CANVASPRO_DATA_DIR=str(self.root), CANVASPRO_API_KEY="fake-secret", CANVASPRO_BASE_URL=self.client.base, CANVASPRO_ALLOW_LOCAL_TEST="1")
            nodes.interrupt = lambda: None
            nodes.progress = lambda: lambda n, t: None
            batch = self.submit(["a", "b"])
            query_batch(self.store, self.client, batch, 5, .2, 2)
            self.store.update(batch, 0, urls=["http://untrusted.example.com/a"])
            images, info = nodes.Fetch().execute(self.store.handle(batch), 2, 1)["result"]
            self.assertEqual(len(images), 1)
            self.assertEqual(json.loads(info)["output_indices"], [1])
            self.assertEqual(len(self.service.posts), 2)
        finally:
            os.environ.clear()
            os.environ.update(old_env)
            nodes.interrupt, nodes.progress = old_interrupt, old_progress


if __name__ == "__main__":
    unittest.main()
