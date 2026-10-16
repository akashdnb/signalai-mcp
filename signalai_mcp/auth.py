import json
from typing import Any

import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier

from signalai_mcp.config import settings


class ConfiguredTokenVerifier(TokenVerifier):
    """Verify bearer tokens through RFC 7662 or an explicit test-token map."""

    def __init__(self) -> None:
        self._tokens = self._load_tokens()
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

    async def close(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _load_tokens() -> dict[str, dict[str, object]]:
        if not settings.auth_tokens:
            return {}
        try:
            configured = json.loads(settings.auth_tokens)
        except json.JSONDecodeError:
            return {}
        return configured if isinstance(configured, dict) else {}

    async def verify_token(self, token: str) -> AccessToken | None:
        if settings.auth_introspection_url:
            return await self._introspect(token)

        entry = self._tokens.get(token)
        if not isinstance(entry, dict):
            return None
        scopes = entry.get("scopes", [settings.required_scope])
        if not isinstance(scopes, list) or settings.required_scope not in scopes:
            return None
        if not entry.get("tenant_id"):
            return None
        return self._access_token(token, entry, [str(scope) for scope in scopes])

    async def _introspect(self, token: str) -> AccessToken | None:
        auth = None
        if settings.auth_client_id and settings.auth_client_secret:
            auth = (settings.auth_client_id, settings.auth_client_secret)
        try:
            response = await self._client.post(
                str(settings.auth_introspection_url),
                data={"token": token},
                auth=auth,
            )
            if response.status_code >= 500:
                return None
            response.raise_for_status()
            body: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError):
            return None

        if not body.get("active") or not body.get("tenant_id"):
            return None
        scope_text = body.get("scope", "")
        scopes = scope_text.split() if isinstance(scope_text, str) else list(scope_text or [])
        if settings.required_scope not in scopes:
            return None
        return self._access_token(token, body, [str(scope) for scope in scopes])

    def _access_token(
        self,
        token: str,
        claims: dict[str, Any],
        scopes: list[str],
    ) -> AccessToken:
        return AccessToken(
            token=token,
            client_id=str(claims.get("client_id", claims.get("sub", "unknown"))),
            scopes=scopes,
            resource=str(settings.public_url),
            subject=str(claims["sub"]) if claims.get("sub") else None,
            claims={"tenant_id": str(claims["tenant_id"])},
        )
