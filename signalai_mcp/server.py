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
        issuer_url=AnyHttpUrl(str(settings.auth_issuer_url)),
        resource_server_url=AnyHttpUrl(str(settings.public_url)),
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


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> Response:
    return JSONResponse({"status": "ok", "service": settings.service_name})


@mcp.tool()
async def search_companies(query: str, ctx: Context[AppContext], limit: int = 10) -> dict:
    """Search external company intelligence visible to the authenticated SignalAI workspace."""
    if not query.strip():
        raise ValueError("company_search_query_required")
    return await ctx.request_context.lifespan_context.capabilities.search_companies(
        tenant_id=tenant_from_token(),
        correlation_id=str(ctx.request_id),
        query=query,
        limit=limit,
    )


@mcp.tool()
async def get_company(
    ctx: Context[AppContext],
    domain: str | None = None,
    company_name: str | None = None,
    linkedin_url: str | None = None,
) -> dict:
    """Research a company by domain, name, or LinkedIn URL."""
    if not any((domain, company_name, linkedin_url)):
        raise ValueError("company_identifier_required")
    return await ctx.request_context.lifespan_context.capabilities.get_company(
        tenant_id=tenant_from_token(),
        correlation_id=str(ctx.request_id),
        domain=domain,
        company_name=company_name,
        linkedin_url=linkedin_url,
    )


@mcp.tool()
async def list_leads(ctx: Context[AppContext], limit: int = 50) -> dict:
    """List leads visible to the authenticated SignalAI workspace."""
    bounded_limit = min(max(limit, 1), 100)
    return await ctx.request_context.lifespan_context.capabilities.invoke(
        "lead.list",
        tenant_id=tenant_from_token(),
        correlation_id=str(ctx.request_id),
        input={"limit": bounded_limit},
    )


@mcp.tool()
async def get_conversation(conversation_id: str, ctx: Context[AppContext]) -> dict:
    """Get a conversation visible to the authenticated SignalAI workspace."""
    return await ctx.request_context.lifespan_context.capabilities.invoke(
        "conversation.get",
        tenant_id=tenant_from_token(),
        correlation_id=str(ctx.request_id),
        input={"conversation_id": conversation_id},
    )


@mcp.tool()
async def list_automations(ctx: Context[AppContext]) -> dict:
    """List automations visible to the authenticated SignalAI workspace."""
    return await ctx.request_context.lifespan_context.capabilities.invoke(
        "automation.list",
        tenant_id=tenant_from_token(),
        correlation_id=str(ctx.request_id),
        input={},
    )


app = mcp.streamable_http_app(
    host="0.0.0.0",
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=settings.allowed_host_list,
        allowed_origins=settings.allowed_origin_list,
    ),
)
