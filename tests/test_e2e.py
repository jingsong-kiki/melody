import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import call, login, reply_action, start, stop

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
        self.assertLess(created.stdout.index("附带："), created.stdout.index(card_id))
        self.assertLess(created.stdout.index("不附带："), created.stdout.index(card_id))
        self.assertIn("密钥", created.stdout)
        stored = json.loads(call(self.url, "GET", "/cards/" + card_id, token=self.a)[1])
        self.assertEqual([item["content"] for item in stored["attachments"]], ["VISIBLE_FIELD"])
        self.assertNotIn("密钥", json.dumps(stored, ensure_ascii=False))

        listed = json.loads(call(self.url, "GET", "/cards?view=待我处理", token=self.b)[1])["cards"]
        self.assertEqual(listed[0]["id"], card_id)
        self.assertEqual(listed[0]["status"], "待处理")
        self.assertIn("补退款状态接口", listed[0]["request"])
        self.assertIn("补退款状态接口", self.inbox_page())
        self.assertEqual(stored["status"], "待处理")

        reminded = self.cli(["inbox", "--hook"], self.b)
        self.assertIn("1 张待处理事项卡", reminded.stdout)
        self.assertIn(card_id, reminded.stdout)
        self.assertIn("补退款状态接口", reminded.stdout)
        self.assertIn("来自 A", reminded.stdout)
        self.assertNotIn("VISIBLE_FIELD", reminded.stdout)
        self.assertEqual(json.loads(call(self.url, "GET", "/cards/" + card_id, token=self.a)[1])["status"], "待处理")

        shown = self.cli(["show", card_id], self.b)
        self.assertIn("已读", shown.stdout)
        self.assertIn("VISIBLE_FIELD", shown.stdout)
        replied = self.cli(["reply", card_id, "--body", "加上 partial 字段"], self.b)
        self.assertIn("已回复", replied.stdout)
        seen = self.cli(["show", card_id], self.a)
        self.assertIn("已回复", seen.stdout)
        self.assertIn("加上 partial 字段", seen.stdout)

        closed = json.loads(call(self.url, "POST", "/cards/" + card_id + "/close", token=self.a, payload={})[1])
        self.assertEqual(closed["status"], "已关闭")
        self.assertEqual(closed["conclusion"], "加上 partial 字段")
        denied, body, _headers = call(self.url, "POST", "/cards/" + card_id + "/close", token=self.b, payload={})
        self.assertEqual(denied, 403)
        self.assertNotIn(b"VISIBLE_FIELD", body)
        still = json.loads(call(self.url, "GET", "/cards/" + card_id, token=self.a)[1])
        self.assertEqual(still["status"], "已关闭")
        self.assertEqual(still["conclusion"], "加上 partial 字段")

        question = json.loads(call(self.url, "POST", "/cards", token=self.a, payload={"recipient": "B", "type": "问题", "request": "能空吗"})[1])
        detail = self.inbox_page("/?card=" + question["id"])
        action = reply_action(detail)
        status, _body, _headers = call(self.url, "POST", action, cookie=self.cookie, form=urlencode({"body": "可以空"}))
        self.assertEqual(status, 303)
        closed_question = json.loads(call(self.url, "POST", "/cards/" + question["id"] + "/close", token=self.a, payload={})[1])
        self.assertEqual(closed_question["status"], "已关闭")
        self.assertEqual(closed_question["work_branch"], "")
        self.assertEqual(closed_question["conclusion"], "可以空")

        status, body, _headers = call(self.url, "GET", "/cards/" + card_id, token="nope")
        self.assertEqual(status, 401)
        self.assertEqual(body, b"")

    def inbox_page(self, path="/"):
        if not hasattr(self, "cookie"):
            self.cookie = login(self.url, self.b)
        status, body, _headers = call(self.url, "GET", path, cookie=self.cookie)
        self.assertEqual(status, 200, body)
        return body.decode()

    def cli(self, args, token):
        env = os.environ.copy()
        env["MELODY_URL"] = self.url
        env["MELODY_TOKEN"] = token
        env["MELODY_CONFIG"] = str(Path(self.dir.name) / "config.json")
        return subprocess.run([sys.executable, "-m", "melody", *args], cwd=ROOT, env=env, text=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
