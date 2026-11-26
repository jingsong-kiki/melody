import json
import os
import queue
import threading
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from melody.card import CardError, add_person, close_card, create_card, follow_up, hook_list, list_cards, reply, set_endpoint, show
from melody.db import connect, init
from melody.deeplink import build

VIEWS = ("待我处理", "我发出的", "已完成")


class Hub:
    def __init__(self):
        self._lock = threading.Lock()
        self._waiters = []

    def listen(self, name):
        item = queue.Queue()
        with self._lock:
            self._waiters.append((name, item))
        return item

    def unlisten(self, name, item):
        with self._lock:
            self._waiters = [(who, waiting) for who, waiting in self._waiters if not (who == name and waiting is item)]

    def publish(self, name, payload):
        with self._lock:
            targets = [waiting for who, waiting in self._waiters if who == name]
        for waiting in targets:
            waiting.put(payload)


def make_server(path, host="127.0.0.1", port=0):
    init(path)
    hub = Hub()
    with open(os.path.join(os.path.dirname(__file__), "inbox.html"), encoding="utf-8") as handle:
        template = handle.read()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path in ("/", "/inbox"):
                    self._page(parse_qs(parsed.query))
                elif parsed.path == "/events":
                    self._events()
                elif parsed.path == "/hook":
                    self._json(200, {"items": hook_list(path, self._token())})
                elif parsed.path == "/cards":
                    view = parse_qs(parsed.query).get("view", ["待我处理"])[0]
                    self._json(200, {"cards": list_cards(path, self._token(), view)})
                elif parsed.path.startswith("/cards/"):
                    public_id = parsed.path.split("/")[2]
                    self._json(200, show(path, self._token(), public_id))
                else:
                    self._empty(404)
            except CardError as error:
                self._error(error)

        def do_POST(self):
            parsed = urlparse(self.path)
            payload = self._payload()
            try:
                if parsed.path == "/persons":
                    self._json(201, add_person(path, payload.get("name", "")))
                elif parsed.path == "/session":
                    token = payload.get("token", "")
                    show_name(path, token)
                    self._cookie(token)
                elif parsed.path == "/endpoint":
                    self._json(200, set_endpoint(path, self._token(payload), payload.get("default_client", ""), payload.get("code_root", "")))
                elif parsed.path == "/cards":
                    card = create_card(
                        path,
                        self._token(payload),
                        payload.get("recipient", ""),
                        payload.get("type", ""),
                        payload.get("request", ""),
                        payload.get("attachments") or [],
                    )
                    recipient = next(person["name"] for person in card["participants"] if person["role"] == "接收人")
                    hub.publish(recipient, {"id": card["id"], "title": card["title"], "sender": _sender(card)})
                    self._json(201, card)
                elif parsed.path.startswith("/cards/") and parsed.path.endswith("/reply"):
                    public_id = parsed.path.split("/")[2]
                    card = reply(path, self._token(payload), public_id, payload.get("body", ""), payload.get("author_mode", "本人"))
                    self._wrote(card, payload)
                elif parsed.path.startswith("/cards/") and parsed.path.endswith("/follow-up"):
                    public_id = parsed.path.split("/")[2]
                    self._wrote(follow_up(path, self._token(payload), public_id, payload.get("body", "")), payload)
                elif parsed.path.startswith("/cards/") and parsed.path.endswith("/close"):
                    public_id = parsed.path.split("/")[2]
                    self._wrote(close_card(path, self._token(payload), public_id, payload.get("conclusion")), payload)
                else:
                    self._empty(404)
            except CardError as error:
                self._error(error)

        def log_message(self, fmt, *args):
            return

        def _page(self, query):
            token = self._token()
            if not token:
                self._html(template.replace("__BODY__", _login()))
                return
            try:
                name = show_name(path, token)
            except CardError:
                self._html(template.replace("__BODY__", _login()))
                return
            selected = query.get("card", [""])[0]
            opened = show(path, token, selected) if selected else None
            requested = query.get("view", [""])[0]
            if requested in VIEWS:
                view = requested
            elif opened:
                view = _queue_for(opened, name)
            else:
                view = VIEWS[0]
            queues = []
            for label in VIEWS:
                rows = []
                unread = 0
                for item in list_cards(path, token, label):
                    full = show(path, token, item["id"], mark_read=False)
                    if item["unread"]:
                        unread += 1
                    rows.append((item, full))
                queues.append((label, rows, unread))
            self._html(template.replace("__BODY__", _inbox(name, view, queues, opened, path, token)))

        def _events(self):
            token = self._token()
            try:
                name = show_name(path, token)
            except CardError as error:
                self._error(error)
                return
            waiting = hub.listen(name)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                payload = waiting.get(timeout=5)
                data = json.dumps(payload, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
            except (queue.Empty, BrokenPipeError, ConnectionResetError):
                return
            finally:
                hub.unlisten(name, waiting)

        def _wrote(self, card, payload):
            if payload.get("_form"):
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return
            self._json(200, card)

        def _cookie(self, token):
            self.send_response(303)
            self.send_header("Set-Cookie", f"melody_token={token}; HttpOnly; Path=/; SameSite=Lax")
            self.send_header("Location", "/")
            self.end_headers()

        def _token(self, payload=None):
            header = self.headers.get("Authorization", "")
            if header.startswith("Bearer "):
                return header[7:]
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            if "melody_token" in cookie:
                return cookie["melody_token"].value
            if payload and payload.get("token"):
                return payload["token"]
            return ""

        def _payload(self):
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length).decode() if length else ""
            kind = self.headers.get("Content-Type", "")
            if "application/json" in kind:
                return json.loads(raw or "{}")
            parsed = {key: values[-1] for key, values in parse_qs(raw).items()}
            parsed["_form"] = True
            if "attachments" in parsed:
                parsed["attachments"] = json.loads(parsed["attachments"])
            return parsed

        def _json(self, code, obj):
            raw = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _html(self, text):
            raw = text.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _empty(self, code):
            self.send_response(code)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _error(self, error):
            if error.code == "unauthorized":
                self._empty(401)
                return
            codes = {"forbidden": 403, "not_found": 404, "invalid": 400, "exists": 409}
            self._json(codes.get(error.code, 400), {"error": error.code})

    httpd = ThreadingHTTPServer((host, port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def show_name(path, token):
    with connect(path) as conn:
        row = conn.execute("SELECT name FROM persons WHERE token = ?", (token,)).fetchone()
    if row is None:
        raise CardError("unauthorized")
    return row["name"]


def _endpoint(path, token):
    with connect(path) as conn:
        row = conn.execute(
            """SELECT default_client, code_root FROM endpoints
               JOIN persons ON persons.id = endpoints.person_id
               WHERE persons.token = ?""",
            (token,),
        ).fetchone()
    if row is None:
        return {"default_client": "", "code_root": ""}
    return {"default_client": row["default_client"], "code_root": row["code_root"]}


def _sender(card):
    return next(person["name"] for person in card["participants"] if person["role"] == "发起人")


def _esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _login():
    return (
        '<form class="login" method="post" action="/session">'
        '<label>个人令牌 <input name="token" autocomplete="off"></label>'
        '<button class="send" type="submit">进入</button>'
        "</form>"
    )


def _form(action, label, placeholder):
    return (
        f'<form method="post" action="{_esc(action)}">'
        f'<label class="clip">{_esc(label)}</label>'
        f'<textarea name="body" placeholder="{_esc(placeholder)}"></textarea>'
        f'<button class="send" type="submit">{_esc(label)}</button>'
        "</form>"
    )


def _queue_for(card, name):
    if card["status"] == "已关闭":
        return "已完成"
    role = next(person["role"] for person in card["participants"] if person["name"] == name)
    if role == "接收人":
        return "待我处理"
    return "我发出的"


def _inbox(name, view, queues, opened, path, token):
    body = ['<div class="shell" data-view="%s">' % _esc(view), '<div class="window">', '<aside class="rail">']
    body.append('<div class="colhead">melody</div>')
    body.append('<nav class="nav" aria-label="收件">')
    for label, _rows, unread in queues:
        current = ' aria-current="page"' if label == view else ""
        badge = '<span class="badge">%d</span>' % unread if label == "待我处理" and unread else ""
        body.append('<a href="/?view=%s"%s>%s%s</a>' % (quote(label), current, _esc(label), badge))
    body.append("</nav>")
    body.append(
        '<p id="signed-in" class="me"><span class="avatar %s">%s</span>%s</p>'
        % (_tone(name), _esc(_initial(name)), _esc(name))
    )
    body.append("</aside>")
    body.append('<div class="list">')
    selected = opened["id"] if opened else ""
    for label, rows, _unread in queues:
        body.append("<section><h2>%s</h2>" % _esc(label))
        if rows:
            body.append('<ul class="rows">')
            for item, full in rows:
                body.append(_row(label, item, full, selected))
            body.append("</ul>")
        else:
            body.append('<p class="empty">没有事项卡</p>')
        body.append("</section>")
    body.append("</div>")
    body.append(_reader(opened, name, path, token))
    body.append("</div></div>")
    return "\n".join(body)


def _row(view, item, full, selected):
    sender = next(person["name"] for person in full["participants"] if person["role"] == "发起人")
    latest = full["entries"][-1]["created_at"] if full["entries"] else ""
    state = "unread" if item["unread"] else "read"
    current = ' aria-current="true"' if full["id"] == selected else ""
    pip = '<i class="pip"></i><span class="clip">未读</span>' if item["unread"] else ""
    held = "".join('<p class="clip">%s</p>' % _esc(attachment["content"]) for attachment in full["attachments"])
    request = " ".join(full["request"].split())
    extra = request[len(full["title"]):].strip()
    preview = '<span class="preview">%s</span>' % _esc(extra) if extra else ""
    return (
        "<li><article>"
        '<a class="row %s" href="/?view=%s&amp;card=%s"%s>'
        '<span class="avatar %s">%s</span>'
        '<span class="copy"><span class="who">%s%s</span><span class="subject">%s</span>%s</span>'
        '<span class="when">%s</span>'
        "</a>%s</article></li>"
        % (
            state,
            quote(view),
            quote(full["id"]),
            current,
            _tone(sender),
            _esc(_initial(sender)),
            pip,
            _esc(sender),
            _esc(full["title"]),
            preview,
            _esc(_when(latest)),
            held,
        )
    )


def _reader(opened, name, path, token):
    if not opened:
        return '<article class="reader"><div class="colhead"></div><p class="empty">选一张卡</p></article>'
    initiator = next(person["name"] for person in opened["participants"] if person["role"] == "发起人")
    recipient = next(person["name"] for person in opened["participants"] if person["role"] == "接收人")
    role = next(person["role"] for person in opened["participants"] if person["name"] == name)
    kind = "执行卡" if opened["type"] == "执行" else "问题卡"
    meta = "发给 %s" % recipient
    if opened["repo_name"]:
        meta += " · %s" % opened["repo_name"]
    if opened["visibility"] == "参与者":
        meta += " · 仅参与者"
    closed = opened["status"] == "已关闭"
    parts = [
        '<article class="reader">',
        '<h2><span class="title">%s</span><span>%s · %s · %s</span></h2>'
        % (_esc(opened["title"]), _esc(opened["id"]), _esc(kind), _esc(opened["status"])),
        '<div class="scroll"><div class="thread">',
        '<div class="from"><span class="avatar %s">%s</span><div><div class="name">%s</div><div class="meta">%s</div></div></div>'
        % (_tone(initiator), _esc(_initial(initiator)), _esc(initiator), _esc(meta)),
    ]
    for attachment in opened["attachments"]:
        parts.append(_attachment(attachment))
    parts.append("<section><h3>往来</h3><ol class=\"log\">")
    for entry in opened["entries"]:
        who = entry["author"]
        mode = "" if entry["author_mode"] == "本人" else entry["author_mode"]
        parts.append(
            '<li class="msg"><span class="avatar %s">%s</span><div>'
            '<div class="msg-h"><b>%s</b><span>%s</span><time>%s</time></div><p>%s</p></div></li>'
            % (
                _tone(who),
                _esc(_initial(who)),
                _esc(who),
                _esc(entry["entry_type"] if not mode else "%s · %s" % (entry["entry_type"], mode)),
                _esc(_when(entry["created_at"])),
                _esc(entry["body"]),
            )
        )
    parts.append("</ol></section></div></div>")
    parts.append('<div class="composer">')
    if role == "接收人":
        parts.append(_form("/cards/%s/reply" % opened["id"], "回复", "写回这张卡"))
        if not closed:
            endpoint = _endpoint(path, token)
            client = endpoint["default_client"] or "claude"
            link = build(client, opened["id"], opened["repo_name"], endpoint["code_root"])
            parts.append('<a class="ghost" href="%s">交给我的 Agent 处理<em>%s</em></a>' % (_esc(link), _esc(_client_name(client))))
    if role == "发起人":
        parts.append(_form("/cards/%s/follow-up" % opened["id"], "追问", "写下追问"))
        if not closed:
            parts.append(
                '<form class="plain" method="post" action="%s"><button class="ghost" type="submit">收到</button></form>'
                % _esc("/cards/%s/close" % opened["id"])
            )
    parts.append("</div></article>")
    return "".join(parts)


def _attachment(item):
    source = item["source"] or "附件"
    ext = source.rsplit(".", 1)[-1][:4] if "." in source else "file"
    content = item["content"]
    head = (
        '<div class="file"><span class="ext">%s</span><span><b>%s</b>'
        % (_esc(ext), _esc(source))
    )
    if "\n" in content or len(content) > 80:
        return head + "</span></div>" + '<pre class="attachment">%s</pre>' % _esc(content)
    return head + "<small>%s</small></span></div>" % _esc(content)


def _client_name(client):
    return {"claude": "Claude Code", "codex": "Codex", "cursor": "Cursor"}.get(client, client)


def _when(iso):
    if not iso:
        return ""
    moment = datetime.fromisoformat(iso)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(timezone(timedelta(hours=8)))
    now = datetime.now(timezone(timedelta(hours=8)))
    if local.date() == now.date():
        return local.strftime("%H:%M")
    if local.year == now.year:
        return "%d/%d" % (local.month, local.day)
    return local.strftime("%Y-%m-%d")


def _tone(name):
    return ("tone-a", "tone-c", "tone-b")[sum(ord(char) for char in name) % 3]


def _initial(name):
    return name[:1] if name else "?"


def main(argv):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.environ.get("MELODY_DB", "melody.sqlite"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    init(args.db)
    print(f"http://{args.host}:{args.port}")
    httpd = make_server(args.db, args.host, args.port)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        httpd.shutdown()
