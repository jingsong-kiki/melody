import json
import re
import sys
import tempfile
import unittest
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.support import call, login, page_section, reply_action, start, stop


class InboxTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        self.httpd, self.url = start(str(self.root / "melody.sqlite"))
        self.a = json.loads(call(self.url, "POST", "/persons", payload={"name": "A"})[1])["token"]
        self.b = json.loads(call(self.url, "POST", "/persons", payload={"name": "B"})[1])["token"]
        (self.root / "order-service").mkdir()
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
        self.cookie = login(self.url, self.b)

    def tearDown(self):
        stop(self.httpd)
        self.dir.cleanup()

    def test_pending_section_holds_the_card_and_the_page_has_no_create_form(self):
        page = self.page("/")
        pending = page_section(page, "待我处理")
        self.assertIn(self.card_id, pending)
        self.assertIn("补退款状态接口", pending)
        self.assertIn("VISIBLE_FIELD", pending)
        self.assertNotIn(self.card_id, page_section(page, "我发出的"))
        self.assertNotIn(self.card_id, page_section(page, "已完成"))
        self.assertNotIn("新建", page)

    def test_unread_clears_on_open_and_returns_after_the_initiator_follows_up(self):
        self.page("/")
        pending = page_section(self.page("/"), "待我处理")
        self.assertIn(self.card_id, pending)
        self.assertIn("未读", pending)

        opened = self.page("/?card=" + self.card_id)
        self.assertNotIn("未读", page_section(opened, "待我处理"))
        self.assertIn("往来", opened)
        self.assertIn("补退款状态接口", opened.split("往来", 1)[1])

        status, _body, _headers = call(self.url, "POST", reply_action(opened), cookie=self.cookie, form=urlencode({"body": "服务端写"}))
        self.assertEqual(status, 303)

        initiator = login(self.url, self.a)
        detail = self.page("/?card=" + self.card_id, initiator)
        self.assertIn("服务端写", detail.split("往来", 1)[1])
        action = re.search(r'action="([^"]*/follow-up)"', detail).group(1)

        status, _body, _headers = call(self.url, "POST", action, cookie=initiator, form=urlencode({"body": "空值呢"}))
        self.assertEqual(status, 303)

        self.assertIn("未读", page_section(self.page("/"), "待我处理"))
        reopened = self.page("/?card=" + self.card_id)
        self.assertIn("空值呢", reopened.split("往来", 1)[1])
        self.assertNotIn("未读", page_section(reopened, "待我处理"))

    def test_page_link_follows_the_default_client_and_omits_the_request(self):
        claude = self.link_for("claude")
        self.assertTrue(claude.startswith("claude-cli://open?q="))
        self.assertIn("cwd=", claude)
        self.assertIn("order-service", claude)

        codex = self.link_for("codex")
        self.assertTrue(codex.startswith("codex://new?prompt="))
        self.assertIn("path=", codex)
        self.assertIn("order-service", codex)

        cursor = self.link_for("cursor")
        self.assertTrue(cursor.startswith("cursor://anysphere.cursor-deeplink/prompt?text="))
        self.assertIn("仓库 order-service", cursor)
        self.assertNotIn("cwd=", cursor)
        self.assertNotIn("path=", cursor)

    def link_for(self, client):
        call(self.url, "POST", "/endpoint", token=self.b, payload={"default_client": client, "code_root": str(self.root)})
        page = unescape(self.page("/?card=" + self.card_id))
        self.assertIn("交给我的 Agent 处理", page)
        start = max(page.find("claude-cli://"), page.find("codex://"), page.find("cursor://"))
        href = unquote(page[start:].split('"', 1)[0])
        self.assertIn("处理 melody 事项卡 " + self.card_id, href)
        self.assertNotIn("补退款状态接口", href)
        self.assertNotIn("VISIBLE_FIELD", href)
        return href

    def page(self, path, cookie=None):
        status, body, _headers = call(self.url, "GET", path, cookie=cookie or self.cookie)
        self.assertEqual(status, 200, body)
        return body.decode()


if __name__ == "__main__":
    unittest.main()
