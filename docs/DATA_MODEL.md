# Data Model

This is a first-draft, implementation-ready schema. It is expected to be refined once Phase 1 ingestion code exists — record any change as a new entry in `DECISIONS.md`, don't silently drift from this file.

## Knowledge graph (NetworkX, directed multigraph)

### Node types

| Node | Key attributes |
|---|---|
| `File` | `path`, `language`, `first_seen_commit`, `last_modified_commit`, `centrality` (computed) |
| `Commit` | `sha`, `author`, `timestamp`, `message`, `parent_shas` |
| `PullRequest` | `number`, `title`, `description`, `author`, `merged_at`, `status` |
| `Issue` | `number`, `title`, `body`, `author`, `closed_at`, `status` |
| `Author` | `id` (email or platform user id), `display_name` |

### Edge types

| Edge | Direction | Attributes |
|---|---|---|
| `MODIFIES` | Commit → File | `lines_added`, `lines_removed`, `diff_summary` |
| `AUTHORED_BY` | Commit → Author | — |
| `INCLUDES` | PullRequest → Commit | — |
| `REFERENCES` | PullRequest → Issue | — |
| `CO_CHANGES_WITH` | File ↔ File (derived, weighted) | `co_change_count`, `last_co_change_commit` |
| `DEPENDS_ON` | File → File (from static import/AST analysis) | `import_kind` |

`CO_CHANGES_WITH` is an aggregated edge, recomputed on each incremental index run — not written directly during ingestion of a single commit.

## Reconciled memory

One entry per previously-generated explanation or claim, so the system can validate its own past output against new commits instead of going stale silently.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | primary key |
| `subject` | string | the file path or symbol qualname the claim is about |
| `claim_text` | string | the explanation itself |
| `source_commit_sha` | string | the evidence that grounded this claim |
| `created_at` | timestamp | |
| `last_validated_at` | timestamp | updated every reconciliation pass, even on no-op |
| `status` | enum: `active`, `stale`, `deleted` | |
| `last_action` | enum: `add`, `update`, `delete`, `no-op` | the reconciliation outcome from the most recent pass, kept for auditability |

**Reconciliation logic** (runs on every incremental index pass): for each existing entry, check whether commits touching `subject` since `last_validated_at` invalidate `claim_text`. If invalidated → `update` (regenerate and mark `active`). If `subject` no longer exists (e.g. file deleted) → `delete`. If nothing relevant changed → `no-op`. A subject with no existing entry that the agent team has now explained → `add`.

## SQLite tables

```sql
CREATE TABLE memory_entries (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    claim_text TEXT NOT NULL,
    source_commit_sha TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    last_validated_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'stale', 'deleted')),
    last_action TEXT NOT NULL CHECK (last_action IN ('add', 'update', 'delete', 'no-op'))
);

CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    caller_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    status_code INTEGER NOT NULL
);

CREATE TABLE index_state (
    repo_url TEXT PRIMARY KEY,
    last_indexed_commit_sha TEXT NOT NULL,
    last_indexed_at TIMESTAMP NOT NULL
);
```

`index_state` backs the health-check endpoint (`ARCHITECTURE.md`) and the incremental-webhook decision of how far back to re-index. `audit_log` is populated starting Phase 2, per the production-readiness requirements — the table can exist from Phase 1 so no migration is needed later.
