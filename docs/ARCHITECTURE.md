# SignalAI MCP Architecture

## Purpose

`signalai-mcp` is the external AI-facing capability adapter for SignalAI. It exposes carefully designed MCP tools over the stable capability layer owned by `signalai-server`.

MCP is an interface, not a second business layer.

## Request flow

```text
External AI / MCP client
        |
        v
MCP transport
        |
        v
authentication + workspace context
        |
        v
permission / action policy
        |
        v
SignalAI capability API
        |
        v
server domain modules
        |
        v
DB / queues / connectors
```

The MCP service must never bypass the capability layer to query or mutate the production database.

## Responsibilities

- MCP server lifecycle and transport
- tool registration and schemas
- authentication/context propagation
- permission tier enforcement
- input validation
- tool result normalization
- audit metadata propagation
- compatibility/versioning
- MCP-specific error mapping

## Out of scope

- CRM business rules
- journey validation/publication rules
- persistence ownership
- direct database access
- provider protocol handling
- autonomous agent planning

## Tool categories

### Read

Safe retrieval tools such as:

- search leads
- get lead
- search conversations
- get conversation
- list automations
- get automation
- metrics queries

### Draft

Tools that prepare a mutation without applying it:

- create automation draft
- propose journey changes
- prepare lead update

### Write

Tools that apply a bounded mutation where policy permits:

- update lead fields
- add CRM note
- create content

### Execute

High-impact side effects:

- publish automation
- send outbound message
- trigger bulk operation

Execute operations require stricter authorization and, where appropriate, explicit human approval.

## Tool design

Tools should be task-oriented rather than thin wrappers over database methods.

Good:

`search_leads`

Avoid:

`query_leads_collection`

Each tool should have a stable name, strict input schema, explicit workspace context and predictable output/error semantics.

## Security

Every request must establish:

- authenticated principal
- workspace
- requested capability
- permission/action tier

Never trust workspace IDs or account IDs supplied only by the model. The authenticated context determines what the caller can access.

## Auditability

Write operations must carry request/correlation IDs and audit context. The server owns authoritative audit records.

Tool responses should not leak secrets, access tokens, internal database identifiers that are not needed by the caller, or cross-workspace data.

## Versioning

Treat tool schemas as public APIs. Breaking changes require a new tool version or compatibility layer. Removing a tool requires a deprecation period when external clients depend on it.

## Native SignalAI chatbot reuse

The same capability layer exposed through MCP should also be usable by SignalAI's own AI experiences. Do not implement a second set of business actions specifically for MCP.

## Failure behavior

Return typed, actionable errors. Never expose raw stack traces. Distinguish authorization, validation, not-found, conflict, rate-limit and internal failures.
