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

    def run_cli(self, args, token, url=None):
        env = os.environ.copy()
        env["MELODY_URL"] = url or self.url
        env["MELODY_TOKEN"] = token
        env["MELODY_CONFIG"] = str(Path(self.dir.name) / "config.json")
        return subprocess.run([sys.executable, "-m", "melody", *args], cwd=ROOT, env=env, text=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
