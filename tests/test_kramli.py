import unittest

import i18n


class KramliLanguageTests(unittest.TestCase):
    def test_supported_overlap_with_hangman(self):
        self.assertTrue(i18n.kramli_supported("en"))
        self.assertTrue(i18n.kramli_supported("de"))
        self.assertTrue(i18n.kramli_supported("pt-br"))
        self.assertFalse(i18n.kramli_supported("ro"))

    def test_site_lang_maps_portuguese(self):
        self.assertEqual(i18n.kramli_site_lang("pt-br"), "pt")
        self.assertEqual(i18n.kramli_site_lang("de"), "de")

    def test_copy_keys_exist_for_every_language(self):
        keys = {
            "kramli_tagline",
            "kramli_blurb",
            "kramli_cta",
            "kramli_dismiss",
            "account_profile",
            "account_security",
            "auth_login_lead",
        }
        for language in i18n._STRINGS:
            catalog = i18n.catalog(language)
            for key in keys:
                self.assertIn(key, catalog, msg=f"{language}.{key}")


if __name__ == "__main__":
    unittest.main()
