from __future__ import annotations

import asyncio
import sys

import pytest

from backend.main import (
    LocalOriginMiddleware,
    _ALLOW_REMOTE_ENV,
    _ALLOWED_ORIGINS_ENV,
    _is_loopback_host,
    _origin_allowed,
    _request_host_is_loopback,
    cli,
)


def _request(
    *,
    origin: str = "",
    host: str = "127.0.0.1:3001",
    method: str = "GET",
    sec_fetch_site: str = "",
) -> list[dict]:
    messages: list[dict] = []
    headers = [(b"host", host.encode())]
    if origin:
        headers.append((b"origin", origin.encode()))
    if sec_fetch_site:
        headers.append((b"sec-fetch-site", sec_fetch_site.encode()))
    if method == "OPTIONS":
        headers.extend(
            [
                (b"access-control-request-method", b"POST"),
                (b"access-control-request-headers", b"content-type"),
            ]
        )

    async def downstream(scope, receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": b'{"ok":true}'})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "method": method,
        "path": "/api/cache/clear",
        "headers": headers,
    }
    asyncio.run(LocalOriginMiddleware(downstream)(scope, receive, send))
    return messages


def _response_status(messages: list[dict]) -> int:
    return next(m["status"] for m in messages if m["type"] == "http.response.start")


def _response_headers(messages: list[dict]) -> dict[str, str]:
    message = next(m for m in messages if m["type"] == "http.response.start")
    return {key.decode(): value.decode() for key, value in message["headers"]}


def test_loopback_host_detection():
    assert _is_loopback_host("127.0.0.1")
    assert _is_loopback_host("::1")
    assert _is_loopback_host("localhost")
    assert not _is_loopback_host("0.0.0.0")
    assert not _is_loopback_host("192.168.1.20")
    assert _request_host_is_loopback("localhost:3001")
    assert _request_host_is_loopback("[::1]:3001")
    assert not _request_host_is_loopback("192.168.1.20:3001")


def test_local_origins_are_allowed_on_any_port(monkeypatch):
    monkeypatch.delenv(_ALLOW_REMOTE_ENV, raising=False)
    monkeypatch.delenv(_ALLOWED_ORIGINS_ENV, raising=False)
    assert _origin_allowed("http://localhost:5173", "127.0.0.1:3001")
    assert _origin_allowed("http://127.0.0.1:3001", "127.0.0.1:3001")
    assert _origin_allowed("http://[::1]:3001", "[::1]:3001")


def test_remote_origins_require_explicit_opt_in(monkeypatch):
    monkeypatch.delenv(_ALLOW_REMOTE_ENV, raising=False)
    monkeypatch.delenv(_ALLOWED_ORIGINS_ENV, raising=False)
    assert not _origin_allowed("http://192.168.1.20:3001", "192.168.1.20:3001")

    monkeypatch.setenv(_ALLOW_REMOTE_ENV, "1")
    assert _origin_allowed("http://192.168.1.20:3001", "192.168.1.20:3001")
    assert not _origin_allowed("https://attacker.example", "192.168.1.20:3001")


def test_remote_host_is_rejected_even_without_browser_headers(monkeypatch):
    monkeypatch.delenv(_ALLOW_REMOTE_ENV, raising=False)
    messages = _request(host="192.168.1.20:3001", method="GET")
    assert _response_status(messages) == 403


def test_remote_host_is_allowed_only_after_explicit_opt_in(monkeypatch):
    monkeypatch.setenv(_ALLOW_REMOTE_ENV, "1")
    messages = _request(host="192.168.1.20:3001", method="GET")
    assert _response_status(messages) == 200


def test_additional_origin_must_be_configured(monkeypatch):
    monkeypatch.delenv(_ALLOW_REMOTE_ENV, raising=False)
    monkeypatch.setenv(_ALLOWED_ORIGINS_ENV, "https://hud.example")
    assert _origin_allowed("https://hud.example", "192.168.1.20:3001")
    assert not _origin_allowed("https://attacker.example", "192.168.1.20:3001")


def test_untrusted_browser_origin_is_rejected_before_route_runs(monkeypatch):
    monkeypatch.delenv(_ALLOW_REMOTE_ENV, raising=False)
    monkeypatch.delenv(_ALLOWED_ORIGINS_ENV, raising=False)
    messages = _request(origin="https://attacker.example", method="POST")
    assert _response_status(messages) == 403


def test_cross_site_browser_request_without_origin_is_rejected():
    messages = _request(sec_fetch_site="cross-site", method="POST")
    assert _response_status(messages) == 403


def test_non_browser_client_without_origin_is_allowed():
    messages = _request(method="POST")
    assert _response_status(messages) == 200


def test_trusted_preflight_echoes_only_the_trusted_origin():
    messages = _request(origin="http://localhost:5173", method="OPTIONS")
    assert _response_status(messages) == 204
    headers = _response_headers(messages)
    assert headers["access-control-allow-origin"] == "http://localhost:5173"
    assert headers["access-control-allow-headers"] == "content-type"


def test_untrusted_preflight_is_denied():
    messages = _request(origin="https://attacker.example", method="OPTIONS")
    assert _response_status(messages) == 403


def test_cli_refuses_remote_bind_without_explicit_unsafe_flag(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["hermes-hudui", "--host", "0.0.0.0"])
    with pytest.raises(SystemExit) as exc:
        cli()
    assert exc.value.code == 2
