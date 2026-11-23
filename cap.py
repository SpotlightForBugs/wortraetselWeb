import os

import requests


def token_ok(token, secret=None, post=None, url=None):
    if secret is None:
        secret = os.environ.get("CAP_SECRET")
    if url is None:
        url = (os.environ.get("CAP_SERVER_URL") or "").strip()
    if not token or not secret or not url:
        return False
    send = post or requests.post
    try:
        response = send(
            url,
            json={"secret": secret, "response": token},
            timeout=5,
        )
        payload = response.json()
    except Exception:
        return False
    return isinstance(payload, dict) and payload.get("success") is True
