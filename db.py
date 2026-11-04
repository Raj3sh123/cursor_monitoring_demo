"""SQLite storage for users, servers, and metric samples."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
HISTORY_LIMIT = 60

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ip TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER NOT NULL,
    collected_at TEXT NOT NULL,
    cpu_percent REAL,
    mem_used INTEGER,
    mem_total INTEGER,
    network_json TEXT,
    ports_json TEXT,
    FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_samples_server_time
    ON metric_samples(server_id, collected_at DESC, id DESC);
"""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@contextmanager
def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path):
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (ADMIN_USERNAME,),
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (ADMIN_USERNAME, generate_password_hash(ADMIN_PASSWORD)),
            )


def get_user(path, username):
    with connect(path) as conn:
        row = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


def list_servers(path):
    with connect(path) as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.name, s.ip, s.created_at,
                   m.cpu_percent, m.mem_used, m.mem_total, m.collected_at
            FROM servers s
            LEFT JOIN metric_samples m ON m.id = (
                SELECT id FROM metric_samples
                WHERE server_id = s.id
                ORDER BY collected_at DESC, id DESC
                LIMIT 1
            )
            ORDER BY s.name COLLATE NOCASE, s.id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_server(path, server_id):
    with connect(path) as conn:
        row = conn.execute(
            "SELECT id, name, ip, created_at FROM servers WHERE id = ?",
            (server_id,),
        ).fetchone()
    return dict(row) if row else None


def add_server(path, name, ip):
    with connect(path) as conn:
        cursor = conn.execute(
            "INSERT INTO servers (name, ip, created_at) VALUES (?, ?, ?)",
            (name, ip, utc_now()),
        )
        return cursor.lastrowid


def delete_server(path, server_id):
    with connect(path) as conn:
        cursor = conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))
        return cursor.rowcount > 0


def add_sample(path, server_id, cpu_percent, mem_used, mem_total, network_json, ports_json):
    with connect(path) as conn:
        conn.execute(
            """
            INSERT INTO metric_samples (
                server_id, collected_at, cpu_percent, mem_used, mem_total,
                network_json, ports_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                server_id,
                utc_now(),
                cpu_percent,
                mem_used,
                mem_total,
                network_json,
                ports_json,
            ),
        )
        conn.execute(
            """
            DELETE FROM metric_samples
            WHERE server_id = ?
              AND id NOT IN (
                SELECT id FROM metric_samples
                WHERE server_id = ?
                ORDER BY collected_at DESC, id DESC
                LIMIT ?
              )
            """,
            (server_id, server_id, HISTORY_LIMIT),
        )


def list_samples(path, server_id):
    with connect(path) as conn:
        rows = conn.execute(
            """
            SELECT collected_at, cpu_percent, mem_used, mem_total, network_json, ports_json
            FROM metric_samples
            WHERE server_id = ?
            ORDER BY collected_at ASC, id ASC
            """,
            (server_id,),
        ).fetchall()
    return [dict(row) for row in rows]
