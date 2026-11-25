import unittest
from unittest import mock

import wiktionary


class WiktionaryTests(unittest.TestCase):
    def test_define_uses_firestore_cache_hit(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss",
            return_value={"definition": "house, building"},
        ) as get_cache, mock.patch("wiktionary._fetch_en") as fetch:
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
        ), mock.patch("wiktionary._fetch_en", return_value=payload), mock.patch(
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
        ), mock.patch("wiktionary._fetch_en", return_value=None), mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ) as set_cache:
            self.assertIsNone(wiktionary.define("xyzzyqq", "en"))
        set_cache.assert_called_once()
        self.assertIsNone(set_cache.call_args[0][2])

    def test_cached_miss_stays_silent(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss",
            return_value={"definition": None, "missing": True},
        ), mock.patch("wiktionary._fetch_en") as fetch:
            self.assertIsNone(wiktionary.define("xyzzyqq", "en"))
        fetch.assert_not_called()

    def test_english_titles_stay_lowercase(self):
        self.assertEqual(wiktionary._titles("labrum", "en"), ["labrum"])
        self.assertEqual(wiktionary._titles("Labrum", "en"), ["labrum", "Labrum"])

    def test_german_titles_prefer_capitalized(self):
        self.assertEqual(wiktionary._titles("hocksitz", "de"), ["Hocksitz", "hocksitz"])

    def test_warm_fills_cache_quietly(self):
        with mock.patch("wiktionary.define") as define:
            wiktionary.warm("haus", "de")
        define.assert_called_once_with("haus", "de")

    def test_warm_swallows_lookup_errors(self):
        with mock.patch("wiktionary.define", side_effect=RuntimeError("offline")):
            wiktionary.warm("haus", "de")

    def test_english_lookup_skips_surname_page(self):
        surname = {
            "en": [
                {
                    "partOfSpeech": "Proper noun",
                    "definitions": [{"definition": "A <a>surname</a>."}],
                }
            ]
        }
        noun = {
            "en": [
                {
                    "partOfSpeech": "Noun",
                    "definitions": [{"definition": "The uppermost of the mouthparts."}],
                }
            ]
        }

        def fake_fetch(term):
            return surname if term == "Labrum" else noun if term == "labrum" else None

        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch("wiktionary._fetch_en", side_effect=fake_fetch), mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ):
            self.assertEqual(
                wiktionary.define("labrum", "en"),
                "The uppermost of the mouthparts.",
            )

    def test_german_falls_back_to_de_wiktionary(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch("wiktionary._fetch_en", return_value=None), mock.patch(
            "wiktionary._de_wiktionary_gloss",
            side_effect=lambda term: (
                "weibliche Person, die sich mit Melken beschäftigt"
                if term == "Melkerin"
                else None
            ),
        ) as de_wiki, mock.patch(
            "wiktionary._dwds_gloss"
        ) as dwds, mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ) as set_cache:
            gloss = "weibliche Person, die sich mit Melken beschäftigt"
            self.assertEqual(wiktionary.define("melkerin", "de"), gloss)
        de_wiki.assert_called()
        dwds.assert_not_called()
        self.assertEqual(set_cache.call_args[0][2], gloss)

    def test_german_falls_back_to_dwds_after_wiktionary_miss(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch("wiktionary._fetch_en", return_value=None), mock.patch(
            "wiktionary._de_wiktionary_gloss", return_value=None
        ), mock.patch(
            "wiktionary._dwds_gloss",
            side_effect=lambda term: (
                "Sitz in geschlossener Kniebeuge" if term == "Hocksitz" else None
            ),
        ), mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ) as set_cache:
            self.assertEqual(
                wiktionary.define("hocksitz", "de"),
                "Sitz in geschlossener Kniebeuge",
            )
        self.assertEqual(set_cache.call_args[0][2], "Sitz in geschlossener Kniebeuge")

    def test_de_wiktionary_parses_bedeutungen(self):
        payload = {
            "parse": {
                "wikitext": {
                    "*": (
                        "== Melkerin ({{Sprache|Deutsch}}) ==\n"
                        "{{Bedeutungen}}\n"
                        ":[1] weibliche Person, die sich (beruflich) "
                        "mit [[melken|Melken]] beschäftigt\n"
                        "{{Synonyme}}\n"
                        ":[1] [[Milchmädchen]]\n"
                    )
                }
            }
        }
        with mock.patch("wiktionary._request_json", return_value=payload):
            self.assertEqual(
                wiktionary._de_wiktionary_gloss("Melkerin"),
                "weibliche Person, die sich (beruflich) mit Melken beschäftigt",
            )

    def test_dwds_parses_definition_span(self):
        page = (
            '<span class="dwdswb-definitionen">'
            '<span class="dwdswb-definition">'
            "Sitz in geschlossener Kniebeuge"
            "</span></span>"
        )
        with mock.patch("wiktionary._request_text", return_value=page):
            self.assertEqual(
                wiktionary._dwds_gloss("Hocksitz"),
                "Sitz in geschlossener Kniebeuge",
            )


if __name__ == "__main__":
    unittest.main()
