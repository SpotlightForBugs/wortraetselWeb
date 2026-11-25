def client_ip(req):
    """Return the real client IP.

    Behind Cloudflare, request.remote_addr is the proxy address, so prefer the
    CF-Connecting-IP header and fall back to remote_addr when it is absent.
    """
    return req.headers.get("CF-Connecting-IP") or req.remote_addr
