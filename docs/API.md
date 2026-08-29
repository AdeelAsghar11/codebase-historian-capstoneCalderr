# API — planned surface

This is a spec to build toward, not an implemented contract. Request/response shapes are described at field level; Pydantic models formalize them exactly during Phase 1 implementation. REST and MCP expose the same underlying capabilities — the MCP tools below are 1:1 wrappers around the REST endpoints.

## REST API (FastAPI, base path `/v1`)

Phase 2 onward, every endpoint below requires `Authorization: Bearer <api_key>` and is rate-limited per key (see `ARCHITECTURE.md`).

### `GET /health`
Returns `{ status, last_indexed_commit, graph_node_count, degraded: bool }`. Backed by the `index_state` table (`DATA_MODEL.md`).

### `POST /explain`
Request: `{ repo_url, target }` — `target` is a file path or a symbol qualname.
Response: `{ answer, citations: [{ commit_sha, pr_number, excerpt }], confidence }`.
Routed to the **Historian** agent.

### `POST /impact`
Request: `{ repo_url, change_description }` (a diff or a plain-language description of the intended change).
Response: `{ affected_files: [...], confidence, evidence: "co-change" | "dependency" | "both" }`.
Routed to the **Impact / Risk** agent.

### `POST /refactor/suggest`
Request: `{ repo_url, target }`.
Response: `{ proposal, critic_verdict: { refuted: bool, notes }, status: "pending_human_review" }`.
Routed to the **Refactor Proposer ↔ Critic** pair. Never returns a status other than `pending_human_review` or `rejected_by_critic` — there is no code path that marks a suggestion approved without a separate human action.

### `POST /refactor/{id}/approve`
Phase 2+, requires auth. The only endpoint that can move a suggestion out of `pending_human_review`. Human-initiated only — no agent may call this endpoint on its own suggestion.

### `POST /onboarding/guide`
Request: `{ repo_url }`.
Response: `{ reading_order: [...], central_files: [...], key_decisions: [...] }`.
Routed to the **Onboarding** agent. Phase 3.

## MCP server (FastMCP)

Exposed as tools, callable directly from any MCP-compatible client:

| Tool | Mirrors | Notes |
|---|---|---|
| `explain_code(repo_url, target)` | `POST /explain` | |
| `trace_impact(repo_url, change_description)` | `POST /impact` | |
| `suggest_refactor(repo_url, target)` | `POST /refactor/suggest` | Tool description must state explicitly that output requires human approval and is never auto-applied. |
| `onboarding_guide(repo_url)` | `POST /onboarding/guide` | Phase 3. |

MCP tools must pass MCP Inspector validation and at least one live client integration test before Phase 2 is considered complete (`ROADMAP.md`).

## What's intentionally absent

No endpoint or tool can commit code, open a pull request, or otherwise mutate the target repository. This is a hard boundary, not a Phase 1 limitation to be lifted later without a new, explicit decision recorded in `DECISIONS.md`.
