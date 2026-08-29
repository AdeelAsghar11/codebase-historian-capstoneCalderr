# Codebase Historian

A multi-agent GraphRAG platform that explains why code in a repository exists, predicts what a proposed change would affect, and proposes reviewed refactors — under adversarial agent review and a mandatory human approval gate.

**Status:** Phase 1 (Foundation) — not yet started. This repository currently contains documentation only; no source code has been written.

## Start here

If you are a coding agent (Claude Code or Codex CLI) picking this project up, read `CLAUDE.md` or `AGENTS.md` first — both point into `/docs`, which is the source of truth for this project.

If you are a person, read in this order:

1. [`docs/PRD.md`](docs/PRD.md) — what this is, who it's for, what's in and out of scope
2. [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the full system design
3. [`docs/ROADMAP.md`](docs/ROADMAP.md) — what gets built in which phase
4. [`docs/TECH_STACK.md`](docs/TECH_STACK.md) — every technology choice and why
5. [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — knowledge graph, memory, and storage schema
6. [`docs/API.md`](docs/API.md) — planned REST and MCP surface
7. [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) — folder layout, naming, testing, commit style
8. [`docs/DECISIONS.md`](docs/DECISIONS.md) — why we chose what we chose, in order
9. [`docs/TESTING.md`](docs/TESTING.md) — how the system gets evaluated
10. [`docs/PROGRESS.md`](docs/PROGRESS.md) — the running log of what's actually been built

## Why the docs exist before the code

This project is designed to be implemented by an AI coding agent across multiple sessions. Every session ends by writing to `docs/PROGRESS.md`, so the next session — even a different agent, even weeks later — can load full context cold instead of re-deriving decisions or contradicting ones already made.
