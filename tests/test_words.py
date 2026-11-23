import unittest
from unittest.mock import patch

import requests

import game


class WordListTests(unittest.TestCase):
    def test_english_word_comes_from_the_local_list(self):
        with patch("game.requests.get") as get:
            word = game.getRandomWord("en")
        get.assert_not_called()
        self.assertIn(word, game._local_words("en"))
        self.assertTrue(word.isalpha())
        self.assertGreaterEqual(len(word), 3)

    def test_finnish_falls_back_when_the_list_cannot_be_fetched(self):
        game._WORD_LISTS.pop(
            "https://raw.githubusercontent.com/hugovk/everyfinnishword/master/kaikkisanat.txt",
            None,
        )
        with patch("game.requests.get", side_effect=requests.RequestException("down")):
            word = game.getRandomWord("fi")
        self.assertIn(word, {"kissa", "talo", "omena", "metsa", "koulu"})

    def test_non_json_english_payload_cannot_crash_a_new_game(self):
        class BrokenResponse:
            def json(self):
                raise requests.exceptions.JSONDecodeError("Expecting value", "", 0)

            def raise_for_status(self):
                return None

            text = "Payment required"

        with patch("game.requests.get", return_value=BrokenResponse()):
            word = game.getRandomWord("en")
        self.assertTrue(word.isalpha())


if __name__ == "__main__":
    unittest.main()
