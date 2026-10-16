from typing import Any

import httpx

from signalai_mcp.config import settings


class CapabilityClient:
    def __init__(self) -> None:
        if not settings.service_token:
            raise RuntimeError("SIGNALAI_SERVICE_TOKEN is required")
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
        tenant_id = tenant_id.strip()
        correlation_id = correlation_id.strip()
        if not tenant_id:
            raise ValueError("tenant_id_required")
        if not correlation_id:
            raise ValueError("correlation_id_required")

        response = await self._client.post(
            f"/v1/capabilities/{capability}:invoke",
            headers={
                "X-SignalAI-Service-Token": settings.service_token,
                "X-SignalAI-Tenant-ID": tenant_id,
                "X-Correlation-ID": correlation_id,
                "Accept": "application/json",
            },
            json=input,
        )
        response.raise_for_status()
        return response.json()
