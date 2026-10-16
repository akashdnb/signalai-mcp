import httpx
import pytest

from signalai_mcp.capabilities import CapabilityClient


@pytest.mark.asyncio
async def test_company_search_propagates_service_and_tenant_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("signalai_mcp.capabilities.settings.service_token", "service-token")

    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.update({key.lower(): value for key, value in request.headers.items()})
        assert request.url.path == "/internal/capabilities/company/search"
        return httpx.Response(200, json={"operation": "company.search", "companies": []})

    client = CapabilityClient()
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        base_url="http://server",
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await client.search_companies(
            tenant_id="tenant-1",
            correlation_id="corr-1",
            query="SignalAI",
            limit=5,
        )
    finally:
        await client.close()

    assert result["operation"] == "company.search"
    assert seen["x-signalai-service-token"] == "service-token"
    assert seen["x-signalai-tenant-id"] == "tenant-1"
    assert seen["x-correlation-id"] == "corr-1"
