import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from melody.server import main as serve_main


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("melody person|ask|show|reply|inbox|endpoint|serve")
        return 0
    command, rest = argv[0], argv[1:]
    if command == "serve":
        serve_main(rest)
        return 0
    if command == "person" and rest[:1] == ["add"]:
        return person_add(rest[1:])
    if command == "ask":
        return ask(rest)
    if command == "show":
        return show_cmd(rest)
    if command == "reply":
        return reply_cmd(rest)
    if command == "inbox" and rest[:1] == ["--hook"]:
        return hook()
    if command == "endpoint":
        return endpoint(rest)
    print("未知命令", file=sys.stderr)
    return 2


def person_add(argv):
    parser = argparse.ArgumentParser(prog="melody person add")
    parser.add_argument("name")
    args = parser.parse_args(argv)
    created = request("POST", "/persons", {"name": args.name}, token=False)
    config = load_config()
    config.update({"url": base_url(), "token": created["token"], "name": created["name"]})
    save_config(config)
    print(created["token"])
    return 0


def ask(argv):
    parser = argparse.ArgumentParser(prog="melody ask")
    parser.add_argument("--to", required=True)
    parser.add_argument("--type", required=True, choices=("问题", "执行"))
    parser.add_argument("--request", required=True)
    parser.add_argument("--attach-json", action="append", default=[])
    parser.add_argument("--omit", action="append", default=[])
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args(argv)
    attachments = [json.loads(item) for item in args.attach_json]
    print("附带：")
    for item in attachments:
        print(f"- {item.get('source', '')}")
    print("不附带：")
    for item in args.omit:
        print(f"- {item}")
    if not args.send:
        return 0
    card = request(
        "POST",
        "/cards",
        {"recipient": args.to, "type": args.type, "request": args.request, "attachments": attachments},
    )
    print(card["id"])
    return 0


def show_cmd(argv):
    parser = argparse.ArgumentParser(prog="melody show")
    parser.add_argument("card_id")
    args = parser.parse_args(argv)
    card = request("GET", "/cards/" + args.card_id)
    print(card["status"])
    print(card["request"])
    for item in card["attachments"]:
        print(item["content"])
    if card.get("conclusion"):
        print(card["conclusion"])
    for item in card["entries"]:
        if item["entry_type"] == "补充":
            continue
        print(f"{item['author']} {item['entry_type']}")
        print(item["body"])
    return 0


def reply_cmd(argv):
    parser = argparse.ArgumentParser(prog="melody reply")
    parser.add_argument("card_id")
    parser.add_argument("--body", required=True)
    parser.add_argument("--agent", action="store_true")
    args = parser.parse_args(argv)
    mode = "经本人同意的 Agent" if args.agent else "本人"
    card = request("POST", "/cards/" + args.card_id + "/reply", {"body": args.body, "author_mode": mode})
    print(card["status"])
    return 0


def endpoint(argv):
    parser = argparse.ArgumentParser(prog="melody endpoint")
    parser.add_argument("--client", default=None)
    parser.add_argument("--root", default=None)
    args = parser.parse_args(argv)
    payload = {}
    if args.client is not None:
        payload["default_client"] = args.client
    if args.root is not None:
        payload["code_root"] = args.root
    if payload:
        request("POST", "/endpoint", payload)
    return 0


def hook():
    try:
        payload = request("GET", "/hook", timeout=0.8, quiet=True)
    except (Exception, SystemExit):
        return 0
    items = payload.get("items") or []
    if not items:
        return 0
    print(f"melody inbox 有 {len(items)} 张待处理事项卡：")
    for item in items:
        print(f"{item['id']} {item['title']}，来自 {item['sender']}")
    return 0


def request(method, path, payload=None, token=True, timeout=5, quiet=False):
    url = base_url() + path
    data = None if payload is None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + current_token()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw.decode())
    except urllib.error.HTTPError as error:
        body = error.read().decode()
        if not quiet:
            print(body, file=sys.stderr)
        raise SystemExit(1) from error


def base_url():
    return os.environ.get("MELODY_URL") or load_config().get("url") or "http://127.0.0.1:8765"


def current_token():
    return os.environ.get("MELODY_TOKEN") or load_config().get("token") or ""


def config_path():
    return os.environ.get("MELODY_CONFIG") or os.path.join(os.path.expanduser("~"), ".melody", "config.json")


def load_config():
    path = config_path()
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_config(config):
    path = config_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(config, handle)


if __name__ == "__main__":
    raise SystemExit(main())
