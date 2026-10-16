import json

import pytest

from signalai_mcp.auth import ConfiguredTokenVerifier
from signalai_mcp.config import settings


@pytest.mark.asyncio
async def test_configured_token_verifier_accepts_scoped_token(monkeypatch):
    monkeypatch.setattr(
        settings,
        "service_token",
        json.dumps({"token-a": {"client_id": "client-a", "tenant_id": "tenant-a", "scopes": [settings.required_scope]}}),
    )
    verifier = ConfiguredTokenVerifier()
    token = await verifier.verify_token("token-a")
    assert token is not None
    assert token.client_id == "client-a"
    assert token.claims["tenant_id"] == "tenant-a"


@pytest.mark.asyncio
async def test_configured_token_verifier_rejects_missing_scope(monkeypatch):
    monkeypatch.setattr(
        settings,
        "service_token",
        json.dumps({"token-b": {"client_id": "client-b", "tenant_id": "tenant-b", "scopes": []}}),
    )
    verifier = ConfiguredTokenVerifier()
    assert await verifier.verify_token("token-b") is None
