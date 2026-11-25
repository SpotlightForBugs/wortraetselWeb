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
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch(
            "wiktionary._native_lookup", return_value="house, building"
        ), mock.patch(
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
        ), mock.patch("wiktionary._en_rest_gloss", return_value=None), mock.patch(
            "wiktionary._native_lookup", return_value=None
        ), mock.patch(
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
            "wiktionary._native_lookup", return_value=None
        ), mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ):
            self.assertEqual(
                wiktionary.define("labrum", "en"),
                "The uppermost of the mouthparts.",
            )

    def test_non_english_never_calls_english_rest(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch(
            "wiktionary._native_lookup",
            return_value="Grammatik: Synonym zu Akkusativ, 4. Fall",
        ), mock.patch(
            "wiktionary._en_rest_gloss"
        ) as en_rest, mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ):
            self.assertEqual(
                wiktionary.define("wenfall", "de"),
                "Grammatik: Synonym zu Akkusativ, 4. Fall",
            )
        en_rest.assert_not_called()

    def test_romanian_prefers_accented_search_hit(self):
        with mock.patch(
            "wiktionary._search_titles", return_value=["casa", "casă"]
        ), mock.patch("wiktionary._titles", return_value=["Casa", "casa"]):
            cands = wiktionary._native_candidates("casa", "ro")
            self.assertEqual(cands[0], "casă")
            self.assertIn("casa", cands)

    def test_local_fallback_after_wiktionary_miss(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch(
            "wiktionary._native_candidates", return_value=["Hocksitz"]
        ), mock.patch(
            "wiktionary._native_wiktionary_gloss", return_value=None
        ), mock.patch(
            "wiktionary._local_gloss",
            side_effect=lambda language, term: (
                "Sitz in geschlossener Kniebeuge"
                if language == "de" and term == "Hocksitz"
                else None
            ),
        ), mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ) as set_cache:
            self.assertEqual(
                wiktionary.define("hocksitz", "de"),
                "Sitz in geschlossener Kniebeuge",
            )
        self.assertEqual(set_cache.call_args[0][2], "Sitz in geschlossener Kniebeuge")

    def test_dexonline_parses_sense(self):
        payload = {
            "definitions": [
                {
                    "internalRep": (
                        "@CASĂ^1,@ $case,$ #s. f.# @1.@ "
                        "Clădire care servește drept locuință. * #Loc.#"
                    )
                }
            ]
        }
        with mock.patch("wiktionary._request_json", return_value=payload):
            self.assertEqual(
                wiktionary._dexonline_gloss("casă"),
                "Clădire care servește drept locuință",
            )

    def test_dexonline_parses_mda2_range_sense(self):
        """MDA2 uses @1-3@ and nested markers; must not return the headword line."""
        payload = {
            "definitions": [
                {
                    "internalRep": (
                        "@$bacilur&#039;ie$@ $#sf#$ "
                        "[#At:# DN^{3} / #Pl:# $~&#039;ii$ / "
                        "#E:# #fr# @$bacillurie$@] @1-3@ "
                        "(Buletin de) analiză cu "
                        "(prezența bacililor în urină)."
                    )
                }
            ]
        }
        with mock.patch("wiktionary._request_json", return_value=payload):
            self.assertEqual(
                wiktionary._dexonline_gloss("baciluria"),
                "(Buletin de) analiză cu (prezența bacililor în urină)",
            )

    def test_dexonline_parses_mda2_numbered_senses(self):
        """MDA2 @1@/@2@ without a period must yield only the first sense."""
        payload = {
            "definitions": [
                {
                    "internalRep": (
                        "@$erg&#039;ot$@ $#sn#$ "
                        "[#At:# DN^4 / #Pl:# $~uri$ / #E:# #fr# @$ergot$@] "
                        "@1@ Formație vegetală parazitară veninoasă "
                        "care apare sub formă de mici puncte pe spicul "
                        "unor graminee. @2@ Boală criptogamică ##a## "
                        "gramineelor."
                    )
                }
            ]
        }
        with mock.patch("wiktionary._request_json", return_value=payload):
            self.assertEqual(
                wiktionary._dexonline_gloss("ergot"),
                (
                    "Formație vegetală parazitară veninoasă care apare "
                    "sub formă de mici puncte pe spicul unor graminee"
                ),
            )

    def test_dexonline_strips_headword_without_sense_number(self):
        """DEX '16 entries like aplicare have lemma+POS then the gloss."""
        payload = {
            "definitions": [
                {
                    "internalRep": (
                        "@APLIC'ARE,@ $aplicări,$ #s.f.#\n"
                        "Acțiunea de $a aplica$ și rezultatul ei.\n"
                        "- #V.# @aplica.@"
                    )
                }
            ]
        }
        with mock.patch("wiktionary._request_json", return_value=payload):
            self.assertEqual(
                wiktionary._dexonline_gloss("aplicarile"),
                "Acțiunea de a aplica și rezultatul ei",
            )

    def test_tdk_parses_sense(self):
        payload = [
            {
                "anlamlarListe": [
                    {"anlam": "► aile"},
                    {"anlam": "Bir kimsenin veya ailenin içinde yaşadığı yer"},
                ]
            }
        ]
        with mock.patch("wiktionary._request_json", return_value=payload):
            self.assertEqual(
                wiktionary._tdk_gloss("ev"),
                "Bir kimsenin veya ailenin içinde yaşadığı yer",
            )

    def test_rae_parses_description(self):
        payload = {
            "data": {
                "meanings": [
                    {"senses": [{"description": "Edificio para habitar", "raw": "1."}]}
                ]
            }
        }
        with mock.patch("wiktionary._request_json", return_value=payload):
            self.assertEqual(wiktionary._rae_gloss("casa"), "Edificio para habitar")

    def test_priberam_parses_meta(self):
        page = (
            '<meta name="description" content="Significado de casa, nome feminino: '
            'Nome genérico de construções destinadas a habitação — Dicionário Priberam">'
        )
        with mock.patch("wiktionary._request_text", return_value=page):
            self.assertEqual(
                wiktionary._priberam_gloss("casa"),
                "Nome genérico de construções destinadas a habitação",
            )

    def test_extract_de_bedeutungen(self):
        body = (
            "== Melkerin ({{Sprache|Deutsch}}) ==\n"
            "{{Bedeutungen}}\n"
            ":[1] weibliche Person, die sich (beruflich) "
            "mit [[melken|Melken]] beschäftigt\n"
            "{{Synonyme}}\n"
            ":[1] [[Milchmädchen]]\n"
        )
        self.assertEqual(
            wiktionary._extract_de(body),
            "weibliche Person, die sich (beruflich) mit Melken beschäftigt",
        )

    def test_extract_es_numbered_senses(self):
        body = (
            "== {{lengua|es}} ==\n"
            ";1 {{csem|vivienda}}: {{plm|edificación}} destinada a [[vivienda]].\n"
            ";2: {{plm|domicilio}}.\n"
        )
        self.assertEqual(
            wiktionary._extract_es(body),
            "edificación destinada a vivienda",
        )

    def test_extract_hash_skips_examples(self):
        body = (
            "=== Nom commun ===\n"
            "# {{édifices|fr}} [[bâtiment|Bâtiment]] servant de [[logis]].\n"
            "#*{{exemple|lang=fr|Les maisons}}\n"
        )
        self.assertEqual(
            wiktionary._extract_hash(body),
            "Bâtiment servant de logis",
        )

    def test_extract_italian_uses_starred_sense(self):
        body = (
            "# {{Pn|w}} ''f sing'' {{Linkp|case}}\n"
            "#* {{Term|architettura|it}} [[edificio]] [[costruito]] per abitazione\n"
        )
        self.assertEqual(
            wiktionary._extract_hash(body),
            "edificio costruito per abitazione",
        )

    def test_skips_weak_and_redirect_gloss(self):
        self.assertFalse(wiktionary._usable("A surname."))
        self.assertFalse(wiktionary._usable("REDIRECT gri"))
        self.assertTrue(wiktionary._usable("The uppermost of the mouthparts."))

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
