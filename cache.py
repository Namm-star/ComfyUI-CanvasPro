"""Bounded result-image cache; task identities and output files are never removed."""
import shutil
import sqlite3
import time


class CacheStore:
    def init_cache(self, db):
        db.execute("CREATE TABLE IF NOT EXISTS cache_policy (id INTEGER PRIMARY KEY,limit_mb INTEGER,max_age_days INTEGER)")
        db.execute("INSERT OR IGNORE INTO cache_policy VALUES (1,1024,7)")
        db.execute("CREATE TABLE IF NOT EXISTS cache_entries (batch TEXT,position INTEGER,cached_at REAL,output_at REAL,PRIMARY KEY(batch,position))")
        # Existing queue delivery marks are evidence of output. Unmarked legacy
        # blobs stay protected, since caching alone does not prove delivery.
        db.execute("""INSERT OR IGNORE INTO cache_entries
            SELECT t.batch,t.position,b.created,
              CASE WHEN EXISTS (SELECT 1 FROM queue_progress p WHERE p.batch=t.batch AND p.position=t.position AND p.delivered=1) THEN b.created ELSE NULL END
            FROM tasks t JOIN batches b ON b.id=t.batch WHERE t.image IS NOT NULL""")

    def cache_policy(self):
        with self.connect() as db:
            row=db.execute("SELECT limit_mb,max_age_days FROM cache_policy WHERE id=1").fetchone()
        return dict(row)

    def set_cache_policy(self, limit_mb, max_age_days):
        if type(limit_mb) is not int or not 1<=limit_mb<=65536:
            raise ValueError("缓存容量须为1–65536 MB")
        if type(max_age_days) is not int or not 0<=max_age_days<=3650:
            raise ValueError("缓存保留天数须为0–3650，0表示不按天清理")
        with self.connect() as db:
            db.execute("UPDATE cache_policy SET limit_mb=?,max_age_days=? WHERE id=1",(limit_mb,max_age_days))

    def cache_info(self):
        with self.connect() as db:
            total=db.execute("SELECT COUNT(*) n,COALESCE(SUM(length(image)),0) bytes FROM tasks WHERE image IS NOT NULL").fetchone()
            rows=self.cache_candidates(db)
            free=db.execute("PRAGMA freelist_count").fetchone()[0]*db.execute("PRAGMA page_size").fetchone()[0]
        eligible=sum(row["bytes"] for row in rows)
        policy=self.cache_policy()
        return {"policy":policy,"cached_images":total["n"],"cache_bytes":total["bytes"],
            "clearable_bytes":eligible,"protected_bytes":total["bytes"]-eligible,
            "over_limit":total["bytes"]>policy["limit_mb"]*1024**2,
            "database_bytes":self.path.stat().st_size,"reclaimable_bytes":free}

    @staticmethod
    def cache_candidates(db):
        return db.execute("""SELECT t.batch,t.position,length(t.image) bytes,c.output_at
            FROM tasks t JOIN cache_entries c ON c.batch=t.batch AND c.position=t.position
            WHERE t.image IS NOT NULL AND t.status='succeeded' AND c.output_at IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM task_queues q LEFT JOIN queue_progress p
              ON p.queue_key=q.queue_key AND p.batch=t.batch AND p.position=t.position
              WHERE q.batch=t.batch AND COALESCE(p.delivered,0)=0)
            ORDER BY c.output_at,c.cached_at,t.batch,t.position""").fetchall()

    def mark_output(self, outputs):
        outputs=set(outputs)
        try:
            with self.connect() as db:
                db.executemany("UPDATE cache_entries SET output_at=? WHERE batch=? AND position=?",[(time.time(),batch,index) for batch,index in outputs])
            return self.maintain_cache(protect=outputs)
        except (sqlite3.Error,OSError):
            # Maintenance must not turn a successfully obtained image into a
            # failed generation. Leave its cache intact for a later attempt.
            return {"maintenance":"deferred_storage_error"}

    def maintain_cache(self, clear_all=False, protect=()):
        protect=set(protect)
        policy=self.cache_policy()
        limit=policy["limit_mb"]*1024**2
        cutoff=time.time()-policy["max_age_days"]*86400 if policy["max_age_days"] else None
        removed=0;released=0;current_protected=0
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            before=db.execute("SELECT COALESCE(SUM(length(image)),0) FROM tasks").fetchone()[0]
            remaining=before
            for row in self.cache_candidates(db):
                pair=(row["batch"],row["position"])
                if pair in protect:
                    current_protected+=row["bytes"]
                    continue
                expired=cutoff is not None and row["output_at"]<cutoff
                if clear_all or expired or remaining>limit:
                    db.execute("UPDATE tasks SET image=NULL WHERE batch=? AND position=?",pair)
                    removed+=1;released+=row["bytes"];remaining-=row["bytes"]
        compact=self.reclaim_cache_space(automatic=not clear_all) if removed or clear_all else "not_needed"
        return {"removed_images":removed,"released_cache_bytes":released,"current_output_protected_bytes":current_protected,"compaction":compact,**self.cache_info()}

    def reclaim_cache_space(self, automatic=True):
        # Work on this single SQLite file only. Never walk/delete output folders.
        db=sqlite3.connect(self.path,timeout=1,isolation_level=None)
        try:
            free=db.execute("PRAGMA freelist_count").fetchone()[0]
            if not free:return "not_needed"
            mode=db.execute("PRAGMA auto_vacuum").fetchone()[0]
            if mode==0:
                size=self.path.stat().st_size
                if automatic and size>256*1024**2:return "manual_compaction_required"
                if shutil.disk_usage(self.root).free<2*size+8*1024**2:return "insufficient_free_space_for_compaction"
                db.execute("PRAGMA auto_vacuum=INCREMENTAL")
                db.execute("VACUUM")
            elif mode==2:
                db.execute("PRAGMA incremental_vacuum").fetchall()
            return "completed"
        except (sqlite3.Error,OSError):
            return "database_busy_or_compaction_unavailable"
        finally:
            db.close()
