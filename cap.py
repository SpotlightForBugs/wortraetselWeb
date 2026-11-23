import os

import requests


def endpoint(server, site_key):
    server = (server or "").strip().rstrip("/")
    site_key = (site_key or "").strip().strip("/")
    if not server or not site_key:
        return ""
    return f"{server}/{site_key}/"


def verify_url(server, site_key):
    base = endpoint(server, site_key)
    if not base:
        return ""
    return base + "siteverify"


def token_ok(token, server=None, site_key=None, secret=None, post=None):
    if server is None:
        server = os.environ.get("CAP_SERVER_URL")
    if site_key is None:
        site_key = os.environ.get("CAP_SITE_KEY")
    if secret is None:
        secret = os.environ.get("CAP_SECRET")
    url = verify_url(server, site_key)
    if not token or not url or not secret:
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
