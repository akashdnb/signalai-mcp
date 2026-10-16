import json
from unittest.mock import AsyncMock

import httpx
import pytest

from signalai_mcp.auth import ConfiguredTokenVerifier
from signalai_mcp.config import settings


@pytest.mark.asyncio
async def test_configured_token_verifier_accepts_scoped_tenant_token(monkeypatch):
    monkeypatch.setattr(
        settings,
        "auth_tokens",
        json.dumps(
            {
                "token-a": {
                    "client_id": "client-a",
                    "tenant_id": "tenant-a",
                    "scopes": [settings.required_scope],
                }
            }
        ),
    )
    monkeypatch.setattr(settings, "auth_introspection_url", None)
    verifier = ConfiguredTokenVerifier()
    try:
        token = await verifier.verify_token("token-a")
        assert token is not None
        assert token.client_id == "client-a"
        assert token.claims["tenant_id"] == "tenant-a"
    finally:
        await verifier.close()


@pytest.mark.asyncio
async def test_configured_token_verifier_rejects_missing_scope(monkeypatch):
    monkeypatch.setattr(
        settings,
        "auth_tokens",
        json.dumps(
            {
                "token-b": {
                    "client_id": "client-b",
                    "tenant_id": "tenant-b",
                    "scopes": [],
                }
            }
        ),
    )
    monkeypatch.setattr(settings, "auth_introspection_url", None)
    verifier = ConfiguredTokenVerifier()
    try:
        assert await verifier.verify_token("token-b") is None
    finally:
        await verifier.close()


@pytest.mark.asyncio
async def test_configured_token_verifier_rejects_missing_tenant(monkeypatch):
    monkeypatch.setattr(
        settings,
        "auth_tokens",
        json.dumps(
            {
                "token-c": {
                    "client_id": "client-c",
                    "scopes": [settings.required_scope],
                }
            }
        ),
    )
    monkeypatch.setattr(settings, "auth_introspection_url", None)
    verifier = ConfiguredTokenVerifier()
    try:
        assert await verifier.verify_token("token-c") is None
    finally:
        await verifier.close()


@pytest.mark.asyncio
async def test_configured_token_verifier_introspects_with_service_token(monkeypatch):
    monkeypatch.setattr(settings, "auth_tokens", None)
    monkeypatch.setattr(settings, "auth_introspection_url", "https://signalai-server.example/oauth/introspect")
    monkeypatch.setattr(settings, "service_token", "service-secret")
    monkeypatch.setattr(settings, "public_url", "https://signalai-mcp.example/mcp")
    verifier = ConfiguredTokenVerifier()
    response = httpx.Response(
        200,
        json={
            "active": True,
            "client_id": "client-d",
            "tenant_id": "tenant-d",
            "scope": settings.required_scope,
            "sub": "user-d",
            "aud": "https://signalai-mcp.example/mcp",
            "exp": 4102444800,
        },
        request=httpx.Request("POST", "https://signalai-server.example/oauth/introspect"),
    )
    verifier._client.post = AsyncMock(return_value=response)  # type: ignore[method-assign]
    try:
        token = await verifier.verify_token("access-token")
        assert token is not None
        assert token.subject == "user-d"
        assert token.claims["tenant_id"] == "tenant-d"
        verifier._client.post.assert_awaited_once_with(
            "https://signalai-server.example/oauth/introspect",
            data={"token": "access-token"},
            headers={"Accept": "application/json", "X-SignalAI-Service-Token": "service-secret"},
        )
    finally:
        await verifier.close()
