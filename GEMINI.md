# Antigravity (Gemini) — Session Protocol & Operating Instructions

This file is automatically loaded at the start of every session in this repository.

## Start-of-Chat Instruction (Mandatory)

Execute this workflow at the start of every chat session:

> **Resume from the last entry in `docs/PROGRESS.md` — don't start cold.**
>
> **Task:** [TODAY'S TASK — or leave blank to pick up the next unchecked item in `docs/ROADMAP.md`'s active phase, in order]
>
> Work only inside `src/` and `tests/`, plus the `docs/` updates below. Stay scoped to this one task — don't touch other roadmap items or files while you're in here. Stop and ask before adding any dependency not already in `docs/TECH_STACK.md`.
>
> Before finishing: run the tests, check the `docs/ROADMAP.md` box only if this is genuinely complete and tested, and append a new dated entry to `docs/PROGRESS.md`.

## Lifecycle & Git Rules

- **Git commit and push after each phase** (and after completing verified phase milestones).
- Follow `docs/CONVENTIONS.md` for folder structure, naming, and commit style without exception.
- Never mark a refactor-suggestion feature "done" if it can reach a user without passing Critic review and the human approval gate described in `docs/ARCHITECTURE.md` — this constraint is non-negotiable.
- Before changing any architectural decision recorded in `docs/DECISIONS.md`, add a new dated entry explaining what changed and why — never edit or delete a prior entry.
