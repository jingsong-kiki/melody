import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from melody.card import add_person, create_card, list_cards
from melody.db import init
from tests.support import call, start, stop


class ListBudgetTest(unittest.TestCase):
    def test_module_lists_fifty_pending_cards_within_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "melody.sqlite")
            init(path)
            token_a = add_person(path, "A")["token"]
            token_b = add_person(path, "B")["token"]
            for index in range(50):
                create_card(path, token_a, "B", "问题", f"问题 {index}", [])
            started = time.perf_counter()
            rows = list_cards(path, token_b, "待我处理")
            elapsed = time.perf_counter() - started
        self.assertEqual(len(rows), 50)
        self.assertLess(elapsed, 0.1)

    def test_http_lists_fifty_pending_cards_within_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            httpd, url = start(str(Path(directory) / "melody.sqlite"))
            try:
                token_a = json.loads(call(url, "POST", "/persons", payload={"name": "A"})[1])["token"]
                token_b = json.loads(call(url, "POST", "/persons", payload={"name": "B"})[1])["token"]
                for index in range(50):
                    call(url, "POST", "/cards", token=token_a, payload={"recipient": "B", "type": "问题", "request": f"问题 {index}"})
                started = time.perf_counter()
                status, body, _headers = call(url, "GET", "/cards?view=待我处理", token=token_b)
                elapsed = time.perf_counter() - started
            finally:
                stop(httpd)
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["cards"]), 50)
        self.assertLess(elapsed, 0.1)


if __name__ == "__main__":
    unittest.main()
