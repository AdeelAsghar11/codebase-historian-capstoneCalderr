# Roadmap

This file tracks planned scope per phase. It is not a log of what's actually been built — that's `PROGRESS.md`. Update a milestone's checkbox here only when it is genuinely done (tested, not just started); log the details of *how* in `PROGRESS.md`.

## Phase 1 — Foundation — **ACTIVE**

Outcome: a complete, demoable, evaluated system on its own.

- [x] Ingestion pipeline — git history + source AST structure extraction
- [x] Knowledge graph construction (NetworkX) — files × commits × PRs × authors × co-change edges
- [x] Hybrid retrieval index (ChromaDB + embeddings) over commit messages, PRs, docstrings
- [x] Reconciled memory store (SQLite) — add / update / delete / no-op logic
- [x] Supervisor-orchestrated routing (LangGraph state graph)
- [x] Historian agent — cited, evidence-grounded explanations
- [x] Refactor Proposer ↔ Critic adversarial debate loop
- [x] Mandatory human review gate before any refactor suggestion is considered approved (CLI-level confirmation is acceptable for Phase 1)
- [x] Structured, schema-validated output (Pydantic) on every agent response
- [x] CLI (Typer + Rich)
- [x] Minimal REST API (FastAPI) exposing the same capabilities as the CLI
- [x] Containerized build (Dockerfile + docker-compose for local dev)
- [x] Faithfulness evaluation set (see `TESTING.md`) run against the reference repository

## Phase 2 — Production Hardening — PLANNED

Outcome: a system a third party could deploy and trust.

- [x] API-key authentication + token-bucket rate limiting on every REST endpoint and MCP tool
- [x] Structured audit logging (SQLite) — timestamp, caller, tool, latency
- [x] Health-check endpoint — graph freshness, last-indexed commit
- [x] MCP server (FastMCP) exposing explain / trace-impact / suggest-refactor / onboarding as tools
- [x] MCP Inspector validation + at least one live client integration test
- [ ] Incremental re-indexing via webhook
- [ ] CI pipeline (GitHub Actions) — lint + full test suite on every push

## Phase 3 — Extended Capabilities — PLANNED

Outcome: the version that demonstrates range, not just completeness.

- [ ] Impact / Risk agent + historical backtest evaluation
- [ ] Onboarding agent (centrality-ranked reading order + traced architectural decisions)
- [ ] Interactive graph-visualization dashboard (Streamlit)
- [ ] Validation against a second, external repository never seen during development
- [ ] Recorded end-to-end demonstration

### Stretch (only if time remains after Phase 3)

- [ ] Draft change-set generation — reviewable diff + description, still gated; never auto-committed
- [ ] Multi-language parsing beyond the initial language, via a general-purpose parser

## Feature tiers, for reference

Every capability above maps to one of three tiers when scoping any single work session:

- **Core** — required for Phase 1 to count as complete.
- **Phase 2** — required for the production-readiness claim.
- **Stretch** — valuable, not required; do not start stretch work while any Core or Phase 2 item is incomplete.
