import unittest

import game


class DrawingThemeTests(unittest.TestCase):
    def test_drawing_urls_use_the_drawing_route(self):
        self.assertEqual(game.drawing_for(0, "playing"), "/drawing/base.svg")
        self.assertEqual(game.drawing_for(9, "lost"), "/drawing/killed.svg")
        self.assertEqual(game.drawing_for(1, "won"), "/drawing/won.svg")
        self.assertEqual(
            game.drawing_for(0, "playing", dark=True),
            "/drawing/base.svg?theme=dark",
        )

    def test_dark_theme_retints_ink_without_inverting_red(self):
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg">'
            '<style type="text/css">'
            ".st2{fill:#fc0000}"
            ".st3{fill:none;stroke:#000;stroke-width:6}"
            "</style>"
            '<path d="M0 0h1v1z"/>'
            '<path class="st2" d="M0 0h1v1z"/>'
            "</svg>"
        )
        themed = game.theme_hangman_svg(svg, dark=True)
        self.assertIn(f"path{{fill:{game._DARK_INK}}}", themed)
        self.assertIn(f"stroke:{game._DARK_INK}", themed)
        self.assertIn(f"fill:{game._DARK_ACCENT}", themed)
        self.assertNotIn("stroke:#000", themed)
        self.assertNotIn("fill:#fc0000", themed)
        self.assertEqual(game.theme_hangman_svg(svg, dark=False), svg)

    def test_asset_whitelist_rejects_unknown_names(self):
        self.assertIsNone(game.hangman_svg_path("../etc/passwd"))
        self.assertIsNone(game.hangman_svg_path("missing"))
        path = game.hangman_svg_path("base")
        self.assertTrue(path.is_file())


if __name__ == "__main__":
    unittest.main()
