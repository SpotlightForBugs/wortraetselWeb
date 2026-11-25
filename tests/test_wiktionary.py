import unittest
from unittest import mock

import wiktionary


class WiktionaryTests(unittest.TestCase):
    def test_define_uses_firestore_cache_hit(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss",
            return_value={"definition": "house, building"},
        ) as get_cache, mock.patch("wiktionary._fetch") as fetch:
            self.assertEqual(wiktionary.define("Haus", "de"), "house, building")
        get_cache.assert_called_once()
        fetch.assert_not_called()

    def test_define_caches_api_result(self):
        payload = {
            "de": [
                {
                    "partOfSpeech": "Noun",
                    "definitions": [
                        {"definition": "house, <a href='/wiki/building'>building</a>"}
                    ],
                }
            ]
        }
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch("wiktionary._fetch", return_value=payload), mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ) as set_cache:
            self.assertEqual(wiktionary.define("Haus", "de"), "house, building")
        set_cache.assert_called_once()
        args = set_cache.call_args[0]
        self.assertEqual(args[0], "de")
        self.assertEqual(args[1], "haus")
        self.assertEqual(args[2], "house, building")

    def test_define_caches_misses(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch("wiktionary._fetch", return_value=None), mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ) as set_cache:
            self.assertIsNone(wiktionary.define("xyzzyqq", "en"))
        set_cache.assert_called_once()
        self.assertIsNone(set_cache.call_args[0][2])

    def test_cached_miss_stays_silent(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss",
            return_value={"definition": None, "missing": True},
        ), mock.patch("wiktionary._fetch") as fetch:
            self.assertIsNone(wiktionary.define("xyzzyqq", "en"))
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
