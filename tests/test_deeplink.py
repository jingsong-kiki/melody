import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from melody.deeplink import build


class DeeplinkTest(unittest.TestCase):
    def test_cursor_names_the_repo_and_does_not_set_a_directory(self):
        url = unquote(build("cursor", "W-1", "order-service", "/tmp/does-not-matter"))
        self.assertTrue(url.startswith("cursor://anysphere.cursor-deeplink/prompt?text="))
        self.assertIn("处理 melody 事项卡 W-1", url)
        self.assertIn("仓库 order-service", url)
        self.assertNotIn("cwd=", url)
        self.assertNotIn("补退款", url)

    def test_codex_sets_path_only_when_the_local_repo_exists(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "order-service").mkdir()
            found = unquote(build("codex", "W-1", "order-service", root))
            missing = unquote(build("codex", "W-1", "order-service", str(Path(root) / "missing")))
        self.assertIn("codex://new?prompt=", found)
        self.assertIn("path=", found)
        self.assertNotIn("path=", missing)
        self.assertIn("处理 melody 事项卡 W-1", missing)
