import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS persons (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    token TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS endpoints (
    person_id INTEGER PRIMARY KEY REFERENCES persons(id),
    default_client TEXT NOT NULL DEFAULT '',
    optional_clients TEXT NOT NULL DEFAULT '',
    code_root TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    request TEXT NOT NULL,
    status TEXT NOT NULL,
    visibility TEXT NOT NULL DEFAULT '参与者',
    repo_name TEXT NOT NULL DEFAULT '',
    conclusion TEXT NOT NULL DEFAULT '',
    work_branch TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS card_participants (
    card_id INTEGER NOT NULL REFERENCES cards(id),
    person_id INTEGER NOT NULL REFERENCES persons(id),
    role TEXT NOT NULL,
    PRIMARY KEY (card_id, person_id)
);
CREATE TABLE IF NOT EXISTS card_attachments (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    repo TEXT NOT NULL DEFAULT '',
    basis_commit TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS card_entries (
    id INTEGER PRIMARY KEY,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    author_id INTEGER NOT NULL REFERENCES persons(id),
    author_mode TEXT NOT NULL,
    entry_type TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS read_marks (
    card_id INTEGER NOT NULL REFERENCES cards(id),
    person_id INTEGER NOT NULL REFERENCES persons(id),
    entry_id INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (card_id, person_id)
);
"""


def init(path):
    with connect(path) as conn:
        conn.executescript(SCHEMA)


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
