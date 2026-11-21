"""Transactional submit intent and durable, secret-free task handles."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from .config import data_dir
from .cache import CacheStore


class Store(CacheStore):
    def __init__(self, root=None):
        self.root = root or data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "tasks.sqlite3"
        with self.connect() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
                db.execute("PRAGMA auto_vacuum=INCREMENTAL")
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

            if "submit_receipt" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN submit_receipt TEXT DEFAULT '{}'")
            if 'progress' not in columns:db.execute("ALTER TABLE tasks ADD COLUMN progress INTEGER")
            if 'failure_reason' not in columns:db.execute("ALTER TABLE tasks ADD COLUMN failure_reason TEXT DEFAULT ''")
            if "image" not in columns:
                db.execute("ALTER TABLE tasks ADD COLUMN image BLOB")
            tracking = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='queue_progress'").fetchone()
            db.execute("CREATE TABLE IF NOT EXISTS queue_progress (queue_key TEXT,batch TEXT,position INTEGER,delivered INTEGER DEFAULT 0,reported_status TEXT DEFAULT '',PRIMARY KEY(queue_key,batch,position))")
            if not tracking:
                # Pre-upgrade cached images have already been obtained. Keep them
                # in history instead of emitting them all on the first new query.
                db.execute("INSERT INTO queue_progress SELECT q.queue_key,t.batch,t.position,1,'' FROM task_queues q JOIN tasks t ON t.batch=q.batch WHERE t.status='succeeded' AND t.image IS NOT NULL")
            self.init_cache(db)

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
        if not fields or not set(fields) <= {"status", "task_id", "detail", "urls", "image", "submit_receipt", "progress", "failure_reason"}:
            raise ValueError("Invalid task update")
        if "submit_receipt" in fields:fields["submit_receipt"]=json.dumps(fields["submit_receipt"],ensure_ascii=False)
        if "urls" in fields:
            fields["urls"] = json.dumps(fields["urls"])
        with self.connect() as db:
            db.execute("UPDATE tasks SET " + ",".join(k + "=?" for k in fields) + " WHERE batch=? AND position=?", (*fields.values(), batch, index))
            if fields.get("image") is not None:
                db.execute("INSERT INTO cache_entries VALUES (?,?,?,NULL) ON CONFLICT(batch,position) DO UPDATE SET cached_at=excluded.cached_at",(batch,index,time.time()))

    def read(self, batch, include_images=True, positions=None):
        with self.connect() as db:
            meta = db.execute("SELECT * FROM batches WHERE id=?", (batch,)).fetchone()
            if not meta:
                raise ValueError("Unknown batch: restore local database or import existing IDs")
            columns="*" if include_images else "batch,position,status,task_id,detail,urls,model,submit_receipt,progress,failure_reason,CASE WHEN image IS NOT NULL THEN 1 ELSE NULL END AS image"
            params=[batch]
            where=""
            if positions is not None:
                where=" AND position IN ("+",".join("?" for _ in positions)+")" if positions else " AND 0"
                params.extend(positions)
            tasks = [dict(r) for r in db.execute("SELECT "+columns+" FROM tasks WHERE batch=?"+where+" ORDER BY position", params)]
        for t in tasks:
            t["model"] = t["model"] or meta["model"]
            t["urls"] = json.loads(t["urls"])
            t["submit_receipt"]=json.loads(t.get("submit_receipt") or "{}")
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

    def queue_work(self,queue_key,include_history=False):
        where="" if include_history else """AND (
            (t.status='succeeded' AND COALESCE(p.delivered,0)=0) OR
            (t.status!='succeeded' AND t.status!='failed' AND t.task_id IS NOT NULL) OR
            ((t.status='failed' OR t.task_id IS NULL) AND t.status!='succeeded'
             AND COALESCE(p.reported_status,'')!=CASE WHEN t.status='sending' THEN 'submit_unknown' ELSE t.status END))"""
        with self.connect() as db:
            rows=db.execute("""SELECT t.batch,t.position FROM task_queues q JOIN tasks t ON t.batch=q.batch
                LEFT JOIN queue_progress p ON p.queue_key=q.queue_key AND p.batch=t.batch AND p.position=t.position
                WHERE q.queue_key=? """+where+" ORDER BY q.added,q.batch,t.position",(queue_key.strip(),)).fetchall()
        batches={}
        for row in rows:batches.setdefault(row["batch"],[]).append(row["position"])
        return batches

    def queue_summary(self,queue_key):
        with self.connect() as db:
            rows=db.execute("""SELECT t.status,COUNT(*) n,SUM(COALESCE(p.delivered,0)) delivered
                FROM task_queues q JOIN tasks t ON t.batch=q.batch
                LEFT JOIN queue_progress p ON p.queue_key=q.queue_key AND p.batch=t.batch AND p.position=t.position
                WHERE q.queue_key=? GROUP BY t.status""",(queue_key.strip(),)).fetchall()
        counts={}
        for row in rows:
            status="submit_unknown" if row["status"]=="sending" else row["status"]
            counts[status]=counts.get(status,0)+row["n"]
        return {"total_tasks":sum(counts.values()),"already_output":sum(row["delivered"] for row in rows),"counts":counts}

    def record_queue_run(self,queue_key,outputs,notices,include_history=False):
        accepted=[]
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for batch,index in outputs:
                old=db.execute("SELECT delivered FROM queue_progress WHERE queue_key=? AND batch=? AND position=?",(queue_key.strip(),batch,index)).fetchone()
                if include_history or not old or not old["delivered"]:accepted.append((batch,index))
                db.execute("INSERT INTO queue_progress VALUES (?,?,?,1,'') ON CONFLICT(queue_key,batch,position) DO UPDATE SET delivered=1",(queue_key.strip(),batch,index))
            for batch,index,status in notices:
                db.execute("INSERT INTO queue_progress VALUES (?,?,?,0,?) ON CONFLICT(queue_key,batch,position) DO UPDATE SET reported_status=excluded.reported_status",(queue_key.strip(),batch,index,status))
        return set(accepted)

    def resources(self, batch, positions=None):
        from urllib.parse import urljoin, urlsplit
        meta,tasks=self.read(batch,include_images=False,positions=positions)
        result=[]
        base=urlsplit(meta["base"])
        for t in tasks:
            urls=[urljoin(meta["base"]+"/",url) for url in t["urls"]]
            result.append({"index":t["position"],"model":t["model"],"task_id":t["task_id"],
                "submission_receipt":t.get("submit_receipt",{}),"resource_urls":urls,"cached_image":t.get("image") is not None,
                "resources":[{"url":url,"requires_api_key":not t["model"].endswith("-W") and urlsplit(url).netloc==base.netloc and urlsplit(url).scheme==base.scheme} for url in urls]})
            if type(t.get('progress')) is int and 0<=t['progress']<=100:result[-1]['progress']=t['progress']
            if t.get('failure_reason'):result[-1]['error_message']=t['failure_reason']
        return result

    def handle(self, batch, positions=None):
        meta, tasks = self.read(batch,include_images=False,positions=positions)
        resources=self.resources(batch,positions=positions)
        return json.dumps({"schema": 1, "batch_id": batch, "model": meta["model"],
            "tasks": [{**{k: t[k] for k in ("position", "model", "task_id", "status", "detail")}, **resources[i]} for i,t in enumerate(tasks)]}, ensure_ascii=False)

    def resolve(self, handle):
        value = json.loads(handle)
        if value.get("schema") != 1:
            raise ValueError("Unsupported task list schema")
        batch = value["batch_id"]
        self.read(batch,include_images=False)
        return batch
