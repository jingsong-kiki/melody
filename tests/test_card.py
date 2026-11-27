import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from melody.card import CardError, add_person, close_card, create_card, follow_up, hook_list, list_cards, reply, set_endpoint, show
from melody.db import init


class CardTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = str(Path(self.dir.name) / "melody.sqlite")
        init(self.path)
        self.a = add_person(self.path, "A")["token"]
        self.b = add_person(self.path, "B")["token"]

    def tearDown(self):
        self.dir.cleanup()

    def test_execution_card_moves_through_four_states_and_records_conclusion(self):
        created = create_card(
            self.path,
            self.a,
            "B",
            "执行",
            "补退款状态接口",
            [{"source": "refund.py", "content": "status field", "repo": "order-service", "commit": "abc"}],
        )
        self.assertEqual(created["status"], "待处理")
        self.assertEqual(created["work_branch"], "")
        self.assertEqual(created["repo_name"], "order-service")
        self.assertEqual(created["attachments"][0]["content"], "status field")

        seen = show(self.path, self.b, created["id"])
        self.assertEqual(seen["status"], "已读")

        answered = reply(self.path, self.b, created["id"], "加上 partial 字段")
        self.assertEqual(answered["status"], "已回复")

        closed = close_card(self.path, self.a, created["id"])
        self.assertEqual(closed["status"], "已关闭")
        self.assertEqual(closed["conclusion"], "加上 partial 字段")
        again = reply(self.path, self.b, created["id"], "补充一句")
        self.assertEqual(again["status"], "已关闭")
        self.assertTrue(any(item["body"] == "补充一句" for item in again["entries"]))

    def test_recipient_cannot_close_and_hook_list_does_not_change_status(self):
        created = create_card(self.path, self.a, "B", "问题", "是否包含部分退款", [])
        before = show(self.path, self.a, created["id"], mark_read=False)
        self.assertEqual(before["status"], "待处理")
        listed = hook_list(self.path, self.b)
        self.assertEqual(listed, [{"id": created["id"], "title": "是否包含部分退款", "sender": "A"}])
        after = show(self.path, self.a, created["id"], mark_read=False)
        self.assertEqual(after["status"], "待处理")
        with self.assertRaises(CardError) as caught:
            close_card(self.path, self.b, created["id"])
        self.assertEqual(caught.exception.code, "forbidden")
        self.assertEqual(show(self.path, self.a, created["id"], mark_read=False)["status"], "待处理")

    def test_follow_up_returns_a_replied_card_to_read(self):
        created = create_card(self.path, self.a, "B", "问题", "这个字段谁写", [])
        show(self.path, self.b, created["id"])
        reply(self.path, self.b, created["id"], "服务端写")
        asked = follow_up(self.path, self.a, created["id"], "空值呢")
        self.assertEqual(asked["status"], "已读")

    def test_recipient_sees_unread_until_opening_and_again_after_a_follow_up(self):
        created = create_card(self.path, self.a, "B", "问题", "这个字段谁写", [])
        self.assertIs(self.unread(self.b, "待我处理", created["id"]), True)
        self.assertIs(self.unread(self.a, "我发出的", created["id"]), False)

        show(self.path, self.b, created["id"])
        self.assertIs(self.unread(self.b, "待我处理", created["id"]), False)

        reply(self.path, self.b, created["id"], "服务端写")
        self.assertIs(self.unread(self.b, "待我处理", created["id"]), False)

        follow_up(self.path, self.a, created["id"], "空值呢")
        self.assertIs(self.unread(self.b, "待我处理", created["id"]), True)

        show(self.path, self.b, created["id"])
        self.assertIs(self.unread(self.b, "待我处理", created["id"]), False)

    def unread(self, token, view, card_id):
        return next(item["unread"] for item in list_cards(self.path, token, view) if item["id"] == card_id)

    def test_only_listed_attachments_are_stored(self):
        created = create_card(
            self.path,
            self.a,
            "B",
            "执行",
            "改接口",
            [{"source": "a.py", "content": "kept", "repo": "order-service"}],
        )
        self.assertEqual([item["source"] for item in created["attachments"]], ["a.py"])

    def test_hook_drops_a_card_after_reply_and_lists_it_again_after_follow_up(self):
        created = create_card(self.path, self.a, "B", "问题", "这个字段谁写", [])
        show(self.path, self.b, created["id"])
        self.assertEqual([item["id"] for item in hook_list(self.path, self.b)], [created["id"]])
        reply(self.path, self.b, created["id"], "服务端写")
        self.assertEqual(hook_list(self.path, self.b), [])
        follow_up(self.path, self.a, created["id"], "空值呢")
        self.assertEqual([item["id"] for item in hook_list(self.path, self.b)], [created["id"]])

    def test_repo_name_cannot_leave_the_code_root(self):
        with self.assertRaises(CardError) as caught:
            create_card(self.path, self.a, "B", "问题", "看配置", [{"source": "a.py", "content": "x", "repo": "/etc"}])
        self.assertEqual(caught.exception.code, "invalid")
        with self.assertRaises(CardError) as caught:
            create_card(self.path, self.a, "B", "问题", "看配置", [{"source": "a.py", "content": "x", "repo": ".."}])
        self.assertEqual(caught.exception.code, "invalid")

    def test_endpoint_keeps_unset_fields_and_rejects_an_unknown_client(self):
        set_endpoint(self.path, self.b, default_client="claude", code_root="/tmp/keep")
        kept = set_endpoint(self.path, self.b, default_client="Cursor")
        self.assertEqual(kept["default_client"], "cursor")
        self.assertEqual(kept["code_root"], "/tmp/keep")
        with self.assertRaises(CardError) as caught:
            set_endpoint(self.path, self.b, default_client="vim")
        self.assertEqual(caught.exception.code, "invalid")

    def test_question_card_has_empty_work_branch(self):
        created = create_card(self.path, self.a, "B", "问题", "能空吗", [])
        self.assertEqual(created["work_branch"], "")
        self.assertTrue(created["id"].startswith("Q-"))


if __name__ == "__main__":
    unittest.main()
