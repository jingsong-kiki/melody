import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import call, start, stop

ROOT = Path(__file__).resolve().parents[1]


class CliTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.httpd, self.url = start(str(Path(self.dir.name) / "melody.sqlite"))
        self.a = json.loads(call(self.url, "POST", "/persons", payload={"name": "A"})[1])["token"]
        self.b = json.loads(call(self.url, "POST", "/persons", payload={"name": "B"})[1])["token"]

    def tearDown(self):
        stop(self.httpd)
        self.dir.cleanup()

    def test_preview_is_printed_before_the_card_is_written(self):
        result = self.run_cli(
            ["ask", "--to", "B", "--type", "执行", "--request", "补接口", "--attach-json", json.dumps({"source": "a.py", "content": "kept"}), "--omit", "本地密钥", "--send"],
            self.a,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = result.stdout.index("附带：")
        omitted = result.stdout.index("不附带：")
        card_at = result.stdout.index("W-")
        self.assertLess(preview, card_at)
        self.assertLess(omitted, card_at)
        self.assertIn("a.py", result.stdout)
        self.assertIn("本地密钥", result.stdout)

    def test_hook_is_empty_when_nothing_is_pending_or_the_server_is_down(self):
        quiet = self.run_cli(["inbox", "--hook"], self.b)
        self.assertEqual(quiet.returncode, 0)
        self.assertEqual(quiet.stdout, "")
        started = time.perf_counter()
        down = self.run_cli(["inbox", "--hook"], self.b, url="http://127.0.0.1:1")
        elapsed = time.perf_counter() - started
        self.assertEqual(down.returncode, 0)
        self.assertEqual(down.stdout, "")
        self.assertLess(elapsed, 1)

    def test_show_prints_a_follow_up_and_a_conclusion(self):
        card = json.loads(
            call(self.url, "POST", "/cards", token=self.a, payload={"recipient": "B", "type": "问题", "request": "这个字段谁写"})[1]
        )
        call(self.url, "POST", "/cards/" + card["id"] + "/reply", token=self.b, payload={"body": "服务端写"})
        call(self.url, "POST", "/cards/" + card["id"] + "/follow-up", token=self.a, payload={"body": "空值呢"})
        shown = self.run_cli(["show", card["id"]], self.b)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        self.assertIn("追问", shown.stdout)
        self.assertIn("空值呢", shown.stdout)
        self.assertIn("服务端写", shown.stdout)
        call(self.url, "POST", "/cards/" + card["id"] + "/close", token=self.a, payload={"conclusion": "单独的结论"})
        closed = self.run_cli(["show", card["id"]], self.a)
        self.assertIn("单独的结论", closed.stdout)

    def test_hook_stays_quiet_when_the_local_config_cannot_be_read(self):
        config = Path(self.dir.name) / "broken.json"
        config.write_text("{", encoding="utf-8")
        result = self.run_cli(["inbox", "--hook"], token=None, url=None, config=config)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_config_can_be_saved_when_the_path_has_no_directory(self):
        from melody.cli import save_config

        path = Path(self.dir.name) / "bare.json"
        previous = os.getcwd()
        saved = os.environ.get("MELODY_CONFIG")
        os.chdir(self.dir.name)
        try:
            os.environ["MELODY_CONFIG"] = path.name
            save_config({"url": self.url, "token": "t", "name": "A"})
        finally:
            if saved is None:
                os.environ.pop("MELODY_CONFIG", None)
            else:
                os.environ["MELODY_CONFIG"] = saved
            os.chdir(previous)
        self.assertEqual(json.loads(path.read_text())["name"], "A")

    def run_cli(self, args, token, url=None, config=None):
        env = os.environ.copy()
        if url is not None:
            env["MELODY_URL"] = url
        elif url is None and token is not None:
            env["MELODY_URL"] = self.url
        else:
            env.pop("MELODY_URL", None)
        if token:
            env["MELODY_TOKEN"] = token
        else:
            env.pop("MELODY_TOKEN", None)
        env["MELODY_CONFIG"] = str(config or Path(self.dir.name) / "config.json")
        return subprocess.run([sys.executable, "-m", "melody", *args], cwd=ROOT, env=env, text=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
