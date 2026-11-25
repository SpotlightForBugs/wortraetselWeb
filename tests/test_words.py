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


if __name__ == "__main__":
    unittest.main()
