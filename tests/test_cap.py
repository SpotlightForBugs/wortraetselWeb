import unittest

import cap


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class CapTests(unittest.TestCase):
    def test_endpoint_uses_the_server_and_site_key(self):
        self.assertEqual(
            cap.endpoint("https://cap.example.com/", "abc123"),
            "https://cap.example.com/abc123/",
        )
        self.assertEqual(cap.verify_url("https://cap.example.com", "abc123"), "https://cap.example.com/abc123/siteverify")
        self.assertEqual(cap.endpoint("", "abc123"), "")

    def test_missing_config_or_token_is_rejected(self):
        self.assertFalse(cap.token_ok("", server="https://cap.example.com", site_key="abc", secret="sk-test"))
        self.assertFalse(cap.token_ok("token", server="", site_key="abc", secret="sk-test"))
        self.assertFalse(cap.token_ok("token", server="https://cap.example.com", site_key="abc", secret=""))

    def test_only_a_successful_verification_is_accepted(self):
        calls = {}

        def post(url, json, timeout):
            calls["url"] = url
            calls["json"] = json
            calls["timeout"] = timeout
            return FakeResponse({"success": True})

        self.assertTrue(
            cap.token_ok(
                "token-1",
                server="https://cap.example.com",
                site_key="abc",
                secret="sk-test",
                post=post,
            )
        )
        self.assertEqual(calls["url"], "https://cap.example.com/abc/siteverify")
        self.assertEqual(calls["json"], {"secret": "sk-test", "response": "token-1"})
        self.assertFalse(
            cap.token_ok(
                "token-1",
                server="https://cap.example.com",
                site_key="abc",
                secret="sk-test",
                post=lambda url, json, timeout: FakeResponse({"success": False}),
            )
        )
        self.assertFalse(
            cap.token_ok(
                "token-1",
                server="https://cap.example.com",
                site_key="abc",
                secret="sk-test",
                post=lambda url, json, timeout: (_ for _ in ()).throw(OSError("down")),
            )
        )


if __name__ == "__main__":
    unittest.main()
