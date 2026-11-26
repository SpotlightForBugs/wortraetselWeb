"""Sanity checks for the hangman stage wipe / crossfade helper."""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "hangman-stage.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
LAYOUT = (ROOT / "templates" / "scripts.html").read_text(encoding="utf-8")


class HangmanStageAssetTests(unittest.TestCase):
    def test_helper_exposes_set_drawing(self):
        self.assertIn("HangmanStage", JS)
        self.assertIn("setDrawing", JS)
        self.assertIn("prefers-reduced-motion", JS)
        self.assertIn("wipeInFresh", JS)
        self.assertIn("isAdditive", JS)
        self.assertIn("hangman-ink-overlay", JS)
        self.assertNotIn("strokeDashoffset", JS)

    def test_overlay_styles_exist(self):
        self.assertIn(".hangman-stage-svg", CSS)
        self.assertIn("hangman-ink-overlay", CSS)
        self.assertIn("has-inline-hangman", CSS)
        self.assertIn("hangman-fade-in", CSS)

    def test_layout_loads_helper(self):
        self.assertIn("hangman-stage.js", LAYOUT)

    def test_miss_frames_are_path_additive(self):
        """Wipe-in relies on later miss frames containing earlier paths."""
        import re

        def path_ds(name):
            text = (ROOT / "static" / "assets" / name).read_text(encoding="utf-8")
            return set(re.findall(r'\bd="([^"]+)"', text))

        sequence = [
            "base.svg",
            "Hangman1_01_Zeichenflache_1.svg",
            "Hangman2_01_Zeichenflache_1.svg",
            "Hangman3_01_Zeichenflache_1.svg",
            "Hangman4_01_Zeichenflache_1.svg",
            "Hangman5_01_Zeichenflache_1.svg",
            "Hangman6_01_Zeichenflache_1.svg",
            "Hangman7_01_Zeichenflache_1.svg",
            "Hangman8_01_Zeichenflache_1.svg",
        ]
        prev = path_ds(sequence[0])
        for name in sequence[1:]:
            cur = path_ds(name)
            self.assertTrue(prev <= cur, msg=f"{name} should keep prior paths")
            prev = cur


if __name__ == "__main__":
    unittest.main()
