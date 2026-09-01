#!/usr/bin/env python3
# SPDX-License-Identifier: MulanPSL-2.0
# Copyright (c) 2026 whiteyoungy
"""模拟企业侧的 OAuth2 授权服务器（client_credentials 流）。

保留了现场常见的几个特征：
- 只支持 client_credentials，不支持 Implicit / ROPC（OAuth 2.1 已移除这两种）
- token 有效期很短（120 秒），逼调用方实现缓存与过期前刷新
- 校验 scope，越权 scope 直接拒
- 提供 introspect 端点供资源服务器校验

用法：python3 fixtures/mock_idp.py [--port 9080]
"""
import argparse
import json
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

CLIENTS = {"fde-gateway": "s3cr3t-gateway"}
ALLOWED_SCOPES = {"orders.read"}
TTL = 120  # 秒，故意短

_tokens: dict[str, dict] = {}
_issued = {"count": 0}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/_stats":
            return self._json(200, {"issued": _issued["count"], "live": len(_tokens)})
        self._json(404, {"error": "not_found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        form = parse_qs(self.rfile.read(n).decode())
        get = lambda k: (form.get(k) or [""])[0]

        if self.path == "/oauth2/token":
            grant = get("grant_type")
            if grant in ("password", "implicit"):
                # OAuth 2.1 草案第 10 节移除了这两种 grant
                return self._json(400, {"error": "unsupported_grant_type",
                                        "error_description": "OAuth 2.1 已移除 ROPC/Implicit"})
            if grant != "client_credentials":
                return self._json(400, {"error": "unsupported_grant_type"})
            cid, sec = get("client_id"), get("client_secret")
            if CLIENTS.get(cid) != sec:
                return self._json(401, {"error": "invalid_client"})
            scopes = set(filter(None, get("scope").split()))
            if not scopes or not scopes <= ALLOWED_SCOPES:
                return self._json(400, {"error": "invalid_scope",
                                        "error_description": f"允许的 scope：{sorted(ALLOWED_SCOPES)}"})
            tok = secrets.token_urlsafe(24)
            _tokens[tok] = {"exp": time.time() + TTL, "scope": " ".join(sorted(scopes)), "sub": cid}
            _issued["count"] += 1
            return self._json(200, {"access_token": tok, "token_type": "Bearer",
                                    "expires_in": TTL, "scope": " ".join(sorted(scopes))})

        if self.path == "/oauth2/introspect":
            tok = get("token")
            rec = _tokens.get(tok)
            if not rec or rec["exp"] < time.time():
                _tokens.pop(tok, None)
                return self._json(200, {"active": False})
            return self._json(200, {"active": True, "scope": rec["scope"],
                                    "sub": rec["sub"], "exp": int(rec["exp"])})

        self._json(404, {"error": "not_found"})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9080)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"[idp] OAuth2 授权服务器已启动 http://127.0.0.1:{a.port}  "
          f"(client_credentials only, token TTL={TTL}s)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
