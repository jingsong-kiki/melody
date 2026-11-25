import json
import sys
import tempfile
import unittest
from html import unescape
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import call, start, stop


class InboxTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        self.httpd, self.url = start(str(self.root / "melody.sqlite"))
        self.a = json.loads(call(self.url, "POST", "/persons", payload={"name": "A"})[1])["token"]
        self.b = json.loads(call(self.url, "POST", "/persons", payload={"name": "B"})[1])["token"]
        repo = self.root / "order-service"
        repo.mkdir()
        call(self.url, "POST", "/endpoint", token=self.b, payload={"default_client": "claude", "code_root": str(self.root)})
        created = json.loads(
            call(
                self.url,
                "POST",
                "/cards",
                token=self.a,
                payload={
                    "recipient": "B",
                    "type": "执行",
                    "request": "补退款状态接口",
                    "attachments": [{"source": "refund.py", "content": "VISIBLE_FIELD", "repo": "order-service"}],
                },
            )[1]
        )
        self.card_id = created["id"]

    def tearDown(self):
        stop(self.httpd)
        self.dir.cleanup()

    def test_page_shows_lists_request_and_attachment_without_a_create_form(self):
        page = self.page("/")
        for heading in ("待我处理", "我发出的", "已完成"):
            self.assertIn(heading, page)
        self.assertIn(self.card_id, page)
        self.assertIn("补退款状态接口", page)
        self.assertIn("VISIBLE_FIELD", page)
        self.assertNotIn("新建", page)

    def test_link_contains_the_card_id_and_not_the_request(self):
        page = unescape(self.page("/?card=" + self.card_id))
        self.assertIn("交给我的 Agent 处理", page)
        href = page[page.index("claude-cli://"):].split('"', 1)[0]
        decoded = unquote(href)
        self.assertIn("处理 melody 事项卡 " + self.card_id, decoded)
        self.assertNotIn("补退款状态接口", decoded)
        self.assertNotIn("VISIBLE_FIELD", decoded)
        self.assertIn("cwd=", decoded)
        self.assertIn("order-service", decoded)

    def page(self, path):
        status, body, _headers = self.open_with_cookie(path)
        self.assertEqual(status, 200, body)
        return body.decode()

    def open_with_cookie(self, path):
        import urllib.request

        class RedirectStop(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(RedirectStop)
        request = urllib.request.Request(self.url + "/session", data=("token=" + self.b).encode(), method="POST")
        try:
            opener.open(request, timeout=5)
        except urllib.error.HTTPError as error:
            cookie = error.headers.get("Set-Cookie", "").split(";", 1)[0]
        request = urllib.request.Request(self.url + path, headers={"Cookie": cookie})
        with opener.open(request, timeout=5) as response:
            return response.status, response.read(), dict(response.headers)


import urllib.error  # noqa: E402
