# Conventions

## Folder structure

Create exactly this layout when Phase 1 implementation begins — do not restructure it without recording why in `DECISIONS.md`:

```
src/
  codebase_historian/
    ingestion/       # git history, PR/issue API clients, AST parsing
    graph/            # knowledge graph construction and queries (NetworkX)
    memory/            # reconciled memory store + reconciliation logic
    agents/             # Supervisor, Historian, Impact / Risk, Proposer, Critic, Onboarding
    api/                 # FastAPI app, routers, request/response schemas
    cli/                  # Typer app
    mcp_server/            # FastMCP tool definitions
    dashboard/               # Streamlit app (Phase 3)
    config.py
tests/
  unit/
  integration/
  eval/                # curated evaluation sets — faithfulness questions, impact backtest cases
scripts/
docs/                    # this folder
```

## Naming

- Modules and functions: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Pydantic request/response models: suffix `Request` / `Response` (e.g. `ExplainRequest`, `ExplainResponse`) — never reuse one model for both directions.
- Agent classes: suffix `Agent` (e.g. `HistorianAgent`, `CriticAgent`).

## Testing

- `pytest` for all tests. Every module under `agents/`, `graph/`, and `memory/` needs unit test coverage before it is considered done — not just before Phase 2.
- Integration tests exercise the REST API and MCP tools end-to-end against a small fixture repository, not just mocked internals.
- Evaluation sets (`tests/eval/`) are data, not code — curated questions/cases with known-correct answers, versioned alongside the code that they evaluate. See `TESTING.md`.
- CI (Phase 2) runs lint + the full test suite on every push; a red pipeline blocks merge.

## Commits

Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. Reference the roadmap milestone in the body when applicable, e.g. `Refs: ROADMAP Phase 1 / Historian agent`.

## Documentation discipline

- `docs/PROGRESS.md` gets a new entry at the end of every implementation session — see the standing rule in `CLAUDE.md` / `AGENTS.md`.
- `docs/DECISIONS.md` gets a new entry whenever an architectural or stack decision is made or changed — append-only, never edit a past entry.
- Docs are updated in the same session as the code they describe, not deferred to "later."
