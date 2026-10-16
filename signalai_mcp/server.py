from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

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
        required_scopes=[settings.required_scope],
        validate_token_resource=True,
    ),
)


def tenant_from_token() -> str:
    token = get_access_token()
    if token is None:
        raise PermissionError("authentication_required")
    tenant_id = token.claims.get("tenant_id") if token.claims else None
    if not tenant_id:
        raise PermissionError("tenant_claim_required")
    return str(tenant_id)


async def invoke(ctx: Context[AppContext], capability: str, input: dict) -> dict:
    return await ctx.request_context.lifespan_context.capabilities.invoke(
        capability,
        tenant_id=tenant_from_token(),
        correlation_id=str(ctx.request_id),
        input=input,
    )


@mcp.custom_route("/.well-known/oauth-protected-resource/mcp", methods=["GET"])
async def protected_resource_metadata(_request: Request) -> Response:
    """Publish canonical RFC 9728 metadata for the /mcp resource.

    The MCP SDK's URL type normalizes HTTP URLs with a trailing slash. OAuth
    issuer identifiers are exact strings, so keep the advertised authorization
    server identical to SignalAI's issuer metadata instead of emitting a
    slash-variant that some clients treat as a different issuer.
    """
    return JSONResponse(
        {
            "resource": resource_server_url(),
            "authorization_servers": [oauth_issuer_url()],
            "scopes_supported": [settings.required_scope],
            "bearer_methods_supported": ["header"],
        }
    )


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> Response:
    return JSONResponse({"status": "ok", "service": settings.service_name})


# Existing company lookup is retained for the separate prospecting/enrichment
# surface. It is not part of the core client CRM toolset below.
@mcp.tool()
async def get_company(company_id: str, ctx: Context[AppContext]) -> dict:
    """Get a company visible to the authenticated SignalAI workspace."""
    return await invoke(ctx, "company.get", {"company_id": company_id})


# Leads
@mcp.tool()
async def list_leads(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List leads in the authenticated SignalAI workspace."""
    return await invoke(ctx, "lead.list", {"limit": min(max(limit, 1), 100)})


@mcp.tool()
async def get_lead(lead_id: str, ctx: Context[AppContext]) -> dict:
    """Get one SignalAI lead by ID."""
    return await invoke(ctx, "lead.get", {"lead_id": lead_id})


# Conversations
@mcp.tool()
async def list_conversations(ctx: Context[AppContext], limit: int = 50, lead_id: str | None = None) -> dict:
    """List conversations in the authenticated SignalAI workspace."""
    payload = {"limit": min(max(limit, 1), 100)}
    if lead_id:
        payload["lead_id"] = lead_id
    return await invoke(ctx, "conversation.list", payload)


@mcp.tool()
async def get_conversation(conversation_id: str, ctx: Context[AppContext]) -> dict:
    """Get a SignalAI conversation and its event history."""
    return await invoke(ctx, "conversation.get", {"conversation_id": conversation_id})


# Automations
@mcp.tool()
async def list_automations(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List automations/journeys in the authenticated SignalAI workspace."""
    return await invoke(ctx, "automation.list", {"limit": min(max(limit, 1), 100)})


@mcp.tool()
async def get_automation(automation_id: str, ctx: Context[AppContext]) -> dict:
    """Get an automation including its editable graph and latest published version."""
    return await invoke(ctx, "automation.get", {"automation_id": automation_id})


# Campaigns
@mcp.tool()
async def list_campaigns(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List campaigns in the authenticated SignalAI workspace."""
    return await invoke(ctx, "campaign.list", {"limit": min(max(limit, 1), 100)})


@mcp.tool()
async def get_campaign(campaign_id: str, ctx: Context[AppContext]) -> dict:
    """Get one SignalAI campaign by ID."""
    return await invoke(ctx, "campaign.get", {"campaign_id": campaign_id})


# Analytics
@mcp.tool()
async def get_analytics_overview(ctx: Context[AppContext]) -> dict:
    """Get a tenant-scoped SignalAI analytics overview for the last 30 days."""
    return await invoke(ctx, "analytics.overview", {})


# Contacts
@mcp.tool()
async def list_contacts(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List contacts in the authenticated SignalAI workspace."""
    return await invoke(ctx, "contact.list", {"limit": min(max(limit, 1), 100)})


@mcp.tool()
async def get_contact(contact_id: str, ctx: Context[AppContext]) -> dict:
    """Get one SignalAI contact by ID."""
    return await invoke(ctx, "contact.get", {"contact_id": contact_id})


# Integrations
@mcp.tool()
async def list_integrations(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List connected SignalAI integrations for the authenticated workspace."""
    return await invoke(ctx, "integration.list", {"limit": min(max(limit, 1), 100)})


@mcp.tool()
async def get_integration(integration_id: str, ctx: Context[AppContext]) -> dict:
    """Get one connected SignalAI integration without exposing credentials."""
    return await invoke(ctx, "integration.get", {"integration_id": integration_id})


app = mcp.streamable_http_app(
    host="0.0.0.0",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=settings.allowed_host_list,
        allowed_origins=settings.allowed_origin_list,
    ),
)
