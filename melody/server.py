import json
import os
import queue
import threading
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

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
                    self._json(200, follow_up(path, self._token(payload), public_id, payload.get("body", "")))
                elif parsed.path.startswith("/cards/") and parsed.path.endswith("/close"):
                    public_id = parsed.path.split("/")[2]
                    self._json(200, close_card(path, self._token(payload), public_id, payload.get("conclusion")))
                else:
                    self._empty(404)
            except CardError as error:
                self._error(error)

        def log_message(self, fmt, *args):
            return

        def _page(self, query):
            token = self._token()
            if not token:
                self._html(_login())
                return
            try:
                name = show_name(path, token)
            except CardError:
                self._html(_login())
                return
            selected = query.get("card", [""])[0]
            body = ['<p id="signed-in">%s</p>' % _esc(name)]
            for view in VIEWS:
                body.append("<section><h2>%s</h2>" % _esc(view))
                for item in list_cards(path, token, view):
                    full = show(path, token, item["id"], mark_read=False)
                    body.append("<article>")
                    body.append("<h3>%s</h3>" % _esc(full["id"]))
                    body.append("<p>%s</p>" % _esc(full["request"]))
                    for attachment in full["attachments"]:
                        body.append("<p>%s</p>" % _esc(attachment["content"]))
                    body.append('<p><a href="/?card=%s">打开</a></p>' % _esc(full["id"]))
                    body.append("</article>")
                body.append("</section>")
            if selected:
                full = show(path, token, selected)
                body.append("<article>")
                body.append("<h2>%s</h2>" % _esc(full["id"]))
                body.append("<p>%s</p>" % _esc(full["status"]))
                body.append("<p>%s</p>" % _esc(full["request"]))
                role = next(person["role"] for person in full["participants"] if person["name"] == name)
                if role == "接收人" and full["status"] != "已关闭":
                    endpoint = _endpoint(path, token)
                    link = build(endpoint["default_client"] or "claude", full["id"], full["repo_name"], endpoint["code_root"])
                    body.append('<p><a href="%s">交给我的 Agent 处理</a></p>' % _esc(link))
                    body.append(_form(f"/cards/{full['id']}/reply", "回复"))
                if role == "发起人" and full["status"] != "已关闭":
                    body.append(_form(f"/cards/{full['id']}/close", "收到"))
                body.append("</article>")
            self._html(template.replace("__BODY__", "\n".join(body)))

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
    return """
    <form method="post" action="/session">
      <label>个人令牌 <input name="token"></label>
      <button type="submit">进入</button>
    </form>
    """


def _form(action, label):
    return (
        f'<form method="post" action="{_esc(action)}">'
        f'<label>{_esc(label)} <textarea name="body"></textarea></label>'
        f'<button type="submit">{_esc(label)}</button>'
        f"</form>"
    )


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
