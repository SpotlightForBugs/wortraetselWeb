import unittest

import game
import i18n


class LanguageTests(unittest.TestCase):
    def test_every_language_has_the_same_interface_copy(self):
        keys = set(i18n.catalog("en"))
        self.assertGreater(len(keys), 20)
        for language in game.getLanguages():
            self.assertEqual(set(i18n.catalog(language)), keys)
            for key in keys:
                self.assertTrue(i18n.text(language, key) or key in ("worth", "unsaved_score", "score_line", "win", "loss"))

    def test_browser_header_picks_a_supported_language(self):
        self.assertEqual(i18n.match_accept_language("de-DE,de;q=0.9,en;q=0.8"), "de")
        self.assertEqual(i18n.match_accept_language("es-MX,es;q=0.8,en;q=0.2"), "es")
        self.assertEqual(i18n.match_accept_language("pt-PT,pt;q=0.9,en;q=0.5"), "pt-br")
        self.assertEqual(i18n.match_accept_language("pt-BR"), "pt-br")
        self.assertEqual(i18n.match_accept_language("fr;q=0.1,it;q=0.9"), "it")
        self.assertEqual(i18n.match_accept_language("zh-CN,zh;q=0.9,en;q=0.8"), "en")
        self.assertEqual(i18n.match_accept_language(""), "en")
        self.assertEqual(i18n.match_accept_language(None), "en")

    def test_messages_include_the_word(self):
        state = i18n.client_state(
            "de",
            "haus",
            ["h", "a", "u", "s"],
            1,
            result={"success": True, "word": "haus", "offer": True, "points": 900},
        )
        self.assertEqual(state["status"], "won")
        self.assertIn("Haus", state["result"]["message"])
        self.assertIn("900", state["result"]["worth"])
        self.assertEqual(state["copy"]["log_in"], "Anmelden")
        self.assertEqual(state["html_lang"], "de")
        self.assertEqual(state["tiles"], ["h", "a", "u", "s"])


class GuessTests(unittest.TestCase):
    def test_a_guess_updates_the_same_word(self):
        letters, wrong, status = game.apply_guess("haus", [], 0, "H")
        self.assertEqual(letters, ["h"])
        self.assertEqual(wrong, 0)
        self.assertEqual(status, "playing")
        self.assertEqual(game.reveal("haus", letters, status), ["h", "", "", ""])

        letters, wrong, status = game.apply_guess("haus", letters, wrong, "z")
        self.assertEqual(wrong, 1)
        self.assertEqual(game.letter_states(letters, "haus")["Z"], "miss")
        self.assertEqual(game.letter_states(letters, "haus")["H"], "hit")

        again, wrong_again, status_again = game.apply_guess("haus", letters, wrong, "z")
        self.assertEqual(again, letters)
        self.assertEqual(wrong_again, wrong)
        self.assertEqual(status_again, status)

    def test_the_last_wrong_guess_reveals_the_word(self):
        letters, wrong, status = game.apply_guess("haus", [], 8, "q")
        self.assertEqual(status, "lost")
        self.assertEqual(game.reveal("haus", letters, status), ["h", "a", "u", "s"])
        self.assertTrue(game.drawing_for(wrong, status).endswith("killed.svg"))

    def test_a_solved_word_uses_the_same_tile_count(self):
        letters, wrong, status = game.apply_guess("haus", ["h", "a", "u"], 0, "s")
        self.assertEqual(status, "won")
        self.assertEqual(len(game.reveal("haus", letters, status)), 4)
        self.assertTrue(game.drawing_for(wrong, status).endswith("won.svg"))


if __name__ == "__main__":
    unittest.main()
