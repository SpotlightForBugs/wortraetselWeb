import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import firebase_admin
from flask import Flask, request

# accounts initialises firebase_admin at import time; pretend it is already set up.
with patch.dict(firebase_admin._apps, {"[DEFAULT]": object()}):
    import accounts

from request_utils import client_ip


class FallbackUsernameTests(unittest.TestCase):
    def _auth_only_user(self):
        auth_user = types.SimpleNamespace(display_name=None)
        db = MagicMock()
        db.collection.return_value.stream.return_value = []
        return auth_user, db

    def test_auth_only_user_gets_legacy_flag_and_doc(self):
        auth_user, db = self._auth_only_user()
        with patch.object(
            accounts.auth, "get_user_by_email", return_value=auth_user
        ), patch.object(accounts.firebaseDB, "getDB", return_value=db), patch.object(
            accounts.firebaseDB, "ensure_user_doc"
        ) as ensure:
            result = accounts.getUsername("daniil@example.com")
            self.assertEqual(result, {"username": "daniil", "legacy": False})
            ensure.assert_called_once_with("daniil@example.com", "daniil")
            self.assertFalse(accounts.is_legacy("daniil@example.com"))

    def test_failed_doc_creation_is_reported_but_not_fatal(self):
        auth_user, db = self._auth_only_user()
        with patch.object(
            accounts.auth, "get_user_by_email", return_value=auth_user
        ), patch.object(accounts.firebaseDB, "getDB", return_value=db), patch.object(
            accounts.firebaseDB, "ensure_user_doc", side_effect=RuntimeError("down")
        ), patch.object(
            accounts.sentry_sdk, "capture_exception"
        ) as capture:
            result = accounts.getUsername("daniil@example.com")
            self.assertEqual(result, {"username": "daniil", "legacy": False})
            capture.assert_called_once()

    def test_legacy_doc_user_is_legacy(self):
        auth_user, db = self._auth_only_user()
        doc = MagicMock()
        doc.to_dict.return_value = {"email": "a@example.com", "username": "Ada"}
        db.collection.return_value.stream.return_value = [doc]
        with patch.object(
            accounts.auth, "get_user_by_email", return_value=auth_user
        ), patch.object(accounts.firebaseDB, "getDB", return_value=db):
            self.assertTrue(accounts.is_legacy("a@example.com"))


class AccountSettingsTests(unittest.TestCase):
    def test_update_display_name_rejects_short_names(self):
        ok, error = accounts.update_display_name("a@example.com", "x")
        self.assertFalse(ok)
        self.assertEqual(error, "bad_name")

    def test_update_display_name_writes_auth_and_firestore(self):
        user = types.SimpleNamespace(uid="uid1")
        with patch.object(
            accounts.auth, "get_user_by_email", return_value=user
        ), patch.object(accounts.auth, "update_user") as update, patch.object(
            accounts.firebaseDB, "set_username"
        ) as set_name:
            ok, name = accounts.update_display_name("a@example.com", "  Ada  ")
            self.assertTrue(ok)
            self.assertEqual(name, "Ada")
            update.assert_called_once_with("uid1", display_name="Ada")
            set_name.assert_called_once_with("a@example.com", "Ada")

    def test_change_password_checks_current_then_updates(self):
        user = types.SimpleNamespace(uid="uid1")
        with patch.object(
            accounts, "login", return_value="a@example.com"
        ), patch.object(
            accounts.auth, "get_user_by_email", return_value=user
        ), patch.object(
            accounts.auth, "update_user"
        ) as update:
            ok, error = accounts.change_password("a@example.com", "old", "newpass")
            self.assertTrue(ok)
            self.assertIsNone(error)
            update.assert_called_once_with("uid1", password="newpass")

    def test_change_password_rejects_wrong_current(self):
        with patch.object(accounts, "login", return_value=False):
            ok, error = accounts.change_password("a@example.com", "bad", "newpass")
            self.assertFalse(ok)
            self.assertEqual(error, "bad_login")

    def test_change_password_rejects_weak_new(self):
        ok, error = accounts.change_password("a@example.com", "old", "123")
        self.assertFalse(ok)
        self.assertEqual(error, "weak_password")

    def test_delete_account_removes_auth_and_doc(self):
        user = types.SimpleNamespace(uid="uid1")
        with patch.object(
            accounts, "login", return_value="a@example.com"
        ), patch.object(
            accounts.auth, "get_user_by_email", return_value=user
        ), patch.object(
            accounts.auth, "delete_user"
        ) as delete, patch.object(
            accounts.firebaseDB, "delete_user_doc"
        ) as delete_doc:
            ok, error = accounts.delete_account("a@example.com", "secret")
            self.assertTrue(ok)
            self.assertIsNone(error)
            delete.assert_called_once_with("uid1")
            delete_doc.assert_called_once_with("a@example.com")


class ClientIpTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)

    def test_prefers_cloudflare_header(self):
        with self.app.test_request_context(
            headers={"CF-Connecting-IP": "203.0.113.7"},
            environ_base={"REMOTE_ADDR": "10.0.0.1"},
        ):
            self.assertEqual(client_ip(request), "203.0.113.7")

    def test_falls_back_to_remote_addr(self):
        with self.app.test_request_context(environ_base={"REMOTE_ADDR": "10.0.0.1"}):
            self.assertEqual(client_ip(request), "10.0.0.1")


if __name__ == "__main__":
    unittest.main()
