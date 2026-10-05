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

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, job_key, fingerprint, base, model, count):
        if not job_key.strip() or len(job_key) > 128:
            raise ValueError("job_key must have 1-128 characters")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM batches WHERE job_key=?", (job_key,)).fetchone()
            if old:
                if old["fingerprint"] != fingerprint or old["base"] != base or old["model"] != model:
                    raise ValueError("job_key already belongs to different inputs; choose a new job_key for a new paid batch")
                return old["id"], False
            batch = str(uuid.uuid4())
            db.execute("INSERT INTO batches VALUES (?,?,?,?,?,?)", (batch, job_key, fingerprint, base, model, time.time()))
            db.executemany("INSERT INTO tasks(batch,position,status,detail) VALUES (?,?,'prepared','')", [(batch, i) for i in range(count)])
        return batch, True

    def claim(self, batch, index):
        with self.connect() as db:
            cur = db.execute("UPDATE tasks SET status='sending', detail='submit_outcome_unknown' WHERE batch=? AND position=? AND status='prepared'", (batch, index))
            return cur.rowcount == 1

    def update(self, batch, index, **fields):
        if not fields or not set(fields) <= {"status", "task_id", "detail", "urls"}:
            raise ValueError("Invalid task update")
        if "urls" in fields:
            fields["urls"] = json.dumps(fields["urls"])
        with self.connect() as db:
            db.execute("UPDATE tasks SET " + ",".join(k + "=?" for k in fields) + " WHERE batch=? AND position=?", (*fields.values(), batch, index))

    def read(self, batch):
        with self.connect() as db:
            meta = db.execute("SELECT * FROM batches WHERE id=?", (batch,)).fetchone()
            if not meta:
                raise ValueError("Unknown batch: restore local database or import existing IDs")
            tasks = [dict(r) for r in db.execute("SELECT * FROM tasks WHERE batch=? ORDER BY position", (batch,))]
        for t in tasks:
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

    def handle(self, batch):
        meta, tasks = self.read(batch)
        return json.dumps({"schema": 1, "batch_id": batch, "model": meta["model"],
            "tasks": [{k: t[k] for k in ("position", "task_id", "status", "detail")} for t in tasks]}, ensure_ascii=False)

    def resolve(self, handle):
        value = json.loads(handle)
        if value.get("schema") != 1:
            raise ValueError("Unsupported task list schema")
        batch = value["batch_id"]
        self.read(batch)
        return batch
