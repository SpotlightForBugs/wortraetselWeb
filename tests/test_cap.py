import unittest

import cap


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class CapTests(unittest.TestCase):
    def test_missing_token_or_secret_is_rejected(self):
        self.assertFalse(cap.token_ok("", secret="sk-test"))
        self.assertFalse(cap.token_ok("token", secret=""))

    def test_only_a_successful_verification_is_accepted(self):
        calls = {}

        def post(url, json, timeout):
            calls["url"] = url
            calls["json"] = json
            calls["timeout"] = timeout
            return FakeResponse({"success": True})

        self.assertTrue(cap.token_ok("token-1", secret="sk-test", post=post))
        self.assertEqual(calls["url"], "https://c.sfbhosting.eu/siteverify")
        self.assertEqual(calls["json"], {"secret": "sk-test", "response": "token-1"})
        self.assertFalse(
            cap.token_ok(
                "token-1",
                secret="sk-test",
                post=lambda url, json, timeout: FakeResponse({"success": False}),
            )
        )
        self.assertFalse(
            cap.token_ok(
                "token-1",
                secret="sk-test",
                post=lambda url, json, timeout: (_ for _ in ()).throw(OSError("down")),
            )
        )


if __name__ == "__main__":
    unittest.main()
