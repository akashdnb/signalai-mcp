import json

from mcp.server.auth.provider import AccessToken, TokenVerifier

from signalai_mcp.config import settings


class ConfiguredTokenVerifier(TokenVerifier):
    """Verifies bearer tokens configured by the deployment secret store.

    This is deliberately isolated behind the MCP SDK TokenVerifier contract so
    the deployment can replace it with OIDC/JWKS or RFC 7662 introspection
    without changing any tool implementation.
    """

    def __init__(self) -> None:
        self._tokens = self._load_tokens()

    @staticmethod
    def _load_tokens() -> dict[str, dict[str, object]]:
        if not settings.service_token:
            return {}
        try:
            configured = json.loads(settings.service_token)
        except json.JSONDecodeError:
            return {
                settings.service_token: {
                    "client_id": "configured-client",
                    "scopes": [settings.required_scope],
                }
            }
        if not isinstance(configured, dict):
            return {}
        return configured

    async def verify_token(self, token: str) -> AccessToken | None:
        entry = self._tokens.get(token)
        if not isinstance(entry, dict):
            return None
        scopes = entry.get("scopes", [settings.required_scope])
        if not isinstance(scopes, list) or settings.required_scope not in scopes:
            return None
        return AccessToken(
            token=token,
            client_id=str(entry.get("client_id", "configured-client")),
            scopes=[str(scope) for scope in scopes],
            resource=str(settings.public_url),
            claims={"tenant_id": entry.get("tenant_id")} if entry.get("tenant_id") else {},
        )
