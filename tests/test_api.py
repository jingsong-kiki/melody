import json
import sys
import tempfile
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
        import http.client
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
        conn.request("GET", "/events", headers={"Authorization": "Bearer " + self.b})
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        call(self.url, "POST", "/cards", token=self.a, payload={"recipient": "B", "type": "问题", "request": "新问题"})
        data = b""
        while b"\n\n" not in data:
            chunk = response.read(1)
            if not chunk:
                break
            data += chunk
        conn.close()
        self.assertIn("新问题", data.decode())

    def test_bad_json_and_a_bodyless_close_stay_on_the_json_path(self):
        import urllib.request

        request = urllib.request.Request(
            self.url + "/cards",
            data=b"not-json",
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.a},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)

        card = json.loads(call(self.url, "POST", "/cards", token=self.a, payload={"recipient": "B", "type": "问题", "request": "能关吗"})[1])
        request = urllib.request.Request(
            self.url + "/cards/" + card["id"] + "/close",
            data=b"",
            headers={"Authorization": "Bearer " + self.a, "Content-Length": "0"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("已关闭", response.read().decode())


if __name__ == "__main__":
    unittest.main()
