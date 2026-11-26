import unittest
from unittest.mock import MagicMock, patch

import firebase_admin

# firebaseDB talks to Firestore; keep import side-effects out of unit tests.
with patch.dict(firebase_admin._apps, {"[DEFAULT]": object()}):
    import firebaseDB


class NormalizeResultPrefsTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(
            firebaseDB.normalize_result_prefs(),
            {"autoskip": True, "seconds": 10, "score_anim": True},
        )
        self.assertEqual(
            firebaseDB.normalize_result_prefs(None),
            {"autoskip": True, "seconds": 10, "score_anim": True},
        )

    def test_clamps_unsupported_seconds(self):
        self.assertEqual(
            firebaseDB.normalize_result_prefs({"autoskip": False, "seconds": 7}),
            {"autoskip": False, "seconds": 10, "score_anim": True},
        )
        self.assertEqual(
            firebaseDB.normalize_result_prefs({"seconds": "30"}),
            {"autoskip": True, "seconds": 30, "score_anim": True},
        )
        self.assertEqual(
            firebaseDB.normalize_result_prefs({"seconds": 0}),
            {"autoskip": True, "seconds": 0, "score_anim": True},
        )

    def test_accepts_firestore_field_names(self):
        self.assertEqual(
            firebaseDB.normalize_result_prefs(
                {
                    "result_autoskip": False,
                    "result_autoskip_sec": 15,
                    "result_score_anim": False,
                }
            ),
            {"autoskip": False, "seconds": 15, "score_anim": False},
        )

    def test_score_anim_coerces_strings(self):
        self.assertFalse(
            firebaseDB.normalize_result_prefs({"score_anim": "false"})["score_anim"]
        )
        self.assertTrue(
            firebaseDB.normalize_result_prefs({"score_anim": "on"})["score_anim"]
        )


class ResultPrefsPersistenceTests(unittest.TestCase):
    def test_get_result_prefs_reads_user_flags(self):
        with patch.object(
            firebaseDB,
            "_user_flags",
            return_value={
                "result_autoskip": False,
                "result_autoskip_sec": 20,
                "result_score_anim": False,
            },
        ):
            self.assertEqual(
                firebaseDB.get_result_prefs("a@example.com"),
                {"autoskip": False, "seconds": 20, "score_anim": False},
            )

    def test_get_result_prefs_defaults_when_missing(self):
        with patch.object(firebaseDB, "_user_flags", return_value={}):
            self.assertEqual(
                firebaseDB.get_result_prefs("a@example.com"),
                {"autoskip": True, "seconds": 10, "score_anim": True},
            )

    def test_set_result_prefs_writes_clamped_values(self):
        document = MagicMock()
        with patch.object(
            firebaseDB, "getDocumentFor", return_value=document
        ), patch.object(
            firebaseDB,
            "get_result_prefs",
            return_value={"autoskip": True, "seconds": 10, "score_anim": True},
        ):
            ok = firebaseDB.set_result_prefs("a@example.com", False, 12, False)
            self.assertTrue(ok)
            document.update.assert_called_once_with(
                {
                    "result_autoskip": False,
                    "result_autoskip_sec": 10,
                    "result_score_anim": False,
                }
            )


if __name__ == "__main__":
    unittest.main()
