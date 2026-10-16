from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import Context
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from signalai_mcp.auth import ConfiguredTokenVerifier
from signalai_mcp.capabilities import CapabilityClient
from signalai_mcp.config import settings


@dataclass
class AppContext:
    capabilities: CapabilityClient


def canonical_url(value: object) -> str:
    return str(value).rstrip("/")


def oauth_issuer_url() -> str:
    return canonical_url(settings.auth_issuer_url)


def resource_server_url() -> str:
    return canonical_url(settings.public_url)


@mcp.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET"])
async def protected_resource_metadata(_request: Request) -> Response:
    """Publish supported OAuth scopes for the MCP resource."""
    return JSONResponse({
        "resource": resource_server_url(),
        "authorization_servers": [oauth_issuer_url()],
        "scopes_supported": [settings.read_scope, settings.write_scope],
        "bearer_methods_supported": ["header"],
    })


@asynccontextmanager
async def lifespan(_server: MCPServer) -> AsyncIterator[AppContext]:
    client = CapabilityClient()
    try:
        yield AppContext(capabilities=client)
    finally:
        await client.close()


mcp = MCPServer(
    "SignalAI",
    version=settings.service_version,
    lifespan=lifespan,
    token_verifier=ConfiguredTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(oauth_issuer_url()),
        resource_server_url=AnyHttpUrl(resource_server_url()),
        # Scope is enforced per tool so read-only tokens remain supported.
        required_scopes=[],
        validate_token_resource=True,
    ),
)


def authenticated_identity() -> tuple[str, str, str]:
    token = get_access_token()
    if token is None:
        raise PermissionError("authentication_required")
    claims = token.claims or {}
    tenant_id = claims.get("tenant_id")
    principal_id = token.subject or claims.get("sub")
    client_id = token.client_id
    if not tenant_id:
        raise PermissionError("tenant_not_found")
    if not principal_id or not client_id:
        raise PermissionError("invalid_token")
    return str(tenant_id), str(principal_id), str(client_id)


def require_tool_scope(scope: str) -> tuple[str, str, str]:
    identity = authenticated_identity()
    token = get_access_token()
    scopes = set(token.scopes if token else [])
    if scope not in scopes:
        raise PermissionError("insufficient_scope")
    return identity




def idempotency_key(value: str | None) -> str:
    key = (value or "").strip()
    if not key or len(key) > 200:
        raise ValueError("idempotency_key_invalid")
    return key

async def invoke(
    ctx: Context[AppContext],
    capability: str,
    input: dict,
    *,
    scope: str | None = None,
    write_key: str | None = None,
) -> dict:
    tenant_id, principal_id, client_id = (
        require_tool_scope(scope) if scope else authenticated_identity()
    )
    return await ctx.request_context.lifespan_context.capabilities.invoke(
        capability,
        tenant_id=tenant_id,
        correlation_id=str(ctx.request_id),
        input=input,
        principal_id=principal_id if scope == settings.write_scope else None,
        client_id=client_id if scope == settings.write_scope else None,
        idempotency_key=idempotency_key(write_key) if scope == settings.write_scope else None,
    )


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> Response:
    return JSONResponse({"status": "ok", "service": settings.service_name})


# Existing company lookup is retained for the separate prospecting/enrichment
# surface. It is not part of the core client CRM toolset below.
@mcp.tool()
async def get_company(company_id: str, ctx: Context[AppContext]) -> dict:
    """Get a company visible to the authenticated SignalAI workspace."""
    return await invoke(ctx, "company.get", {"company_id": company_id}, scope=settings.read_scope)


# Leads
@mcp.tool()
async def list_leads(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List leads in the authenticated SignalAI workspace."""
    return await invoke(ctx, "lead.list", {"limit": min(max(limit, 1), 100)}, scope=settings.read_scope)


@mcp.tool()
async def get_lead(lead_id: str, ctx: Context[AppContext]) -> dict:
    """Get one SignalAI lead by ID."""
    return await invoke(ctx, "lead.get", {"lead_id": lead_id}, scope=settings.read_scope)


# Conversations
@mcp.tool()
async def list_conversations(ctx: Context[AppContext], limit: int = 50, lead_id: str | None = None) -> dict:
    """List conversations in the authenticated SignalAI workspace."""
    payload = {"limit": min(max(limit, 1), 100)}
    if lead_id:
        payload["lead_id"] = lead_id
    return await invoke(ctx, "conversation.list", payload, scope=settings.read_scope)


@mcp.tool()
async def get_conversation(conversation_id: str, ctx: Context[AppContext]) -> dict:
    """Get a SignalAI conversation and its event history."""
    return await invoke(ctx, "conversation.get", {"conversation_id": conversation_id}, scope=settings.read_scope)


# Automations
@mcp.tool()
async def list_automations(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List automations/journeys in the authenticated SignalAI workspace."""
    return await invoke(ctx, "automation.list", {"limit": min(max(limit, 1), 100)}, scope=settings.read_scope)


@mcp.tool()
async def get_automation(automation_id: str, ctx: Context[AppContext]) -> dict:
    """Get an automation including its editable graph and latest published version."""
    return await invoke(ctx, "automation.get", {"automation_id": automation_id}, scope=settings.read_scope)


@mcp.tool()
async def create_automation_draft(
    name: str,
    trigger: str,
    idempotency_key: str,
    ctx: Context[AppContext],
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict:
    """Create a new SignalAI automation as a draft. It is not published or activated."""
    payload: dict[str, Any] = {"name": name, "trigger": trigger}
    if nodes is not None:
        payload["nodes"] = nodes
    if edges is not None:
        payload["edges"] = edges
    if metadata is not None:
        payload["metadata"] = metadata
    return await invoke(ctx, "automation.create_draft", payload, scope=settings.write_scope, write_key=idempotency_key)


@mcp.tool()
async def update_automation_draft(
    automation_id: str,
    expected_version: int,
    changes: dict[str, Any],
    idempotency_key: str,
    ctx: Context[AppContext],
) -> dict:
    """Update an inactive, unpublished SignalAI automation draft using expected-version checks."""
    return await invoke(
        ctx, "automation.update_draft",
        {"automation_id": automation_id, "expected_version": expected_version, "changes": changes},
        scope=settings.write_scope, write_key=idempotency_key,
    )


@mcp.tool()
async def validate_automation(
    idempotency_key: str,
    ctx: Context[AppContext],
    automation_id: str | None = None,
    nodes: list[dict[str, Any]] | None = None,
    edges: list[dict[str, Any]] | None = None,
    expected_version: int | None = None,
) -> dict:
    """Validate an automation draft using SignalAI's canonical journey rules; this does not publish it."""
    payload: dict[str, Any] = {}
    if automation_id is not None:
        payload["automation_id"] = automation_id
    if nodes is not None:
        payload["nodes"] = nodes
    if edges is not None:
        payload["edges"] = edges
    if expected_version is not None:
        payload["expected_version"] = expected_version
    return await invoke(ctx, "automation.validate", payload, scope=settings.write_scope, write_key=idempotency_key)


# Campaigns
@mcp.tool()
async def list_campaigns(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List campaigns in the authenticated SignalAI workspace."""
    return await invoke(ctx, "campaign.list", {"limit": min(max(limit, 1), 100)}, scope=settings.read_scope)


@mcp.tool()
async def get_campaign(campaign_id: str, ctx: Context[AppContext]) -> dict:
    """Get one SignalAI campaign by ID."""
    return await invoke(ctx, "campaign.get", {"campaign_id": campaign_id}, scope=settings.read_scope)


# Analytics
@mcp.tool()
async def get_analytics_overview(ctx: Context[AppContext]) -> dict:
    """Get a tenant-scoped SignalAI analytics overview for the last 30 days."""
    return await invoke(ctx, "analytics.overview", {}, scope=settings.read_scope)


# Contacts
@mcp.tool()
async def list_contacts(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List contacts in the authenticated SignalAI workspace."""
    return await invoke(ctx, "contact.list", {"limit": min(max(limit, 1), 100)}, scope=settings.read_scope)


@mcp.tool()
async def get_contact(contact_id: str, ctx: Context[AppContext]) -> dict:
    """Get one SignalAI contact by ID."""
    return await invoke(ctx, "contact.get", {"contact_id": contact_id}, scope=settings.read_scope)


# Integrations
@mcp.tool()
async def list_integrations(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List connected SignalAI integrations for the authenticated workspace."""
    return await invoke(ctx, "integration.list", {"limit": min(max(limit, 1), 100)}, scope=settings.read_scope)


@mcp.tool()
async def get_integration(integration_id: str, ctx: Context[AppContext]) -> dict:
    """Get one connected SignalAI integration without exposing credentials."""
    return await invoke(ctx, "integration.get", {"integration_id": integration_id}, scope=settings.read_scope)


app = mcp.streamable_http_app(
    host="0.0.0.0",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=settings.allowed_host_list,
        allowed_origins=settings.allowed_origin_list,
    ),
)
