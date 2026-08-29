# Technical Stack

Every choice below is locked (see `DECISIONS.md` for the reasoning trail). Do not substitute or add to this list without recording a new decision entry first.

| Layer | Technology | Why |
|---|---|---|
| Language / runtime | Python 3.11+ | One language across ingestion, agents, API, CLI, and MCP server keeps the stack small enough for a solo/small-team build to actually finish. |
| Orchestration | LangChain, LangGraph | LangGraph gives explicit state-machine control over agent routing and supports the human-in-the-loop interrupt the Refactor path requires; raw chains don't. |
| LLM | An LLM API, e.g. Groq / Llama 3.3 70B | Fast inference keeps multi-agent latency (Supervisor → specialist → possibly Proposer/Critic debate) acceptable; swappable behind a single interface. |
| Retrieval | ChromaDB + sentence-embedding models | Hybrid vector + keyword retrieval over commit messages, PR text, and docstrings; embedded/local, no separate service to operate for Phase 1. |
| Graph store | NetworkX | In-process, zero-ops graph for the repository's file/commit/PR/author/co-change graph; has a documented migration path to a dedicated graph database if scale demands it later. |
| Ingestion | GitPython / PyGitHub, Python's built-in `ast` module | Mature, well-documented libraries for git history and host-platform API access; `ast` avoids a heavier external parser for the initial language. |
| Protocol / API | FastMCP + MCP Python SDK, FastAPI, Uvicorn | FastMCP is the standard for building an MCP server in Python; FastAPI gives async support, automatic OpenAPI docs, and Pydantic integration for the REST layer. |
| CLI | Typer + Rich | Typer gives type-hint-driven CLI definitions consistent with the rest of the Pydantic-typed codebase; Rich makes terminal output actually readable. |
| Dashboard | Streamlit | Python-native, fast to build without a separate frontend toolchain; adequate for an internal/demo-grade graph-visualization surface (Phase 3). |
| Storage | SQLite | Zero-ops relational store for the audit log and reconciled memory; sufficient at Phase 1–2 scale, no server to run. |
| Validation | Pydantic | Schema-validated structured output from every agent — every response is checked against a schema before it's returned, not just prompted for. |
| Operations | Docker, Docker Compose, GitHub Actions | Single-command deployment and CI on every push — required for the production-readiness bar in `ARCHITECTURE.md`. |

## What's deliberately not here

- **A dedicated graph database** (e.g. Neo4j) — not justified at Phase 1–2 scale; NetworkX's migration path exists precisely so this can change later without a rewrite.
- **A JS/TS frontend framework** — Streamlit keeps the whole stack in Python; revisit only if the dashboard's UX requirements outgrow it.
- **Kubernetes** — Docker Compose is sufficient for a single-command deployment target; no multi-node requirement has been identified.
