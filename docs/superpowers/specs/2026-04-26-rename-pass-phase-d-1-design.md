# Rename Pass Phase D-1 — Persisted-State Migration

**Status:** Approved
**Date:** 2026-04-26
**Branch:** `claude/rename-pass-phase-d-1` (worktree at `.claude/worktrees/rename-pass-phase-d-1`)
**Baseline:** main `47ae160`, 477 tests passing

## Problem

The persisted workflow ledger uses model-tied field names that leak into operator-visible state files:

```json
{
  "reviews": {
    "claudeCode": { "verdict": "PASS_CLEAN", ... },
    "codexCloud": { "status": "pending", ... }
  }
}
```

These names tie the ledger to specific providers (Claude / Codex Cloud). After Phases A–C made runtimes, reviewers, and webhooks pluggable, the ledger fields are the last operator-visible surface still hard-named to those providers. An operator who configures Greptile as their external reviewer sees `codexCloud: { status: "pending" }` written to disk on every tick — confusing and misleading.

Phase D-1 renames the two `reviews.*` keys to provider-neutral names (`internalReview`, `externalReview`) and migrates existing ledgers in-place on workspace setup. Source code adopts read-both / write-new semantics so unmigrated ledgers still work for one release. The action-type literal `run_claude_review` (transient, not persisted) renames to `run_internal_review` with the same back-compat reader.

## Scope

### In scope (this PR)
1. **JSON ledger field renames**:
   - `reviews.claudeCode` → `reviews.internalReview`
   - `reviews.codexCloud` → `reviews.externalReview`
2. **One-shot migration** in `workspace.py` on every workspace setup. Reads the persisted ledger; if old keys exist and new keys don't, rewrites the file with new keys. Idempotent. Logs a one-line message on first migration.
3. **Read-both, write-new in source code**. Helper `_get_review(reviews_dict, key)` accepts the new key and falls back to the old key for one release. All write sites use the new key only.
4. **Action-type literal** `run_claude_review` → `run_internal_review`. The action-type comes from `pick_workflow_action()` (transient, in-memory only, never persisted) — no migration needed. Just rename the literal in the dispatcher and provide a back-compat alias for one release in case any tests or fixtures use the old name.
5. **Tests**: migration round-trip, read-both fallback, write-new behavior, action-type alias.
6. **Operator docs**: `skills/operator/SKILL.md` notes the field rename + automatic migration.

### Out of scope (Phase D-2 + later)
- Other top-level ledger field renames: `claudeRepairHandoff`, `codexCloudRepairHandoff`, `codexCloudAutoResolved`, `claudeModel`, `interReviewAgentModel`, `lastClaudeVerdict`. (Migrated in D-2 with the same pattern.)
- Function-name renames in `reviews.py`: `fetch_codex_cloud_review` → `fetch_external_review`, etc. (D-2; depends on Phase B merging.)
- Internal parameter rename `run_acpx_prompt_fn` → `run_prompt_fn`. (D-2.)
- Dropping Phase B's `render_codex_cloud_repair_handoff_prompt` alias and the deprecated top-level `codex-bot:` block fallback. (D-2; depends on Phase B merging.)
- Dropping Phase A's `coder-dispatch.md` / `internal-review-strict.md` filename aliases. (Already done in Phase A — no-op for D.)

## Architecture

### Migration helper
```python
# workflows/code_review/migrations.py (new module)

REVIEW_KEY_RENAMES: dict[str, str] = {
    "claudeCode": "internalReview",
    "codexCloud": "externalReview",
}

def migrate_review_keys(ledger: dict) -> tuple[dict, bool]:
    """Rewrite legacy `reviews.<old>` keys to their new names.

    Returns (migrated_ledger, was_changed). Idempotent — calling twice on
    an already-migrated ledger returns (ledger, False).

    Migration policy: if the new key already exists, the new key wins
    (caller already migrated this slot at runtime). Old key is dropped.
    """
```

The helper runs once during workspace setup, after the ledger is loaded but before any code reads it. If migration changes anything, the file is written back with `json.dumps(..., indent=2)` matching the existing on-disk format.

### Read-both helper
```python
# workflows/code_review/migrations.py

def get_review(reviews: dict, key: str) -> dict:
    """Read a review by its new key, falling back to the legacy key.

    Defense-in-depth: even after the one-shot migration, if a stale
    process or external tool wrote an old key to the ledger, code paths
    that use this helper will still find the data.
    """
    new_value = reviews.get(key)
    if new_value is not None:
        return new_value
    legacy_key = _LEGACY_KEY_FOR.get(key)
    if legacy_key:
        return reviews.get(legacy_key) or {}
    return {}

_LEGACY_KEY_FOR = {v: k for k, v in REVIEW_KEY_RENAMES.items()}
```

### Source-code rename strategy

**Read sites** (~25 references to `claudeCode` + ~20 to `codexCloud`): replace `reviews.get("claudeCode")` and `(reviews or {}).get("claudeCode")` with `get_review(reviews or {}, "internalReview")`. Same for `codexCloud` → `externalReview`. Pattern is mechanical, but volume requires care.

**Write sites** (a handful in `actions.py` and `reviews.py`): replace the assignment target. E.g. `ledger['reviews']['claudeCode'] = ...` becomes `ledger['reviews']['internalReview'] = ...`.

**Mixed code paths** that read AND write to the same dict in one tick: ensure the new key is written, the old key is removed (so a process that crashes mid-tick doesn't leave both keys alive).

### Action-type literal rename

Source: `actions.py:473`:
```python
if action_type == 'run_claude_review':
    return run_inter_review_agent_review_action(...)
```

Becomes:
```python
if action_type in ('run_internal_review', 'run_claude_review'):  # back-compat alias
    return run_inter_review_agent_review_action(...)
```

Producers (`pick_workflow_action()` in `workflow.py`) emit only `run_internal_review` after this PR. The alias drops in Phase D-2.

### Migration write-back semantics

The migration runs in `workspace.py` at workspace bootstrap. The ledger path is already known (`ledger_path` variable around line 583). Pseudocode:

```python
# In workspace.py, after ledger_path is determined but before any reads
from workflows.code_review.migrations import migrate_persisted_ledger

migrate_persisted_ledger(ledger_path)  # idempotent; logs once if it changed something
```

`migrate_persisted_ledger` opens the file, runs `migrate_review_keys`, and writes back atomically (temp file + rename) only if anything changed. If the file doesn't exist, it's a no-op.

## Migration path for live `yoyopod` workspace

Live ledger at `~/.hermes/workflows/yoyopod/memory/yoyopod-workflow-status.json` currently has:
```json
{
  "reviews": {
    "claudeCode": { ... },
    "codexCloud": { ... },
    "rockClaw": { ... }
  }
}
```

After this PR's first workspace setup:
- File rewritten to:
  ```json
  {
    "reviews": {
      "internalReview": { ... },
      "externalReview": { ... },
      "rockClaw": { ... }    // unchanged — not in REVIEW_KEY_RENAMES
    }
  }
  ```
- Subsequent workspace setups: no-op (idempotent).
- If any other process (cron, script) writes `claudeCode` after migration, the read-both helper still finds it. Next workspace setup re-runs migration and re-rewrites the file.

## Tests

New file `tests/test_rename_pass_phase_d_1.py`:

**Migration helper:**
- `test_migrate_review_keys_renames_legacy_keys` — `claudeCode` + `codexCloud` → new names; `was_changed=True`.
- `test_migrate_review_keys_idempotent` — second call returns `was_changed=False`.
- `test_migrate_review_keys_new_key_wins` — both old + new present ⇒ new wins, old dropped.
- `test_migrate_review_keys_passes_through_unknown_keys` — `rockClaw` and other keys preserved.
- `test_migrate_review_keys_handles_missing_reviews_block` — ledger without `reviews:` key returns unchanged.

**Read-both helper:**
- `test_get_review_returns_new_when_present`
- `test_get_review_falls_back_to_legacy_when_only_legacy_present`
- `test_get_review_prefers_new_when_both_present`
- `test_get_review_returns_empty_dict_for_unknown_key`

**Persisted-ledger migration:**
- `test_migrate_persisted_ledger_rewrites_file_atomically` (uses tmp file)
- `test_migrate_persisted_ledger_noop_on_already_migrated` (no file rewrite if already done)
- `test_migrate_persisted_ledger_handles_missing_file` (silently)
- `test_migrate_persisted_ledger_preserves_indent_2_format`

**Action-type alias:**
- `test_action_dispatcher_accepts_run_internal_review`
- `test_action_dispatcher_accepts_run_claude_review_alias`

**Live-yoyopod regression:**
- `test_existing_yoyopod_ledger_migrates_cleanly` — copy the live ledger to tmp, run migration, assert all keys round-trip and the read-both helper still works on `rockClaw` and other untouched keys.

Existing 477 tests stay green. Target: 477 + 14 new = 491 passing.

## Risks

1. **In-flight crash during migration** — if the engine crashes between reading the old ledger and writing the new one, atomic temp-file + rename ensures the file is either fully old or fully new, never half-renamed. Standard `os.replace()` semantics on POSIX.

2. **Concurrent writers** — if cron jobs or other processes are writing the ledger while migration runs, the temp+rename pattern means migration can clobber a concurrent write. **Mitigation:** the live YoYoPod workspace is currently idle (`no-active-lane`). Run migration during a quiet window. **Documentation:** the operator notes that `daedalus migrate-state` (future CLI) is the safer manual path; automatic-on-bootstrap is the current default since the workspace is idle anyway.

3. **Code paths that bypass `get_review` and read `claudeCode` directly** — these break only after migration runs. Risk: ~25 read sites; if any are missed, lane state appears empty after migration. **Mitigation:** the test suite exercises every read site through fixture data that uses ONLY the new keys. If any code path still hardcodes the old key, the corresponding test fails.

## Open questions

None — locked in:
- Read-both / write-new for one release.
- Migration runs automatically on workspace bootstrap (live workspace is idle so race risk is minimal).
- Other field renames stay in Phase D-2.
