import unittest
from unittest.mock import patch

import admin_ops


class AdminOpsTests(unittest.TestCase):
    def test_bootstrap_emails_parse(self):
        with patch.dict("os.environ", {"ADMIN_EMAILS": "a@x.io, B@Y.IO "}):
            self.assertEqual(admin_ops.bootstrap_emails(), {"a@x.io", "b@y.io"})

    def test_is_admin_email_uses_firestore_or_bootstrap(self):
        with patch.object(admin_ops, "bootstrap_emails", return_value={"boss@x.io"}):
            self.assertTrue(admin_ops.is_admin_email("boss@x.io"))
        with patch.object(admin_ops, "bootstrap_emails", return_value=set()), patch.object(
            admin_ops.firebaseDB, "is_admin", return_value=True
        ):
            self.assertTrue(admin_ops.is_admin_email("mods@x.io"))
        with patch.object(admin_ops, "bootstrap_emails", return_value=set()), patch.object(
            admin_ops.firebaseDB, "is_admin", return_value=False
        ):
            self.assertFalse(admin_ops.is_admin_email("player@x.io"))

    def test_set_score_rejects_bad_values(self):
        ok, error = admin_ops.set_score("a@x.io", "-1")
        self.assertFalse(ok)
        self.assertEqual(error, "admin_bad_score")

    def test_set_score_overwrites(self):
        with patch.object(admin_ops.firebaseDB, "setScore", return_value=True) as set_score:
            ok, value = admin_ops.set_score("a@x.io", "42")
            self.assertTrue(ok)
            self.assertEqual(value, 42)
            set_score.assert_called_once_with("a@x.io", 42, overwrite=True)

    def test_delete_user_blocks_self(self):
        ok, error = admin_ops.delete_user("a@x.io", "a@x.io")
        self.assertFalse(ok)
        self.assertEqual(error, "admin_self")

    def test_announcement_length_limit(self):
        ok, error = admin_ops.set_announcement("x" * 281, "a@x.io")
        self.assertFalse(ok)
        self.assertEqual(error, "admin_announcement_long")

    def test_list_users_filters_and_sorts(self):
        users = [
            {"email": "b@x.io", "username": "Bea", "score": 10, "admin": False, "banned": False},
            {"email": "a@x.io", "username": "Ada", "score": 30, "admin": True, "banned": False},
            {"email": "c@x.io", "username": "Cem", "score": 5, "admin": False, "banned": True},
        ]
        with patch.object(admin_ops.firebaseDB, "getUsers", return_value=users):
            rows = admin_ops.list_users("ada")
            self.assertEqual([row["email"] for row in rows], ["a@x.io"])
            ranked = admin_ops.list_users("")
            self.assertEqual([row["email"] for row in ranked], ["a@x.io", "b@x.io", "c@x.io"])


if __name__ == "__main__":
    unittest.main()
