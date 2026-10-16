# MCP Security Model

## Trust boundary

Treat MCP clients and model-generated tool arguments as untrusted input. Authentication and authorization are established outside the model prompt.

## Tenant isolation

The authenticated workspace is the security boundary. Every capability invocation must carry the server-validated workspace context.

A tool must never accept a model-supplied workspace ID as permission to access another workspace.

## Permission model

Use least privilege. Read-only tools should not inherit write permissions. Execute tools should require explicit action permission and may require human approval.

## Secrets

Never expose:

- provider access tokens
- refresh tokens
- database credentials
- internal signing keys
- unrelated users' private data

Tool outputs should be redacted and minimized.

## Prompt/tool injection

External content may contain instructions intended to manipulate the model. MCP tools must enforce authorization independently of model reasoning. A webpage, message, lead note or connector response cannot grant permission to perform an action.

## High-impact actions

For sending messages, publishing automations, bulk changes or other irreversible actions, support:

1. preview
2. validation
3. explicit approval
4. execution
5. audit

The agent/model cannot skip these stages by changing tool arguments.

## Auditing

Record principal, workspace, tool, action tier, request/correlation ID, target resource and outcome for mutations. Avoid recording sensitive payloads unnecessarily.

## Operational security

- service authentication between MCP and server
- TLS in production
- bounded request timeouts
- rate limiting
- structured security logs
- dependency scanning
- schema validation
- tenant-isolation tests

## Incident response

If a tool is discovered to permit cross-tenant access or an unauthorized side effect, disable the affected tool/capability first, preserve audit evidence, rotate affected credentials if required, and patch the server-side authorization boundary before re-enabling it.
