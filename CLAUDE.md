# Claude Code — operating instructions

This file is auto-loaded by Claude Code at the start of every session in this repository. It is intentionally short. Full context lives in `/docs` — treat `/docs` as the single source of truth, not this file.

This file and `AGENTS.md` (Codex CLI's equivalent auto-loaded file) must stay in sync. If you update one, update the other the same way.

## Before you write any code

Read, in order: `docs/ARCHITECTURE.md`, `docs/ROADMAP.md`, and `docs/DECISIONS.md`. Do not start implementation work without them — they contain locked decisions you must not silently re-derive, contradict, or replace.

## One-line project summary

Codebase Historian is a multi-agent GraphRAG platform: it ingests a repository's git history, PR/issue history, and source, builds a knowledge graph and a reconciled memory store from it, and reasons over both with a five-agent team (Historian, Impact / Risk, Refactor Proposer ↔ Critic, Onboarding) behind a Supervisor router. Served via REST API, CLI, MCP server, and a Streamlit dashboard.

## Stack summary

Python 3.11+ · LangChain + LangGraph · an LLM API (e.g. Groq / Llama 3.3 70B) · ChromaDB + sentence-embeddings · NetworkX · GitPython/PyGitHub + `ast` · FastAPI + Uvicorn · FastMCP + MCP Python SDK · Typer + Rich · Streamlit · Pydantic · SQLite · Docker + Docker Compose · GitHub Actions CI.

Full rationale for each choice: `docs/TECH_STACK.md`. Do not swap or add to this stack without recording why in `docs/DECISIONS.md`.

## Folder layout

Currently: this README, this file, `AGENTS.md`, and `/docs`. No `src/` exists yet — its proposed layout is defined in `docs/CONVENTIONS.md`; create it exactly as specified there when Phase 1 implementation begins.

## How to run things

Nothing is runnable yet — no code exists. Once Phase 1 scaffolding lands, this section must be updated with real setup and run commands.

## Start-of-chat workflow (mandatory)

Resume from the last entry in `docs/PROGRESS.md` — don't start cold.

Task: [TODAY'S TASK — or leave blank to pick up the next unchecked item in `docs/ROADMAP.md`'s active phase, in order]

Work only inside `src/` and `tests/`, plus the `docs/` updates below. Stay scoped to this one task — don't touch other roadmap items or files while you're in here. Stop and ask before adding any dependency not already in `docs/TECH_STACK.md`.

Before finishing: run the tests, check the `docs/ROADMAP.md` box only if this is genuinely complete and tested, and append a new dated entry to `docs/PROGRESS.md`.

## Standing rules

- **Git commit and push after each phase.**
- **After completing any implementation task — however small — append a dated entry to `docs/PROGRESS.md` before ending the session.** State what was built, which files changed, any decisions made along the way, and what the logical next step is. This is not optional; it is how the next session (yours or another agent's) recovers context.
- Before changing any architectural decision recorded in `docs/DECISIONS.md`, add a new dated entry explaining what changed and why — never edit or delete a prior entry.
- Follow `docs/CONVENTIONS.md` for folder structure, naming, and commit style without exception.
- Never mark a refactor-suggestion feature "done" if it can reach a user without passing Critic review and the human approval gate described in `docs/ARCHITECTURE.md` — this constraint is non-negotiable.
- Only make changes directly requested or clearly required by the current roadmap milestone. Do not add extra files, abstractions, dependencies, or features beyond what `docs/ROADMAP.md` calls for at the current phase.
