"""Transactional submit intent and durable, secret-free task handles."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from .config import data_dir


class Store:
    def __init__(self, root=None):
        self.root = root or data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "tasks.sqlite3"
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS batches (
              id TEXT PRIMARY KEY, job_key TEXT UNIQUE, fingerprint TEXT, base TEXT, model TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS tasks (
              batch TEXT, position INTEGER, status TEXT, task_id TEXT, detail TEXT,
              urls TEXT DEFAULT '[]', PRIMARY KEY(batch, position));
            """)
            db.execute("CREATE TABLE IF NOT EXISTS task_queues (queue_key TEXT, batch TEXT, added REAL, PRIMARY KEY(queue_key,batch))")
            db.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in db.execute("PRAGMA table_info(tasks)")}
            if "model" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN model TEXT")

            if "image" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN image BLOB")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, job_key, fingerprint, base, model, count, models=None):
        if not job_key.strip() or len(job_key) > 128:
            raise ValueError("job_key must have 1-128 characters")
        if models is not None and len(models) != count:
            raise ValueError("Task model count mismatch")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM batches WHERE job_key=?", (job_key,)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint or old["base"] != base or old["model"] != model:
                    raise ValueError("job_key already belongs to different inputs; choose a new job_key for a new paid batch")
                return old["id"], False
            batch = str(uuid.uuid4())
            db.execute("INSERT INTO batches VALUES (?,?,?,?,?,?)", (batch, job_key, fingerprint, base, model, time.time()))
            db.executemany("INSERT INTO tasks(batch,position,status,detail,model) VALUES (?,?,'prepared','',?)", [(batch, i, models[i] if models is not None else model) for i in range(count)])
        return batch, True

    def claim(self, batch, index):
        with self.connect() as db:
            cur = db.execute("UPDATE tasks SET status='sending', detail='submit_outcome_unknown' WHERE batch=? AND position=? AND status='prepared'", (batch, index))
            return cur.rowcount == 1

    def update(self, batch, index, **fields):
        if not fields or not set(fields) <= {"status", "task_id", "detail", "urls", "image"}:
            raise ValueError("Invalid task update")
        if "urls" in fields:
            fields["urls"] = json.dumps(fields["urls"])
        with self.connect() as db:
            db.execute("UPDATE tasks SET " + ",".join(k + "=?" for k in fields) + " WHERE batch=? AND position=?", (*fields.values(), batch, index))

    def read(self, batch, include_images=True):
        with self.connect() as db:
            meta = db.execute("SELECT * FROM batches WHERE id=?", (batch,)).fetchone()
            if not meta:
                raise ValueError("Unknown batch: restore local database or import existing IDs")
            columns="*" if include_images else "batch,position,status,task_id,detail,urls,model,CASE WHEN image IS NOT NULL THEN 1 ELSE NULL END AS image"
            tasks = [dict(r) for r in db.execute("SELECT "+columns+" FROM tasks WHERE batch=? ORDER BY position", (batch,))]
        for t in tasks:
            t["model"] = t["model"] or meta["model"]
            t["urls"] = json.loads(t["urls"])
            if t["status"] == "sending":
                t["status"] = "submit_unknown"
        return dict(meta), tasks

    def by_key(self, job_key):
        with self.connect() as db:
            row = db.execute("SELECT id FROM batches WHERE job_key=?", (job_key,)).fetchone()
        if not row:
            raise ValueError("No saved batch for job_key")
        return row[0]

    def add_queue(self,queue_key,batch):
        if not isinstance(queue_key,str) or not queue_key.strip() or len(queue_key)>128:raise ValueError("队列名称须为1–128个字符")
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO task_queues VALUES (?,?,?)",(queue_key.strip(),batch,time.time()))

    def queue_batches(self,queue_key):
        with self.connect() as db:
            rows=db.execute("SELECT batch FROM task_queues WHERE queue_key=? ORDER BY added,batch",(queue_key.strip(),)).fetchall()
        return [row[0] for row in rows]

    def resources(self, batch):
        from urllib.parse import urljoin, urlsplit
        meta,tasks=self.read(batch,include_images=False)
        result=[]
        base=urlsplit(meta["base"])
        for t in tasks:
            urls=[urljoin(meta["base"]+"/",url) for url in t["urls"]]
            result.append({"index":t["position"],"model":t["model"],"task_id":t["task_id"],
                "resource_urls":urls,"cached_image":t.get("image") is not None,
                "resources":[{"url":url,"requires_api_key":not t["model"].endswith("-W") and urlsplit(url).netloc==base.netloc and urlsplit(url).scheme==base.scheme} for url in urls]})
        return result

    def handle(self, batch):
        meta, tasks = self.read(batch,include_images=False)
        resources=self.resources(batch)
        return json.dumps({"schema": 1, "batch_id": batch, "model": meta["model"],
            "tasks": [{**{k: t[k] for k in ("position", "model", "task_id", "status", "detail")}, **resources[i]} for i,t in enumerate(tasks)]}, ensure_ascii=False)

    def resolve(self, handle):
        value = json.loads(handle)
        if value.get("schema") != 1:
            raise ValueError("Unsupported task list schema")
        batch = value["batch_id"]
        self.read(batch,include_images=False)
        return batch
