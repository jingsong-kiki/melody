import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import call, start, stop


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.httpd, self.url = start(str(Path(self.dir.name) / "melody.sqlite"))
        self.a = json.loads(call(self.url, "POST", "/persons", payload={"name": "A"})[1])["token"]
        self.b = json.loads(call(self.url, "POST", "/persons", payload={"name": "B"})[1])["token"]

    def tearDown(self):
        stop(self.httpd)
        self.dir.cleanup()

    def test_bad_token_has_empty_body_and_only_listed_attachments_are_kept(self):
        status, body, _headers = call(self.url, "GET", "/cards?view=待我处理", token="nope")
        self.assertEqual(status, 401)
        self.assertEqual(body, b"")
        status, body, _headers = call(
            self.url,
            "POST",
            "/cards",
            token=self.a,
            payload={
                "recipient": "B",
                "type": "执行",
                "request": "补接口",
                "attachments": [{"source": "a.py", "content": "kept", "repo": "order-service"}],
            },
        )
        self.assertEqual(status, 201)
        card = json.loads(body)
        self.assertEqual([item["content"] for item in card["attachments"]], ["kept"])

    def test_hook_list_does_not_change_status_or_return_body(self):
        card = json.loads(
            call(
                self.url,
                "POST",
                "/cards",
                token=self.a,
                payload={"recipient": "B", "type": "问题", "request": "标题行\n这是正文", "attachments": [{"source": "a.py", "content": "SECRET_ATTACH"}]},
            )[1]
        )
        status, body, _headers = call(self.url, "GET", "/hook", token=self.b)
        self.assertEqual(status, 200)
        text = body.decode()
        self.assertIn("标题行", text)
        self.assertNotIn("这是正文", text)
        self.assertNotIn("SECRET_ATTACH", text)
        shown = json.loads(call(self.url, "GET", "/cards/" + card["id"], token=self.a)[1])
        self.assertEqual(shown["status"], "待处理")

    def test_open_stream_receives_the_new_card(self):
        box = {}

        def listen():
            status, body, _headers = call(self.url, "GET", "/events", token=self.b)
            box["status"] = status
            box["body"] = body

        thread = threading.Thread(target=listen)
        thread.start()
        time.sleep(0.2)
        call(
            self.url,
            "POST",
            "/cards",
            token=self.a,
            payload={"recipient": "B", "type": "问题", "request": "新问题"},
        )
        thread.join(timeout=3)
        self.assertEqual(box["status"], 200)
        self.assertIn("新问题", box["body"].decode())

    def test_list_fifty_cards_within_budget(self):
        for index in range(50):
            call(self.url, "POST", "/cards", token=self.a, payload={"recipient": "B", "type": "问题", "request": f"问题 {index}"})
        started = time.perf_counter()
        status, body, _headers = call(self.url, "GET", "/cards?view=待我处理", token=self.b)
        elapsed = time.perf_counter() - started
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["cards"]), 50)
        self.assertLess(elapsed, 0.1)


if __name__ == "__main__":
    unittest.main()
