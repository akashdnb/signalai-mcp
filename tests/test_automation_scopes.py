import json

import pytest

from signalai_mcp.auth import ConfiguredTokenVerifier
from signalai_mcp.config import settings


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope",
    [settings.automation_publish_scope, settings.automation_operate_scope],
)
async def test_configured_token_verifier_accepts_opt_in_automation_scope(monkeypatch, scope):
    monkeypatch.setattr(
        settings,
        "auth_tokens",
        json.dumps({
            "automation-token": {
                "client_id": "client-automation",
                "sub": "user-automation",
                "tenant_id": "tenant-automation",
                "scopes": [scope],
            }
        }),
    )
    monkeypatch.setattr(settings, "auth_introspection_url", None)
    verifier = ConfiguredTokenVerifier()
    try:
        token = await verifier.verify_token("automation-token")
        assert token is not None
        assert token.scopes == [scope]
    finally:
        await verifier.close()
