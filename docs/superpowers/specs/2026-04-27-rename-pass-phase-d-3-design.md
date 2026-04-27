# Rename Pass Phase D-3 — Top-Level Ledger Field Renames

**Status:** Approved
**Date:** 2026-04-27
**Branch:** `claude/rename-pass-phase-d-3` from main `13d5723`. Baseline 572 tests passing.

## Problem

Phase D-1 migrated `reviews.claudeCode` / `reviews.codexCloud` to provider-neutral names. Five top-level ledger fields still carry provider-tied names — operator-visible in `yoyopod-workflow-status.json` on every tick:

```json
{
  "claudeRepairHandoff": {...},
  "codexCloudRepairHandoff": {...},
  "codexCloudAutoResolved": {...},
  "claudeModel": "claude-sonnet-4",
  "interReviewAgentModel": "claude-sonnet-4",
  "lastClaudeVerdict": "PASS_CLEAN"
}
```

Plus four workspace-internal `_codex_cloud_*` shim names still leak the provider into the workspace namespace.

Phase D-3 renames the top-level fields with one-shot migration (parallel pattern to D-1), renames the workspace shims, and KEEPS the D-2 function-name aliases for one more release (drop deferred to D-4).

## Scope

### In scope (this PR)
1. **Top-level ledger field renames** with migration:
   - `claudeRepairHandoff` → `internalReviewRepairHandoff`
   - `codexCloudRepairHandoff` → `externalReviewRepairHandoff`
   - `codexCloudAutoResolved` → `externalReviewAutoResolved`
   - `claudeModel` → drop entirely (canonicalize on `internalReviewerModel`)
   - `interReviewAgentModel` → `internalReviewerModel`
   - `lastClaudeVerdict` → `lastInternalVerdict`

2. **Migration extension** in `workflows/code_review/migrations.py`:
   - New `LEDGER_KEY_RENAMES: dict[str, str]` constant for top-level keys
   - New `migrate_top_level_keys(ledger) → (ledger, was_changed)` helper (parallel to `migrate_review_keys`)
   - `migrate_persisted_ledger(path)` runs both helpers

3. **Read-both / write-new in source** for one release:
   - New `get_ledger_field(ledger, new_key)` helper (parallel to `get_review`) with legacy fallback
   - All read sites use `get_ledger_field(ledger, "internalReviewRepairHandoff")` etc.
   - All write sites write the new key only AND drop the legacy key (parallel to D-1 pattern)

4. **Workspace shim renames** in `workflows/code_review/workspace.py`:
   - `should_dispatch_codex_cloud_repair_handoff` → `should_dispatch_external_review_repair_handoff`
   - `build_codex_cloud_repair_handoff_payload` → `build_external_review_repair_handoff_payload`
   - `record_codex_cloud_repair_handoff` → `record_external_review_repair_handoff`
   - `_render_codex_cloud_repair_handoff_prompt` → `_render_external_review_repair_handoff_prompt`

5. **Tests**: migration + read-both + write-new round-trip; live yoyopod ledger smoke test.

6. **Operator docs**: note in `skills/operator/SKILL.md`.

### Explicitly KEPT this release (drop in D-4 or later)
- D-2 function aliases in `reviews.py` (`fetch_codex_cloud_review = fetch_external_review`, etc.) — operators / external tooling may still reference them.

### Out of scope
- Cosmetic variable-name renames (`claude_review`, `codex_cloud_review`, etc.) — pure local-scope cleanup, not operator-visible.
- The per-thread `"source": "codexCloud"` field inside review threads — different field, broader migration concern.

## Architecture

### Migration extension
```python
# workflows/code_review/migrations.py — added

LEDGER_KEY_RENAMES: dict[str, str] = {
    "claudeRepairHandoff": "internalReviewRepairHandoff",
    "codexCloudRepairHandoff": "externalReviewRepairHandoff",
    "codexCloudAutoResolved": "externalReviewAutoResolved",
    "interReviewAgentModel": "internalReviewerModel",
    "lastClaudeVerdict": "lastInternalVerdict",
    # claudeModel: dropped entirely (no rename target — interReviewAgentModel is the canonical input)
}

_LEGACY_LEDGER_KEY_FOR: dict[str, str] = {v: k for k, v in LEDGER_KEY_RENAMES.items()}


def migrate_top_level_keys(ledger: dict) -> tuple[dict, bool]:
    """Rewrite top-level ledger keys per LEDGER_KEY_RENAMES.

    `claudeModel` is special — it's dropped entirely (not migrated to a new
    target) since `interReviewAgentModel` (in this PR migrated to
    `internalReviewerModel`) carries the same value. If both exist the
    renamed-from value wins.
    """
    changed = False
    # Rename pass
    for old, new in LEDGER_KEY_RENAMES.items():
        if old in ledger:
            if new not in ledger:
                ledger[new] = ledger[old]
            del ledger[old]
            changed = True
    # Drop claudeModel (canonical is now internalReviewerModel)
    if "claudeModel" in ledger:
        del ledger["claudeModel"]
        changed = True
    return ledger, changed


def get_ledger_field(ledger: dict | None, new_key: str) -> Any:
    """Read a top-level ledger field with legacy-key fallback for one release."""
    ledger = ledger or {}
    if new_key in ledger:
        return ledger[new_key]
    legacy = _LEGACY_LEDGER_KEY_FOR.get(new_key)
    if legacy and legacy in ledger:
        return ledger[legacy]
    return None
```

`migrate_persisted_ledger` runs both helpers in sequence:
```python
def migrate_persisted_ledger(path):
    ...
    ledger, c1 = migrate_review_keys(ledger)
    ledger, c2 = migrate_top_level_keys(ledger)
    if not (c1 or c2):
        return False
    ...write...
```

### Source-code rename strategy
Mechanical. ~21 production references identified:
- `actions.py` — 8 writes (across 3 functions, lines 381-450) — write only `internalReviewerModel`, pop legacy keys.
- `orchestrator.py` — 2 writes (lines 495, 513) — `codexCloudAutoResolved` → `externalReviewAutoResolved`.
- `reviews.py` — 2 writes (lines 1390, 1451) — `claudeRepairHandoff` / `codexCloudRepairHandoff` → new names.
- `status.py` — 4 reads + 2 writes (lines 437, 441-442, 546-547, 927) — switch to `get_ledger_field` + write new key.
- `workspace.py` — 3 reads (lines 126, 502, 504) — derive `internalReviewerModel` from new field.

### Workspace shim renames
Pure rename — workspace tests assert the shim names. Tests need updating to the new names.

## Migration path for live `yoyopod` workspace

Live ledger has all six legacy keys. After this PR boots:
- `migrate_persisted_ledger` rewrites the file in place
- `claudeModel` dropped (its value lives in `internalReviewerModel` after rename)
- All read paths via `get_ledger_field` find data via legacy fallback if migration hasn't run yet
- `migrate_persisted_ledger` runs at workspace bootstrap (already wired in D-1) — both helpers fire

## Tests

New test sections appended to `tests/test_rename_pass_phase_d_1.py` (or new file `tests/test_rename_pass_phase_d_3.py`):

- `test_migrate_top_level_keys_renames_legacy_keys` — all five keys migrated.
- `test_migrate_top_level_keys_drops_claudeModel` — `claudeModel` removed without target.
- `test_migrate_top_level_keys_idempotent` — second call returns `was_changed=False`.
- `test_migrate_top_level_keys_new_key_wins_when_both_present`
- `test_migrate_persisted_ledger_runs_both_migrations` — combined behavior.
- `test_get_ledger_field_returns_new_when_present`
- `test_get_ledger_field_falls_back_to_legacy_when_only_legacy_present`
- `test_get_ledger_field_returns_none_for_unknown_key`
- `test_existing_yoyopod_ledger_top_level_migration` — live ledger smoke test.

Plus alias-rename tests for the workspace shims (just structural — name exists, name old gone).

Existing tests may need updating where they assert on legacy field names. Target: 572 + ~10 = ~582 passing.

## Risks

1. **`claudeModel` drop changes status.py output shape** — `print_status` etc. emit `"claudeModel": ...`. After migration, code reading `ledger["claudeModel"]` returns None. Fix: status output uses `internalReviewerModel` (new name). External tooling that parsed `claudeModel` from status JSON breaks. Acceptable for one operator one repo.

2. **Test fixtures using legacy keys** — pre-existing tests likely use `interReviewAgentModel`/`claudeModel` literals. They'll continue working via the read-both fallback in `get_ledger_field`, but should be updated to the new keys for clarity.

3. **No regression risk on the migration itself** — pattern proven in D-1.

## Open questions

None.
