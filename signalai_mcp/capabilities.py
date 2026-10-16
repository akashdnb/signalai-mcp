from typing import Any

import httpx

from signalai_mcp.config import settings


class CapabilityClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=str(settings.capability_base_url).rstrip("/"),
            timeout=httpx.Timeout(settings.capability_timeout_seconds),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def invoke(
        self,
        capability: str,
        *,
        tenant_id: str,
        correlation_id: str,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._client.post(
            f"/v1/capabilities/{capability}:invoke",
            headers=self._headers(tenant_id, correlation_id),
            json=input,
        )
        response.raise_for_status()
        return response.json()

    async def search_companies(
        self,
        *,
        tenant_id: str,
        correlation_id: str,
        query: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        response = await self._client.post(
            "/internal/capabilities/company/search",
            headers=self._headers(tenant_id, correlation_id),
            json={"query": query, "limit": min(max(limit, 1), 100)},
        )
        response.raise_for_status()
        return response.json()

    async def get_company(
        self,
        *,
        tenant_id: str,
        correlation_id: str,
        domain: str | None = None,
        company_name: str | None = None,
        linkedin_url: str | None = None,
    ) -> dict[str, Any]:
        response = await self._client.post(
            "/internal/capabilities/company/get",
            headers=self._headers(tenant_id, correlation_id),
            json={
                key: value
                for key, value in {
                    "domain": domain,
                    "companyName": company_name,
                    "linkedinUrl": linkedin_url,
                }.items()
                if value,
            },
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _headers(tenant_id: str, correlation_id: str) -> dict[str, str]:
        if not settings.service_token:
            raise RuntimeError("SIGNALAI_SERVICE_TOKEN is required for capability calls")
        return {
            "X-SignalAI-Service-Token": settings.service_token,
            "X-SignalAI-Tenant-Id": tenant_id,
            "X-Correlation-Id": correlation_id,
        }
