# MCP Tool Contracts

## Standard shape

Every tool must define:

- stable name
- description focused on user outcome
- strict input schema
- authenticated workspace context
- permission tier
- deterministic result shape
- typed error behavior
- idempotency behavior for mutations

## Naming

Use domain-neutral capability names:

```text
search_leads
get_lead
search_conversations
get_conversation
list_automations
get_automation
create_automation_draft
validate_automation
publish_automation
activate_automation
pause_automation
get_lead_metrics
get_campaign_metrics
```

Avoid exposing storage or implementation terms.

## Automation lifecycle scopes

Automation mutations are intentionally split by impact:

| OAuth scope | Tools | Purpose | Default |
|---|---|---|---|
| `signalai:write` | `create_automation_draft`, `update_automation_draft`, `validate_automation` | Prepare and validate drafts | existing write opt-in |
| `signalai:automation:publish` | `publish_automation` | Publish an inactive validated draft | opt-in, off unless granted |
| `signalai:automation:operate` | `activate_automation`, `pause_automation` | Start/stop an already-published automation | opt-in, off unless granted |

The dashboard is the future control plane for granting/revoking these scopes. Until that UI exists, an OAuth client must explicitly request the lifecycle scope and the MCP resource will only use it when the issued token contains it.

A token with `signalai:write` alone cannot publish, activate, or pause an automation.

## Action tiers

| Tier | Examples | Approval |
|---|---|---|
| READ | search/get/list/metrics | normally none |
| DRAFT | create draft/propose change | none or workspace policy |
| WRITE | update CRM/add note/create content | policy dependent |
| EXECUTE | publish/send/bulk operation | explicit permission; approval where high impact |

Publishing and activation/pause are EXECUTE-level automation operations and require their dedicated scopes.

## Automation lifecycle

```text
create draft -> update/save -> validate -> publish -> activate -> pause
                                              ^             |
                                              |-------------|
```

`publish_automation` requires an inactive, unpublished draft and an expected builder version. Publishing creates an immutable runtime snapshot but does not activate it.

`activate_automation` requires a published automation and at least one healthy assigned Instagram account.

`pause_automation` only pauses an active automation. Repeated lifecycle requests return a structured lifecycle conflict rather than silently changing state.

## Mutation safety

Mutating tools should accept an idempotency key. High-impact operations should support a preview/dry-run form when feasible.

For journey changes, prefer:

```text
create draft -> validate -> review -> publish -> activate
```

The model must not directly alter an immutable published journey version.

## Output rules

Return structured objects with enough information for the caller to continue safely. Do not force an AI client to parse human prose to determine success.

Example:

```json
{
  "success": true,
  "data": {
    "automationId": "auto_123",
    "version": 18,
    "status": "DRAFT"
  }
}
```

## Errors

Use stable codes such as:

- `UNAUTHENTICATED`
- `FORBIDDEN`
- `NOT_FOUND`
- `VALIDATION_ERROR`
- `CONFLICT`
- `APPROVAL_REQUIRED`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

The underlying server capability remains responsible for domain validation.

## Contract evolution

Tool schemas are external API contracts. Add optional fields before making breaking changes. Deprecate before removal. Maintain compatibility for clients that may not upgrade simultaneously.
