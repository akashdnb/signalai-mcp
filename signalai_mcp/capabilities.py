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
            headers={
                "X-Tenant-Id": tenant_id,
                "X-Correlation-Id": correlation_id,
            },
            json=input,
        )
        response.raise_for_status()
        return response.json()
