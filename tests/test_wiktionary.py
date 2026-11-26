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
            "wiktionary._native_lookup",
            return_value=("house, building", "Wiktionary", "Haus"),
        ), mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ) as set_cache:
            self.assertEqual(wiktionary.define("Haus", "de"), "house, building")
        set_cache.assert_called_once()
        args = set_cache.call_args[0]
        self.assertEqual(args[0], "de")
        self.assertEqual(args[1], "haus")
        self.assertEqual(args[2], "house, building")
        self.assertEqual(set_cache.call_args[1].get("source"), "Wiktionary")
        self.assertEqual(
            set_cache.call_args[1].get("source_url"),
            "https://de.wiktionary.org/wiki/Haus",
        )

    def test_define_caches_misses(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch(
            "wiktionary._en_rest_gloss", return_value=(None, None)
        ), mock.patch(
            "wiktionary._native_lookup", return_value=(None, None, None)
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
        with mock.patch("wiktionary.define_entry") as define_entry:
            wiktionary.warm("haus", "de")
        define_entry.assert_called_once_with("haus", "de")

    def test_warm_swallows_lookup_errors(self):
        with mock.patch("wiktionary.define_entry", side_effect=RuntimeError("offline")):
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
            "wiktionary._native_lookup", return_value=(None, None, None)
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
            return_value=(
                "Grammatik: Synonym zu Akkusativ, 4. Fall",
                "Wiktionary",
                "Wenfall",
            ),
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

    def _dex_page(self, rows):
        """Minimal Dexonline synthesis HTML (vxern meaning-row shape)."""
        parts = []
        for text, source in rows:
            parts.append(
                '<div class="meaning-row">'
                '<div class="meaningContainer">'
                f'<span class="tree-def html">{text}</span>'
                f'<span class="meaning-sources tag-group">{source}</span>'
                "</div></div>"
                '<div class="meaning-relations"></div>'
            )
        return "".join(parts)

    def test_dexonline_scrapes_html_definition(self):
        page = self._dex_page([("Clădire care servește drept locuință.", "DEX '09")])
        with mock.patch("wiktionary._request_text", return_value=page):
            self.assertEqual(
                wiktionary._dexonline_gloss("casă"),
                "Clădire care servește drept locuință",
            )

    def test_dexonline_skips_examples_and_etymology(self):
        page = self._dex_page(
            [
                (
                    "Viteazul voievod ni s-a închinat... CARAGIALE, O. III 92.",
                    "DLRLC",
                ),
                ("Agro- + terasă", "DEX '09"),
                (
                    "Formă de relief cu aspect de treaptă.",
                    "DEX '09",
                ),
            ]
        )
        with mock.patch("wiktionary._request_text", return_value=page):
            self.assertEqual(
                wiktionary._dexonline_gloss("agroterasa"),
                "Formă de relief cu aspect de treaptă",
            )

    def test_dexonline_prefers_non_copyrighted_source(self):
        page = self._dex_page(
            [
                ("Definiție din MDA2 care ar trebui să piardă.", "MDA2"),
                ("Acțiunea de a aplica și rezultatul ei.", "DEX '09"),
            ]
        )
        with mock.patch("wiktionary._request_text", return_value=page):
            self.assertEqual(
                wiktionary._dexonline_gloss("aplicarile"),
                "Acțiunea de a aplica și rezultatul ei",
            )

    def test_dexonline_falls_back_to_copyrighted_when_needed(self):
        page = self._dex_page([("Prezența bacililor în urină.", "DN")])
        with mock.patch("wiktionary._request_text", return_value=page):
            self.assertEqual(
                wiktionary._dexonline_gloss("bacilurie"),
                "Prezența bacililor în urină",
            )

    def test_define_entry_includes_source(self):
        with mock.patch(
            "wiktionary.firebaseDB.get_word_gloss", return_value=None
        ), mock.patch(
            "wiktionary._native_lookup",
            return_value=("house", "Dexonline", "casă"),
        ), mock.patch(
            "wiktionary.firebaseDB.set_word_gloss"
        ) as set_cache:
            entry = wiktionary.define_entry("casa", "ro")
        self.assertEqual(
            entry,
            {
                "definition": "house",
                "source": "Dexonline",
                "source_url": "https://dexonline.ro/definitie/cas%C4%83",
            },
        )
        self.assertEqual(set_cache.call_args[0][:3], ("ro", "casa", "house"))
        self.assertEqual(set_cache.call_args[1].get("source"), "Dexonline")
        self.assertEqual(
            set_cache.call_args[1].get("source_url"),
            "https://dexonline.ro/definitie/cas%C4%83",
        )

    def test_source_url_for_wiktionary_and_locals(self):
        self.assertEqual(
            wiktionary._source_url("Wiktionary", "de", "Hocksitz"),
            "https://de.wiktionary.org/wiki/Hocksitz",
        )
        self.assertEqual(
            wiktionary._source_url("DWDS", "de", "Hocksitz"),
            "https://www.dwds.de/wb/Hocksitz",
        )
        self.assertEqual(
            wiktionary._source_url("RAE", "es", "casa"),
            "https://dle.rae.es/casa",
        )
        self.assertEqual(
            wiktionary._source_url("TDK", "tr", "ev"),
            "https://sozluk.gov.tr/?ara=ev",
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
