import unittest

import game


class WordListTests(unittest.TestCase):
    def test_supported_languages_fit_an_alphabet_board(self):
        self.assertEqual(
            game.getLanguages(),
            ["en", "es", "it", "de", "fr", "pt-br", "ro", "tr"],
        )
        self.assertNotIn("zh", game.getLanguages())
        self.assertNotIn("fi", game.getLanguages())

    def test_every_language_comes_from_its_local_list(self):
        for language in game.getLanguages():
            word = game.getRandomWord(language)
            self.assertIn(word, game._local_words(language))
            self.assertGreaterEqual(len(word), 3)
            self.assertTrue(word.isascii())
            self.assertTrue(word.isalpha())

    def test_unsupported_language_uses_english(self):
        self.assertEqual(game.coerce_language("zh"), "en")
        self.assertEqual(game.coerce_language("fi"), "en")
        word = game.getRandomWord("zh")
        self.assertIn(word, game._local_words("en"))

    def test_word_picker_does_not_call_the_network(self):
        self.assertFalse(hasattr(game, "requests"))

    def test_phrases_and_quoted_strings_are_dropped(self):
        for sample in (
            "Das ist ein Traum",
            '"Das ist ein Traum"',
            "In den Warenkorb",
            "Ich weiß nicht.",
            "Luft- und Raumfahrt",
        ):
            self.assertIsNone(game.normalize_word(sample))

    def test_german_list_is_the_local_duden_copy(self):
        words = game._local_words("de")
        self.assertIn("aachen", words)
        self.assertIn("aalraeucherei", words)
        self.assertNotIn("dasisteintraum", words)
        joined = "\n".join(words)
        self.assertNotIn(" ", joined)
        self.assertNotIn('"', joined)

    def test_german_reveal_keeps_umlauts_and_capitalizes(self):
        words = game._local_words("de")
        self.assertIn("aalraeucherei", words)
        # Lists are lowercase; German nouns still show with a capital letter.
        self.assertEqual(game.display_word("de", "aalraeucherei"), "Aalräucherei")
        self.assertEqual(game.display_word("de", "aaskaefer"), "Aaskäfer")
        self.assertEqual(game.display_word("de", "abaenderung"), "Abänderung")
        self.assertEqual(game.display_word("de", "haus"), "Haus")
        self.assertEqual(game.display_word("en", "house"), "house")

    def test_normalize_folds_german_umlauts_for_play(self):
        self.assertEqual(game.normalize_word("Aalräucherei"), "aalraeucherei")
        self.assertEqual(game.normalize_word("Straße"), "strasse")

    def test_german_board_keeps_digraphs_while_playing(self):
        # Mid-game stays in play form; umlauts only appear on win/lose.
        self.assertEqual(len("aalraeucherei"), 13)
        self.assertEqual(len(game.display_word("de", "aalraeucherei")), 12)
        blank = game.reveal("aalraeucherei", [], "playing", "de")
        self.assertEqual(len(blank), 13)
        self.assertEqual(blank, [""] * 13)

        partial = game.reveal("aalraeucherei", ["a", "l", "r"], "playing", "de")
        self.assertEqual(
            partial, ["a", "a", "l", "r", "a", "", "", "", "", "", "r", "", ""]
        )

        both = game.reveal(
            "aalraeucherei", ["a", "e", "l", "r", "u", "c", "h", "i"], "playing", "de"
        )
        self.assertEqual(
            both, ["a", "a", "l", "r", "a", "e", "u", "c", "h", "e", "r", "e", "i"]
        )
        self.assertEqual(
            game.reveal("mueller", ["m", "u", "e", "l", "r"], "playing", "de"),
            ["m", "u", "e", "l", "l", "e", "r"],
        )

        lost = game.reveal("aalraeucherei", [], "lost", "de")
        self.assertEqual(
            lost, ["a", "a", "l", "r", "ä", "u", "c", "h", "e", "r", "e", "i"]
        )
        won = game.reveal("mueller", ["m", "u", "e", "l", "r"], "won", "de")
        self.assertEqual(won, ["m", "ü", "l", "l", "e", "r"])

    def test_eszett_collapses_only_on_result(self):
        self.assertEqual(game.display_word("de", "strasse"), "Straße")
        self.assertEqual(
            game.reveal("strasse", ["s", "t", "r", "a", "e"], "playing", "de"),
            ["s", "t", "r", "a", "s", "s", "e"],
        )
        self.assertEqual(
            game.reveal("strasse", ["s", "t", "r", "a", "e"], "won", "de"),
            ["s", "t", "r", "a", "ß", "e"],
        )

    def test_literal_ae_is_not_forced_to_umlaut(self):
        # English (and any word whose list form keeps ae) stays two tiles.
        self.assertEqual(
            game.reveal("aerial", ["a", "e"], "playing", "en"),
            ["a", "e", "", "", "a", ""],
        )
        # German "Dauer" keeps u+e; it is not "Däur"/ü.
        self.assertEqual(
            game.reveal("dauer", ["d", "a", "u", "e", "r"], "playing", "de"),
            ["d", "a", "u", "e", "r"],
        )


if __name__ == "__main__":
    unittest.main()
