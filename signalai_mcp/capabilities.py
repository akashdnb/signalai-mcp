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
        principal_id: str | None = None,
        client_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        tenant_id = tenant_id.strip()
        correlation_id = correlation_id.strip()
        if not tenant_id:
            raise ValueError("tenant_id_required")
        if not correlation_id:
            raise ValueError("correlation_id_required")

        headers = {
            "X-SignalAI-Service-Token": settings.service_token or "",
            "X-SignalAI-Tenant-ID": tenant_id,
            "X-Correlation-ID": correlation_id,
            "Accept": "application/json",
        }
        if principal_id is not None:
            headers["X-SignalAI-Principal-Id"] = principal_id
        if client_id is not None:
            headers["X-SignalAI-Client-Id"] = client_id
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key

        try:
            response = await self._client.post(
                f"/v1/capabilities/{capability}:invoke",
                headers=headers,
                json=input,
            )
        except httpx.RequestError:
            return {
                "error": "upstream_error",
                "code": "upstream_error",
                "message": "SignalAI could not be reached. Retry using the same idempotency key.",
                "correlationId": correlation_id,
            }

        if response.is_error:
            try:
                body = response.json()
            except ValueError:
                body = {}
            safe_codes = {
                "authentication_required", "invalid_token", "token_expired",
                "insufficient_scope", "tenant_not_found", "resource_not_found",
                "validation_error", "capability_unavailable", "upstream_error",
                "rate_limited", "version_conflict", "invalid_lifecycle_state",
                "activation_not_ready", "idempotency_conflict", "idempotency_in_progress",
            }
            code = body.get("code") or body.get("error")
            if not isinstance(code, str) or code not in safe_codes:
                code = {
                    401: "invalid_token",
                    403: "insufficient_scope",
                    404: "resource_not_found",
                    409: "version_conflict",
                    422: "validation_error",
                    429: "rate_limited",
                }.get(response.status_code, "upstream_error")
            result: dict[str, Any] = {
                "error": code,
                "code": code,
                "message": body.get("message") if isinstance(body.get("message"), str) else "The capability request was rejected.",
                "correlationId": body.get("correlationId") or correlation_id,
            }
            for field in ("currentVersion", "recovery", "validationErrors", "retryAfterSeconds"):
                if field in body:
                    result[field] = body[field]
            return result

        try:
            return response.json()
        except ValueError:
            return {
                "error": "upstream_error",
                "code": "upstream_error",
                "message": "SignalAI returned an unreadable response.",
                "correlationId": correlation_id,
            }
