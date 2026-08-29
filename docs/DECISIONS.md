# Architecture Decision Log

Append-only. Never edit or delete a past entry — if a decision changes, add a new entry that supersedes it and say so explicitly. Newest entries at the bottom.

---

### ADR 0001 — LangGraph over raw LangChain chains for agent orchestration
**Date:** 2026-08-27 · **Status:** Accepted

Agent routing needs explicit state and a real interrupt point for the human review gate on the Refactor path. A linear chain can't represent "pause here until a human responds." LangGraph's state-graph model can.

---

### ADR 0002 — NetworkX for the knowledge graph, not a dedicated graph database
**Date:** 2026-08-27 · **Status:** Accepted

At Phase 1–2 scale (single repositories, not a multi-tenant graph), an in-process graph avoids standing up and operating a separate database. A migration path to a dedicated graph database is kept open and should be revisited if scale or multi-repo querying requires it.

---

### ADR 0003 — ChromaDB + sentence-embeddings for retrieval
**Date:** 2026-08-27 · **Status:** Accepted

Embedded, no separate service to run, and sufficient for hybrid vector + keyword retrieval over commit messages, PR text, and docstrings at this scale.

---

### ADR 0004 — FastAPI for the REST layer
**Date:** 2026-08-27 · **Status:** Accepted

Async support, automatic OpenAPI documentation, and native Pydantic integration match a codebase that validates every agent response against a schema.

---

### ADR 0005 — Streamlit for the dashboard, deferred to Phase 3
**Date:** 2026-08-27 · **Status:** Accepted

Keeps the entire stack in Python — no separate frontend toolchain to build and maintain. Adequate for an internal/demo-grade graph-visualization surface. Not required for Phase 1 or Phase 2 to be considered complete.

---

### ADR 0006 — Mandatory human approval gate for every refactor suggestion
**Date:** 2026-08-27 · **Status:** Accepted — non-negotiable

No refactor suggestion may ever reach a "ready to apply" state without (a) surviving Critic review and (b) a separate human approval action. This is a safety property of the product, not an implementation detail — it must hold starting Phase 1, not deferred to "production hardening." See `ARCHITECTURE.md`.

---

### ADR 0007 — SQLite for memory and audit storage
**Date:** 2026-08-27 · **Status:** Accepted

Zero-ops, sufficient for Phase 1–2 scale, no server to run or credentials to manage. Revisit only if concurrent-write volume becomes a real bottleneck.

---

### ADR 0008 — Public repositories only, read-only access, for the initial release
**Date:** 2026-08-27 · **Status:** Accepted

Avoids handling access control and sensitive private-repository data before the system has proven itself. Private-repository support is explicitly out of scope until a separate decision is recorded here.
