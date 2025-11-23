import os
import sqlite3
from datetime import datetime
from pathlib import Path


DEFAULT_DB_FILENAME = "usage_stats.db"


def _default_db_path() -> str:
    """
    Choose a DB path that survives container rebuilds.
    Priority:
    1) DB_PATH env (absolute path on host volume is recommended).
    2) DATA_DIR env (join with default filename).
    3) /data volume inside container (bind mount this on the host).
    4) User home (Windows/dev fallback).
    """
    if os.getenv("DB_PATH"):
        return os.getenv("DB_PATH")  # type: ignore[return-value]

    data_dir = os.getenv("DATA_DIR")
    if data_dir:
        return str(Path(data_dir) / DEFAULT_DB_FILENAME)

    if os.name != "nt":
        return str(Path("/data") / DEFAULT_DB_FILENAME)

    return str(Path.home() / ".autocad_assistance" / DEFAULT_DB_FILENAME)


# Allow overriding DB location via env var (useful for Docker volume)
DB_NAME = _default_db_path()

def _ensure_db_dir() -> None:
    try:
        db_dir = os.path.dirname(DB_NAME)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    except Exception:
        # If we cannot create the directory, sqlite will raise a clear error below
        pass

def _connect():
    _ensure_db_dir()
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            command TEXT,
            file_uploaded TEXT,
            file_generated TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def record_usage(user_id, username, command, file_uploaded=None, file_generated=None):
    conn = _connect()
    cursor = conn.cursor()
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO usage_stats (user_id, username, command, file_uploaded, file_generated, timestamp)      
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, username, command, file_uploaded, file_generated, timestamp))
    conn.commit()
    conn.close()

def record_error(user_id, username, error_message, error_trace, context=""):
    conn = _connect()
    cursor = conn.cursor()
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO usage_stats (user_id, username, command, file_uploaded, file_generated, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, username, f"ERROR ({context}): {error_message}", error_trace, None, timestamp))
    conn.commit()
    conn.close()

def get_usage_stats():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT user_id), COUNT(*) FROM usage_stats")
    result = cursor.fetchone()
    conn.close()
    return result

def get_recent_errors(limit=5):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usage_stats WHERE command LIKE 'ERROR%' ORDER BY timestamp DESC LIMIT ?", (limit,))
    result = cursor.fetchall()
    conn.close()
    return result

def get_users_page(page, page_size):
    offset = page * page_size
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, username, COUNT(*) as cnt FROM usage_stats
        GROUP BY user_id, username
        ORDER BY cnt DESC
        LIMIT ? OFFSET ?
    """, (page_size, offset))
    result = cursor.fetchall()
    conn.close()
    return result

def get_user_details(user_id, offset=0, limit=5):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM usage_stats
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """, (user_id, limit, offset))
    result = cursor.fetchall()
    conn.close()
    return result

def count_user_details(user_id):
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usage_stats WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def delete_user_stats(user_id, start_date, end_date):
    """
    Удаляет записи статистики для user_id, где timestamp между start_date и end_date.
    Формат дат: YYYY-MM-DD
    """
    conn = _connect()
    cursor = conn.cursor()
    # Преобразуем даты, добавляя время для охвата всего дня
    start_dt = f"{start_date} 00:00:00"
    end_dt = f"{end_date} 23:59:59"
    cursor.execute("""
        DELETE FROM usage_stats
        WHERE user_id = ?
          AND timestamp BETWEEN ? AND ?
    """, (user_id, start_dt, end_dt))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected

def delete_all_stats():
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usage_stats")
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected
