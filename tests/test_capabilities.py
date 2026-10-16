import httpx
import pytest

from signalai_mcp.capabilities import CapabilityClient
from signalai_mcp.config import settings


@pytest.mark.asyncio
async def test_capability_client_propagates_service_auth_tenant_and_correlation(monkeypatch):
    monkeypatch.setattr(settings, "service_token", "server-service-token")
    monkeypatch.setattr(settings, "capability_base_url", "http://signalai-server:3000")

    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = CapabilityClient()
    await client.close()
    client._client = httpx.AsyncClient(
        base_url=str(settings.capability_base_url).rstrip("/"),
        transport=transport,
        timeout=httpx.Timeout(settings.capability_timeout_seconds),
    )

    try:
        result = await client.invoke(
            "lead.list",
            tenant_id="tenant-123",
            correlation_id="corr-456",
            input={"limit": 10},
        )
        assert result == {"ok": True}
        assert captured["method"] == "POST"
        assert captured["url"].endswith("/v1/capabilities/lead.list:invoke")
        assert captured["headers"]["x-signalai-service-token"] == "server-service-token"
        assert captured["headers"]["x-signalai-tenant-id"] == "tenant-123"
        assert captured["headers"]["x-correlation-id"] == "corr-456"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_capability_client_requires_service_token(monkeypatch):
    monkeypatch.setattr(settings, "service_token", None)
    with pytest.raises(RuntimeError, match="SIGNALAI_SERVICE_TOKEN is required"):
        CapabilityClient()
