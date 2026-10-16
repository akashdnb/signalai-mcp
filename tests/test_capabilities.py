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


@pytest.mark.asyncio
async def test_capability_client_propagates_write_identity_and_idempotency_headers(monkeypatch):
    monkeypatch.setattr(settings, "service_token", "service-secret")
    monkeypatch.setattr(settings, "capability_base_url", "http://signalai-server:3000")
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"status": "draft"})

    client = CapabilityClient()
    await client.close()
    client._client = httpx.AsyncClient(
        base_url=str(settings.capability_base_url).rstrip("/"),
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(settings.capability_timeout_seconds),
    )
    try:
        result = await client.invoke(
            "automation.create_draft",
            tenant_id="tenant-123",
            correlation_id="corr-456",
            input={"name": "Qualification", "trigger": "details"},
            principal_id="user-123",
            client_id="client-123",
            idempotency_key="idem-123",
        )
        assert result["status"] == "draft"
        assert captured["headers"]["x-signalai-principal-id"] == "user-123"
        assert captured["headers"]["x-signalai-client-id"] == "client-123"
        assert captured["headers"]["idempotency-key"] == "idem-123"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_capability_client_normalizes_structured_conflict(monkeypatch):
    monkeypatch.setattr(settings, "service_token", "service-secret")
    monkeypatch.setattr(settings, "capability_base_url", "http://signalai-server:3000")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={
            "error": "version_conflict",
            "code": "version_conflict",
            "message": "Re-read the automation.",
            "currentVersion": 4,
            "recovery": "reread_automation",
        })

    client = CapabilityClient()
    await client.close()
    client._client = httpx.AsyncClient(
        base_url=str(settings.capability_base_url).rstrip("/"),
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(settings.capability_timeout_seconds),
    )
    try:
        result = await client.invoke(
            "automation.update_draft", tenant_id="tenant-123",
            correlation_id="corr-456", input={"automation_id": "a", "expected_version": 2, "changes": {"name": "x"}},
        )
        assert result["code"] == "version_conflict"
        assert result["currentVersion"] == 4
        assert result["recovery"] == "reread_automation"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_capability_client_normalizes_unexpected_upstream_404(monkeypatch):
    """A stale/unsupported capability must not become an MCP tool exception."""
    monkeypatch.setattr(settings, "service_token", "service-secret")
    monkeypatch.setattr(settings, "capability_base_url", "http://signalai-server:3000")

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "capability_unavailable", "code": "capability_unavailable"})

    client = CapabilityClient()
    await client.close()
    client._client = httpx.AsyncClient(
        base_url=str(settings.capability_base_url).rstrip("/"),
        transport=httpx.MockTransport(handler),
        timeout=httpx.Timeout(settings.capability_timeout_seconds),
    )
    try:
        result = await client.invoke(
            "unsupported.capability", tenant_id="tenant-123", correlation_id="corr-456", input={},
        )
        assert result == {
            "error": "capability_unavailable",
            "code": "capability_unavailable",
            "message": "The capability request was rejected.",
            "correlationId": "corr-456",
        }
    finally:
        await client.close()
