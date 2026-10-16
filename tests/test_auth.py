import json

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
