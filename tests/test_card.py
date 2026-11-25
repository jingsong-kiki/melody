import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from melody.card import CardError, add_person, close_card, create_card, follow_up, hook_list, list_cards, reply, show
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

    def test_question_card_has_empty_work_branch(self):
        created = create_card(self.path, self.a, "B", "问题", "能空吗", [])
        self.assertEqual(created["work_branch"], "")
        self.assertTrue(created["id"].startswith("Q-"))

    def test_list_fifty_pending_cards_within_budget(self):
        for index in range(50):
            create_card(self.path, self.a, "B", "问题", f"问题 {index}", [])
        started = time.perf_counter()
        rows = list_cards(self.path, self.b, "待我处理")
        elapsed = time.perf_counter() - started
        self.assertEqual(len(rows), 50)
        self.assertLess(elapsed, 0.1)


if __name__ == "__main__":
    unittest.main()
