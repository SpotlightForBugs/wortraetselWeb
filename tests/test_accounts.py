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
