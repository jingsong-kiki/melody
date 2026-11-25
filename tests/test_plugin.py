import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PluginTest(unittest.TestCase):
    def test_hook_command_does_not_receive_the_card_body(self):
        for name in ("claude", "codex"):
            config = json.loads((ROOT / "plugins" / name / "hooks.json").read_text())
            commands = []
            for event in config["hooks"].values():
                for group in event:
                    for hook in group["hooks"]:
                        commands.append(hook["command"])
            self.assertEqual(commands, ["melody inbox --hook", "melody inbox --hook"])


if __name__ == "__main__":
    unittest.main()
