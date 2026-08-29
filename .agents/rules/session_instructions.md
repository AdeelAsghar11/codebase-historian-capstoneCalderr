# Session Workflow & Operating Rules

## Start-of-Chat Protocol (Mandatory)

Execute this workflow at the start of every chat session:

> Resume from the last entry in docs/PROGRESS.md — don't start cold.
>
> Task: [TODAY'S TASK — or leave blank to pick up the next unchecked item in docs/ROADMAP.md's active phase, in order]
>
> Work only inside src/ and tests/, plus the docs/ updates below. Stay scoped to this one task — don't touch other roadmap items or files while you're in here. Stop and ask before adding any dependency not already in docs/TECH_STACK.md.
>
> Before finishing: run the tests, check the ROADMAP.md box only if this is genuinely complete and tested, and append a new dated entry to docs/PROGRESS.md.

## Phase Completion & Git Rule

- Git commit and push after each phase (and after major tested phase deliverables).
- Never mark a refactor suggestion "done" without Critic review and the human approval gate.
