"""Sanity checks for the hangman stage crossfade helper."""

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

    def test_overlay_styles_exist(self):
        self.assertIn(".hangman-image-overlay", CSS)
        self.assertIn(".hangman-image-overlay.is-shown", CSS)

    def test_layout_loads_helper(self):
        self.assertIn("hangman-stage.js", LAYOUT)


if __name__ == "__main__":
    unittest.main()
