# Product Requirements — Codebase Historian

## Problem

Every codebase accumulates decisions nobody remembers making. Git blame shows who last touched a line, not why. Code review tools read a diff in isolation, never the abandoned approaches and review threads that preceded it. New contributors spend their first weeks re-deriving context that already exists, scattered across commit messages and closed issues nobody reopens. Refactoring tools suggest changes with no knowledge of what else in the codebase has historically moved in lockstep with the file being touched.

## Solution

Codebase Historian treats a repository's history — commits, pull requests, issues, and code structure — as a queryable knowledge graph instead of an append-only log nobody revisits. A small team of specialized agents reasons over that graph to explain why code exists, predict what a change would affect, and propose improvements — with "explain this" and "change this" treated as different risk tiers requiring different levels of oversight.

## Who this is for

- **Maintainers and tech leads** who need to understand blast radius before approving a change.
- **New contributors** who need onboarding context that doesn't exist as a single document anywhere.
- **Reviewers** who want a second, evidence-grounded opinion on a proposed refactor before approving it.
- **Other tools and agents** that want programmatic access to repository history and reasoning via MCP.

## What it does

1. **Explains** why a file, function, or pattern exists, citing the specific commits, pull requests, and discussions behind it.
2. **Predicts impact** — given a proposed change, what else is likely to need updating, based on historical co-change patterns and dependency structure.
3. **Proposes refactors** — a Proposer agent drafts a concrete, history-grounded improvement; a Critic agent independently tries to refute it; only a suggestion that survives that debate is shown to a human for approval. Nothing is ever auto-committed.
4. **Onboards new contributors** — generates a starting guide: the most central files by graph centrality, key architectural decisions traced from major pull requests, and a suggested reading order.
5. **Maintains its own memory** — explanations are reconciled (added, updated, marked stale, or left alone) as the codebase evolves, instead of going stale silently.

## In scope

- Public Git repositories, read-only access.
- The five-agent reasoning team described in `ARCHITECTURE.md`.
- Delivery via REST API, CLI, MCP server, and (Phase 3) a dashboard.
- Evaluation against a reference repository and at least one external repository never seen during development.

## Out of scope (for now)

- Private/proprietary repositories — deferred until access-control and data-handling requirements are defined.
- Auto-committing or auto-opening pull requests for suggested refactors — the system explains and suggests; a human always decides.
- Multi-language parsing beyond the initial target language — listed as a Phase 3 / stretch capability in `ROADMAP.md`.
- The dashboard — Phase 3, not required for a working, evaluable system.

## Success criteria

- **Faithfulness:** ≥ 80% of "why does X exist" evaluation questions answered with a correct, verifiable citation, across two repositories.
- **Impact / Risk precision:** ≥ 0.6 against a historical backtest (hide a past commit, ask what it would affect, compare to what actually changed).
- **Zero unreviewed refactors:** no suggestion reaches a user without passing Critic review and the human approval gate — every time, no exceptions.
- **Cold-demo readiness:** the system runs live against a repository not specially prepared in advance.
- **Deployment:** starts with a single command; MCP tools pass MCP Inspector validation; at least one live client integration is verified.
