import hashlib
import secrets
from datetime import datetime, timezone

from melody.db import connect

TYPES = ("问题", "执行")
OPEN = "待处理"
READ = "已读"
REPLIED = "已回复"
CLOSED = "已关闭"


class CardError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def add_person(path, name):
    name = name.strip()
    if not name:
        raise CardError("invalid")
    token = secrets.token_urlsafe(24)
    with connect(path) as conn:
        exists = conn.execute("SELECT id FROM persons WHERE name = ?", (name,)).fetchone()
        if exists:
            raise CardError("exists")
        conn.execute("INSERT INTO persons (name, token) VALUES (?, ?)", (name, token))
        person_id = conn.execute("SELECT id FROM persons WHERE token = ?", (token,)).fetchone()["id"]
        conn.execute("INSERT INTO endpoints (person_id) VALUES (?)", (person_id,))
    return {"name": name, "token": token}


def set_endpoint(path, token, default_client="", code_root="", optional_clients=""):
    with connect(path) as conn:
        person = _person(conn, token)
        conn.execute(
            """UPDATE endpoints
               SET default_client = ?, code_root = ?, optional_clients = ?
               WHERE person_id = ?""",
            (default_client, code_root, optional_clients, person["id"]),
        )
    return {"name": person["name"], "default_client": default_client, "code_root": code_root}


def create_card(path, token, recipient_name, card_type, request, attachments):
    if card_type not in TYPES:
        raise CardError("invalid")
    request = request.strip()
    if not request:
        raise CardError("invalid")
    attachments = list(attachments or [])
    with connect(path) as conn:
        initiator = _person(conn, token)
        recipient = conn.execute("SELECT * FROM persons WHERE name = ?", (recipient_name,)).fetchone()
        if recipient is None:
            raise CardError("invalid")
        if recipient["id"] == initiator["id"]:
            raise CardError("invalid")
        cur = conn.execute(
            """INSERT INTO cards (public_id, type, request, status, work_branch)
               VALUES ('', ?, ?, ?, '')""",
            (card_type, request, OPEN),
        )
        card_id = cur.lastrowid
        prefix = "W" if card_type == "执行" else "Q"
        public_id = f"{prefix}-{card_id}"
        repo_name = _repo_name(attachments)
        conn.execute(
            "UPDATE cards SET public_id = ?, repo_name = ? WHERE id = ?",
            (public_id, repo_name, card_id),
        )
        conn.execute(
            "INSERT INTO card_participants (card_id, person_id, role) VALUES (?, ?, '发起人')",
            (card_id, initiator["id"]),
        )
        conn.execute(
            "INSERT INTO card_participants (card_id, person_id, role) VALUES (?, ?, '接收人')",
            (card_id, recipient["id"]),
        )
        for item in attachments:
            content = item.get("content", "")
            conn.execute(
                """INSERT INTO card_attachments
                   (card_id, source, content, content_hash, repo, basis_commit)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    card_id,
                    item.get("source", ""),
                    content,
                    hashlib.sha256(content.encode()).hexdigest(),
                    item.get("repo", ""),
                    item.get("commit", ""),
                ),
            )
        _entry(conn, card_id, initiator["id"], "本人", "补充", request)
    return show(path, token, public_id, mark_read=False)


def show(path, token, public_id, mark_read=True):
    with connect(path) as conn:
        person = _person(conn, token)
        card = _card(conn, public_id)
        role = _role(conn, card["id"], person["id"])
        if role is None:
            raise CardError("forbidden")
        if mark_read and role == "接收人":
            if card["status"] == OPEN:
                conn.execute("UPDATE cards SET status = ? WHERE id = ?", (READ, card["id"]))
            _mark_read(conn, card["id"], person["id"])
        return _present(conn, card["id"])


def hook_list(path, token):
    with connect(path) as conn:
        person = _person(conn, token)
        rows = conn.execute(
            """SELECT cards.public_id, cards.request, cards.status, sender.name AS sender
               FROM cards
               JOIN card_participants me
                 ON me.card_id = cards.id AND me.person_id = ? AND me.role = '接收人'
               JOIN card_participants owner
                 ON owner.card_id = cards.id AND owner.role = '发起人'
               JOIN persons sender ON sender.id = owner.person_id
               WHERE cards.status != ?
               ORDER BY cards.id""",
            (person["id"], CLOSED),
        ).fetchall()
        return [{"id": row["public_id"], "title": _title(row["request"]), "sender": row["sender"]} for row in rows]


def list_cards(path, token, view):
    with connect(path) as conn:
        person = _person(conn, token)
        if view == "待我处理":
            where = "me.role = '接收人' AND cards.status != ?"
            args = (person["id"], CLOSED)
        elif view == "我发出的":
            where = "me.role = '发起人' AND cards.status != ?"
            args = (person["id"], CLOSED)
        elif view == "已完成":
            where = "cards.status = ?"
            args = (person["id"], CLOSED)
        elif view == "分享给我的":
            where = "me.role = '读者'"
            args = (person["id"],)
        else:
            raise CardError("invalid")
        rows = conn.execute(
            f"""SELECT cards.id, cards.public_id, cards.type, cards.request, cards.status, cards.repo_name, me.role
                FROM cards
                JOIN card_participants me ON me.card_id = cards.id AND me.person_id = ?
                WHERE {where}
                ORDER BY cards.id""",
            args,
        ).fetchall()
        return [
            {
                "id": row["public_id"],
                "type": row["type"],
                "title": _title(row["request"]),
                "request": row["request"],
                "status": row["status"],
                "repo_name": row["repo_name"],
                "unread": _unread(conn, row["id"], person["id"], row["role"], row["status"]),
            }
            for row in rows
        ]


def reply(path, token, public_id, body, author_mode="本人"):
    body = body.strip()
    if not body:
        raise CardError("invalid")
    if author_mode not in ("本人", "经本人同意的 Agent"):
        raise CardError("invalid")
    with connect(path) as conn:
        person = _person(conn, token)
        card = _card(conn, public_id)
        if _role(conn, card["id"], person["id"]) != "接收人":
            raise CardError("forbidden")
        _entry(conn, card["id"], person["id"], author_mode, "回复", body)
        _mark_read(conn, card["id"], person["id"])
        if card["status"] != CLOSED:
            conn.execute("UPDATE cards SET status = ? WHERE id = ?", (REPLIED, card["id"]))
    return show(path, token, public_id, mark_read=False)


def follow_up(path, token, public_id, body):
    body = body.strip()
    if not body:
        raise CardError("invalid")
    with connect(path) as conn:
        person = _person(conn, token)
        card = _card(conn, public_id)
        if _role(conn, card["id"], person["id"]) != "发起人":
            raise CardError("forbidden")
        _entry(conn, card["id"], person["id"], "本人", "追问", body)
        if card["status"] == REPLIED:
            conn.execute("UPDATE cards SET status = ? WHERE id = ?", (READ, card["id"]))
    return show(path, token, public_id, mark_read=False)


def close_card(path, token, public_id, conclusion=None):
    with connect(path) as conn:
        person = _person(conn, token)
        card = _card(conn, public_id)
        if _role(conn, card["id"], person["id"]) != "发起人":
            raise CardError("forbidden")
        if card["status"] != CLOSED:
            text = (conclusion or "").strip() or _latest_reply(conn, card["id"])
            conn.execute(
                "UPDATE cards SET status = ?, conclusion = ? WHERE id = ?",
                (CLOSED, text, card["id"]),
            )
            _entry(conn, card["id"], person["id"], "本人", "状态变化", "已关闭")
    return show(path, token, public_id, mark_read=False)


def _person(conn, token):
    if not token:
        raise CardError("unauthorized")
    row = conn.execute("SELECT * FROM persons WHERE token = ?", (token,)).fetchone()
    if row is None:
        raise CardError("unauthorized")
    return row


def _card(conn, public_id):
    row = conn.execute("SELECT * FROM cards WHERE public_id = ?", (public_id,)).fetchone()
    if row is None:
        raise CardError("not_found")
    return row


def _role(conn, card_id, person_id):
    row = conn.execute(
        "SELECT role FROM card_participants WHERE card_id = ? AND person_id = ?",
        (card_id, person_id),
    ).fetchone()
    return row["role"] if row else None


def _entry(conn, card_id, author_id, author_mode, entry_type, body):
    conn.execute(
        """INSERT INTO card_entries
           (card_id, author_id, author_mode, entry_type, body, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (card_id, author_id, author_mode, entry_type, body, datetime.now(timezone.utc).isoformat()),
    )


def _mark_read(conn, card_id, person_id):
    conn.execute(
        """INSERT INTO read_marks (card_id, person_id, entry_id)
           SELECT ?, ?, COALESCE(MAX(id), 0) FROM card_entries WHERE card_id = ?
           ON CONFLICT(card_id, person_id) DO UPDATE SET entry_id = excluded.entry_id""",
        (card_id, person_id, card_id),
    )


def _unread(conn, card_id, person_id, role, status):
    if role != "接收人" or status == CLOSED:
        return False
    row = conn.execute(
        """SELECT (SELECT entry_id FROM read_marks WHERE card_id = ? AND person_id = ?) AS seen,
                  (SELECT MAX(id) FROM card_entries WHERE card_id = ?) AS latest""",
        (card_id, person_id, card_id),
    ).fetchone()
    return row["seen"] is None or row["seen"] < row["latest"]


def _latest_reply(conn, card_id):
    row = conn.execute(
        """SELECT body FROM card_entries
           WHERE card_id = ? AND entry_type = '回复'
           ORDER BY id DESC LIMIT 1""",
        (card_id,),
    ).fetchone()
    return row["body"] if row else ""


def _repo_name(attachments):
    repos = []
    for item in attachments:
        repo = (item.get("repo") or "").strip()
        if repo and repo not in repos:
            repos.append(repo)
    if len(repos) == 1:
        return repos[0]
    return ""


def _title(request):
    line = request.strip().splitlines()[0] if request.strip() else ""
    return line[:80]


def _present(conn, card_id):
    card = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    people = conn.execute(
        """SELECT persons.name, card_participants.role
           FROM card_participants
           JOIN persons ON persons.id = card_participants.person_id
           WHERE card_id = ?
           ORDER BY card_participants.role""",
        (card_id,),
    ).fetchall()
    attachments = conn.execute(
        "SELECT source, content, content_hash, repo, basis_commit FROM card_attachments WHERE card_id = ? ORDER BY id",
        (card_id,),
    ).fetchall()
    entries = conn.execute(
        """SELECT persons.name AS author, author_mode, entry_type, body, created_at
           FROM card_entries
           JOIN persons ON persons.id = card_entries.author_id
           WHERE card_id = ?
           ORDER BY card_entries.id""",
        (card_id,),
    ).fetchall()
    return {
        "id": card["public_id"],
        "type": card["type"],
        "request": card["request"],
        "status": card["status"],
        "visibility": card["visibility"],
        "repo_name": card["repo_name"],
        "conclusion": card["conclusion"],
        "work_branch": card["work_branch"],
        "title": _title(card["request"]),
        "participants": [{"name": row["name"], "role": row["role"]} for row in people],
        "attachments": [dict(row) for row in attachments],
        "entries": [dict(row) for row in entries],
    }
