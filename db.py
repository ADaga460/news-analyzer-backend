# db.py
import sqlite3
import threading
import time
from typing import Optional

DB_PATH = "jobs.db"
_lock = threading.Lock()

def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    with _lock:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            type TEXT,
            status TEXT,
            result TEXT,
            created_at REAL
        )
        """)
        conn.commit()
        conn.close()

def create_job(job_id: str, job_type: str):
    with _lock:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("INSERT OR REPLACE INTO jobs (id,type,status,result,created_at) VALUES (?,?,?,?,?)",
                    (job_id, job_type, "processing", "", time.time()))
        conn.commit()
        conn.close()

def set_job_result(job_id: str, status: str, result: str):
    with _lock:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("UPDATE jobs SET status=?, result=? WHERE id=?", (status, result, job_id))
        conn.commit()
        conn.close()

def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT id,type,status,result,created_at FROM jobs WHERE id=?", (job_id,))
        row = cur.fetchone()
        conn.close()
    if not row:
        return None
    return {"id": row[0], "type": row[1], "status": row[2], "result": row[3], "created_at": row[4]}
