# Testing & Evaluation Plan

Two different concerns live in this file: conventional software testing (does the code do what it's supposed to) and model evaluation (does the system's reasoning actually hold up). Both are required before any phase is considered complete.

## Evaluation plan

Favors real ground truth over subjective review.

| Method | What it proves |
|---|---|
| Faithfulness eval — curated "why does X exist" questions across two repositories, with verified citations | The Historian cites the real commit or pull request, not a plausible-sounding fabrication. |
| Impact backtest — hide a historical commit, ask Impact / Risk what it would affect, compare to what actually changed | Blast-radius prediction is measured against real ground truth, not guesswork. |
| Critic override rate — how often the Critic changes or kills a Proposer suggestion | The debate layer earns its keep instead of rubber-stamping. |
| MCP Inspector + live client integration test | Every MCP tool schema is valid and actually callable, not just declared. |

Targets (from `PRD.md`): faithfulness ≥ 80%, impact/risk precision ≥ 0.6, Critic override rate tracked and reported (no fixed target — a rate near zero is itself a signal the debate isn't doing anything).

Evaluation sets live in `tests/eval/` (see `CONVENTIONS.md`), are version-controlled, and must include cases from at least two repositories — the reference repository used during development, and one external repository the system has never been tuned against.

## Testing strategy

- **Unit tests** — every module under `agents/`, `graph/`, and `memory/` (see `CONVENTIONS.md`'s folder layout). Cover the reconciliation logic (`add`/`update`/`delete`/`no-op`) explicitly — it's easy to get the edge cases wrong silently.
- **Integration tests** — exercise the REST API and MCP tools end-to-end against a small fixture repository checked into `tests/integration/fixtures/`, not against a live external repo.
- **Safety test (non-negotiable, every phase)** — an explicit test asserting that no code path can move a refactor suggestion out of `pending_human_review` except the human-approval action. This test must exist before Phase 1 is marked complete in `ROADMAP.md`, and must never be skipped or weakened.
- **CI** (Phase 2) — lint + full suite on every push; a red pipeline blocks merge.

## Definition of "evaluated," per phase

- **Phase 1 complete** requires the faithfulness eval run (not just written) against the reference repository, plus the safety test above passing.
- **Phase 2 complete** requires MCP Inspector validation, a live client integration test, and CI green on the current commit.
- **Phase 3 complete** requires the impact backtest run, and the full faithfulness eval re-run against the second, external repository.
