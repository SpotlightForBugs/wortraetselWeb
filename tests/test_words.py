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


if __name__ == "__main__":
    unittest.main()
