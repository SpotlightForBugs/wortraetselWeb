import os
import unittest
from unittest.mock import patch

import cap


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class CapTests(unittest.TestCase):
    def test_missing_token_secret_or_url_is_rejected(self):
        url = "https://c.sfbhosting.eu/siteverify"
        self.assertFalse(cap.token_ok("", secret="sk-test", url=url))
        self.assertFalse(cap.token_ok("token", secret="", url=url))
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(cap.token_ok("token", secret="sk-test"))

    def test_verification_posts_to_the_coolify_url(self):
        calls = {}

        def post(url, json, timeout):
            calls["url"] = url
            calls["json"] = json
            calls["timeout"] = timeout
            return FakeResponse({"success": True})

        env = {"CAP_SERVER_URL": "https://c.sfbhosting.eu/siteverify"}
        with patch.dict(os.environ, env, clear=True):
            self.assertTrue(cap.token_ok("token-1", secret="sk-test", post=post))
        self.assertEqual(calls["url"], "https://c.sfbhosting.eu/siteverify")
        self.assertEqual(calls["json"], {"secret": "sk-test", "response": "token-1"})
        self.assertFalse(
            cap.token_ok(
                "token-1",
                secret="sk-test",
                url=env["CAP_SERVER_URL"],
                post=lambda url, json, timeout: FakeResponse({"success": False}),
            )
        )
        self.assertFalse(
            cap.token_ok(
                "token-1",
                secret="sk-test",
                url=env["CAP_SERVER_URL"],
                post=lambda url, json, timeout: (_ for _ in ()).throw(OSError("down")),
            )
        )


if __name__ == "__main__":
    unittest.main()
