import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import call, start, stop

ROOT = Path(__file__).resolve().parents[1]


class EndToEndTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.httpd, self.url = start(str(Path(self.dir.name) / "melody.sqlite"))
        self.a = json.loads(call(self.url, "POST", "/persons", payload={"name": "A"})[1])["token"]
        self.b = json.loads(call(self.url, "POST", "/persons", payload={"name": "B"})[1])["token"]

    def tearDown(self):
        stop(self.httpd)
        self.dir.cleanup()

    def test_execution_card_and_question_card_close_without_a_native_client(self):
        created = self.cli(
            ["ask", "--to", "B", "--type", "执行", "--request", "补退款状态接口", "--attach-json", json.dumps({"source": "refund.py", "content": "VISIBLE_FIELD", "repo": "order-service"}), "--omit", "密钥", "--send"],
            self.a,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        card_id = created.stdout.strip().splitlines()[-1]
        self.assertTrue(card_id.startswith("W-"))

        listed = json.loads(call(self.url, "GET", "/cards?view=待我处理", token=self.b)[1])["cards"]
        self.assertEqual(listed[0]["status"], "待处理")
        self.assertIn("VISIBLE_FIELD", self.inbox_page())

        reminded = self.cli(["inbox", "--hook"], self.b)
        self.assertIn(card_id, reminded.stdout)
        self.assertNotIn("VISIBLE_FIELD", reminded.stdout)
        self.assertEqual(json.loads(call(self.url, "GET", "/cards/" + card_id, token=self.a)[1])["status"], "待处理")

        shown = self.cli(["show", card_id], self.b)
        self.assertIn("已读", shown.stdout)
        self.assertIn("VISIBLE_FIELD", shown.stdout)
        replied = self.cli(["reply", card_id, "--body", "加上 partial 字段"], self.b)
        self.assertIn("已回复", replied.stdout)
        seen = self.cli(["show", card_id], self.a)
        self.assertIn("加上 partial 字段", seen.stdout)

        closed = json.loads(call(self.url, "POST", "/cards/" + card_id + "/close", token=self.a, payload={})[1])
        self.assertEqual(closed["status"], "已关闭")
        self.assertEqual(closed["conclusion"], "加上 partial 字段")
        denied, body, _headers = call(self.url, "POST", "/cards/" + card_id + "/close", token=self.b, payload={})
        self.assertEqual(denied, 403)
        self.assertNotIn(b"VISIBLE_FIELD", body)

        question = json.loads(call(self.url, "POST", "/cards", token=self.a, payload={"recipient": "B", "type": "问题", "request": "能空吗"})[1])
        form = urlencode({"body": "可以空"})
        status, _body, _headers = call(self.url, "POST", "/cards/" + question["id"] + "/reply", token=self.b, form=form)
        self.assertEqual(status, 303)
        closed_question = json.loads(call(self.url, "POST", "/cards/" + question["id"] + "/close", token=self.a, payload={})[1])
        self.assertEqual(closed_question["status"], "已关闭")
        self.assertEqual(closed_question["work_branch"], "")
        self.assertEqual(closed_question["conclusion"], "可以空")

        status, body, _headers = call(self.url, "GET", "/cards/" + card_id, token="nope")
        self.assertEqual(status, 401)
        self.assertEqual(body, b"")

    def inbox_page(self):
        import urllib.request

        class RedirectStop(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(RedirectStop)
        request = urllib.request.Request(self.url + "/session", data=("token=" + self.b).encode(), method="POST")
        try:
            opener.open(request, timeout=5)
            cookie = ""
        except urllib.error.HTTPError as error:
            cookie = error.headers.get("Set-Cookie", "").split(";", 1)[0]
        with opener.open(urllib.request.Request(self.url + "/", headers={"Cookie": cookie}), timeout=5) as response:
            return response.read().decode()

    def cli(self, args, token):
        env = os.environ.copy()
        env["MELODY_URL"] = self.url
        env["MELODY_TOKEN"] = token
        env["MELODY_CONFIG"] = str(Path(self.dir.name) / "config.json")
        return subprocess.run([sys.executable, "-m", "melody", *args], cwd=ROOT, env=env, text=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
