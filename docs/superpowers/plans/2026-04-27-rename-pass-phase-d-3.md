# Rename Pass Phase D-3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Migrate top-level ledger keys (`claudeRepairHandoff`/`codexCloudRepairHandoff`/`codexCloudAutoResolved`/`interReviewAgentModel`/`lastClaudeVerdict`) to provider-neutral names; drop `claudeModel`; rename four `_codex_cloud_*` workspace shims; extend the D-1 migration mechanism to top-level fields.

**Spec:** `docs/superpowers/specs/2026-04-27-rename-pass-phase-d-3-design.md`

**Worktree:** `/home/radxa/WS/hermes-relay/.claude/worktrees/rename-pass-phase-d-3` on `claude/rename-pass-phase-d-3` from main `13d5723`. Baseline 572 passing. Use `/usr/bin/python3`.

---

## Task 1: Migrations module extension

**Files:**
- Modify: `workflows/code_review/migrations.py`
- Test: `tests/test_rename_pass_phase_d_3.py` (new)

- [ ] **Step 1: Write failing tests**

Create `tests/test_rename_pass_phase_d_3.py`:

```python
"""Phase D-3 tests: top-level ledger field migrations."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


def test_migrate_top_level_keys_renames_legacy():
    from workflows.code_review.migrations import migrate_top_level_keys

    ledger = {
        "claudeRepairHandoff": {"v": 1},
        "codexCloudRepairHandoff": {"v": 2},
        "codexCloudAutoResolved": {"v": 3},
        "interReviewAgentModel": "claude-sonnet-4",
        "lastClaudeVerdict": "PASS_CLEAN",
    }
    out, changed = migrate_top_level_keys(ledger)
    assert changed is True
    assert out["internalReviewRepairHandoff"] == {"v": 1}
    assert out["externalReviewRepairHandoff"] == {"v": 2}
    assert out["externalReviewAutoResolved"] == {"v": 3}
    assert out["internalReviewerModel"] == "claude-sonnet-4"
    assert out["lastInternalVerdict"] == "PASS_CLEAN"
    for old in (
        "claudeRepairHandoff", "codexCloudRepairHandoff",
        "codexCloudAutoResolved", "interReviewAgentModel",
        "lastClaudeVerdict",
    ):
        assert old not in out


def test_migrate_top_level_keys_drops_claude_model():
    from workflows.code_review.migrations import migrate_top_level_keys

    ledger = {"claudeModel": "claude-sonnet-4"}
    out, changed = migrate_top_level_keys(ledger)
    assert changed is True
    assert "claudeModel" not in out


def test_migrate_top_level_keys_idempotent():
    from workflows.code_review.migrations import migrate_top_level_keys

    ledger = {
        "internalReviewRepairHandoff": {"v": 1},
        "internalReviewerModel": "x",
    }
    out, changed = migrate_top_level_keys(ledger)
    assert changed is False


def test_migrate_top_level_keys_new_key_wins():
    from workflows.code_review.migrations import migrate_top_level_keys

    ledger = {
        "interReviewAgentModel": "old",
        "internalReviewerModel": "new",
    }
    out, changed = migrate_top_level_keys(ledger)
    assert changed is True
    assert out["internalReviewerModel"] == "new"
    assert "interReviewAgentModel" not in out


def test_migrate_persisted_ledger_runs_both_migrations(tmp_path):
    from workflows.code_review.migrations import migrate_persisted_ledger

    p = tmp_path / "l.json"
    p.write_text(json.dumps({
        "reviews": {"claudeCode": {"v": 1}},
        "claudeRepairHandoff": {"v": 2},
        "claudeModel": "claude-sonnet-4",
    }, indent=2))
    migrate_persisted_ledger(p)
    out = json.loads(p.read_text())
    assert out["reviews"]["internalReview"] == {"v": 1}
    assert out["internalReviewRepairHandoff"] == {"v": 2}
    assert "claudeModel" not in out


def test_get_ledger_field_returns_new_when_present():
    from workflows.code_review.migrations import get_ledger_field
    assert get_ledger_field({"internalReviewerModel": "x"}, "internalReviewerModel") == "x"


def test_get_ledger_field_falls_back_to_legacy():
    from workflows.code_review.migrations import get_ledger_field
    assert get_ledger_field({"interReviewAgentModel": "x"}, "internalReviewerModel") == "x"
    assert get_ledger_field({"claudeRepairHandoff": {"v": 1}}, "internalReviewRepairHandoff") == {"v": 1}


def test_get_ledger_field_returns_none_for_unknown_key():
    from workflows.code_review.migrations import get_ledger_field
    assert get_ledger_field({"x": 1}, "made-up") is None


def test_get_ledger_field_handles_none_ledger():
    from workflows.code_review.migrations import get_ledger_field
    assert get_ledger_field(None, "internalReviewerModel") is None


def test_existing_yoyopod_ledger_top_level_migration(tmp_path):
    from workflows.code_review.migrations import migrate_persisted_ledger
    src = Path(os.path.expanduser("~/.hermes/workflows/yoyopod/memory/yoyopod-workflow-status.json"))
    if not src.exists():
        pytest.skip("yoyopod ledger not present")
    dst = tmp_path / "l.json"
    dst.write_text(src.read_text())
    migrate_persisted_ledger(dst)
    out = json.loads(dst.read_text())
    # All legacy top-level keys should be gone
    for old in (
        "claudeRepairHandoff", "codexCloudRepairHandoff",
        "codexCloudAutoResolved", "interReviewAgentModel",
        "lastClaudeVerdict", "claudeModel",
    ):
        assert old not in out, f"{old} should have been migrated"
```

- [ ] **Step 2: Verify failure**

```bash
cd /home/radxa/WS/hermes-relay/.claude/worktrees/rename-pass-phase-d-3
/usr/bin/python3 -m pytest tests/test_rename_pass_phase_d_3.py -v
```

Expected: FAIL — `migrate_top_level_keys` doesn't exist.

- [ ] **Step 3: Extend `migrations.py`**

Append to `workflows/code_review/migrations.py`:

```python
LEDGER_KEY_RENAMES: dict[str, str] = {
    "claudeRepairHandoff": "internalReviewRepairHandoff",
    "codexCloudRepairHandoff": "externalReviewRepairHandoff",
    "codexCloudAutoResolved": "externalReviewAutoResolved",
    "interReviewAgentModel": "internalReviewerModel",
    "lastClaudeVerdict": "lastInternalVerdict",
}

_LEGACY_LEDGER_KEY_FOR: dict[str, str] = {v: k for k, v in LEDGER_KEY_RENAMES.items()}

# Top-level keys that are dropped entirely (no rename target).
# claudeModel is canonicalized as internalReviewerModel via the
# interReviewAgentModel migration; the explicit claudeModel mirror
# from the previous migration round is no longer needed.
LEDGER_KEYS_TO_DROP: set[str] = {"claudeModel"}


def migrate_top_level_keys(ledger: dict) -> tuple[dict, bool]:
    """Rewrite legacy top-level ledger keys per LEDGER_KEY_RENAMES.

    If both old and new keys are present, the new value wins and the
    old key is dropped. Keys in LEDGER_KEYS_TO_DROP are removed entirely.
    Returns (ledger, was_changed). Mutates in place.
    """
    changed = False
    for old, new in LEDGER_KEY_RENAMES.items():
        if old in ledger:
            if new not in ledger:
                ledger[new] = ledger[old]
            del ledger[old]
            changed = True
    for k in LEDGER_KEYS_TO_DROP:
        if k in ledger:
            del ledger[k]
            changed = True
    return ledger, changed


def get_ledger_field(ledger: dict | None, new_key: str):
    """Read a top-level ledger field by its new key; fall back to legacy."""
    ledger = ledger or {}
    if new_key in ledger:
        return ledger[new_key]
    legacy = _LEGACY_LEDGER_KEY_FOR.get(new_key)
    if legacy and legacy in ledger:
        return ledger[legacy]
    return None
```

- [ ] **Step 4: Update `migrate_persisted_ledger` to run both migrations**

Find the existing `migrate_persisted_ledger` body. After the `_, changed = migrate_review_keys(ledger)` line, add a call to `migrate_top_level_keys` and OR the `changed` flag:

```python
    _, c1 = migrate_review_keys(ledger)
    _, c2 = migrate_top_level_keys(ledger)
    if not (c1 or c2):
        return False
```

(Replace the original `if not changed: return False` line.)

- [ ] **Step 5: Run target + full**

```bash
/usr/bin/python3 -m pytest tests/test_rename_pass_phase_d_3.py -v
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -3
```

Expected: 10 in target, 582 total.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(migrations): add top-level ledger key migration

Extends migrate_persisted_ledger with migrate_top_level_keys and
get_ledger_field helpers (parallel to the reviews-key migration).
Renames claudeRepairHandoff/codexCloudRepairHandoff/codexCloudAutoResolved/
interReviewAgentModel/lastClaudeVerdict to provider-neutral names;
drops claudeModel entirely (canonicalized as internalReviewerModel).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Read sites via get_ledger_field

**Files:**
- Modify: `workflows/code_review/status.py` (lines ~437, 441, 442, 927)
- Modify: `workflows/code_review/workspace.py` (lines ~502, 504)

- [ ] **Step 1: Replace read sites**

`status.py:437`: `"codexCloudAutoResolved": ledger.get("codexCloudAutoResolved"),` → `"externalReviewAutoResolved": get_ledger_field(ledger, "externalReviewAutoResolved"),`. Update the OUTPUT key to also be the new name (status output is operator-visible — this is part of the rename).

`status.py:441-442`: the fallback chain currently emits both `claudeModel` and `interReviewAgentModel`. Replace with single emission `"internalReviewerModel"`:
```python
"internalReviewerModel": (
    get_ledger_field(ledger, "internalReviewerModel")
    or (get_review(reviews, "internalReview").get("model"))
    or inter_review_agent_model
),
```

Drop the `claudeModel` and `interReviewAgentModel` keys from the status dict.

`status.py:927`: `"lastClaudeVerdict": ((get_review(reviews, "internalReview")).get("verdict")) or ((existing.get("review") or {}).get("lastClaudeVerdict")),` → `"lastInternalVerdict": ((get_review(reviews, "internalReview")).get("verdict")) or ((existing.get("review") or {}).get("lastInternalVerdict")),`. Note both the dict key AND the inner read.

`workspace.py:502, 504`: The fallback `review_policy.get("interReviewAgentModel") or ... or review_policy.get("claudeModel", ...)` should use:
```python
review_policy.get("internalReviewerModel")
or review_policy.get("interReviewAgentModel")  # legacy fallback for one release
or "claude-sonnet-4-6"
```

(Drop the `claudeModel` fallback — it was the original-original name; if a workspace still has it, the migration will rewrite it on bootstrap.)

`workspace.py:126`: `"interReviewAgentModel": int_reviewer.get("model", "claude-sonnet-4-6"),` → `"internalReviewerModel": int_reviewer.get("model", "claude-sonnet-4-6"),`. Note this is in a config dict construction — the output key changes too.

Add `from workflows.code_review.migrations import get_ledger_field` import to status.py and workspace.py at top with other migration imports.

- [ ] **Step 2: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```

Expected: 582 passing. Existing tests that asserted on `claudeModel` / `interReviewAgentModel` / `codexCloudAutoResolved` / `lastClaudeVerdict` keys in status output will fail — these need to be updated to the new key names. (See Task 3 Step 6.)

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: read top-level ledger fields via get_ledger_field

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Write sites + drop legacy keys

**Files:**
- Modify: `workflows/code_review/actions.py` (lines ~381-382, 417-418, 440-441, 449-450)
- Modify: `workflows/code_review/orchestrator.py` (lines ~495, 513)
- Modify: `workflows/code_review/reviews.py` (lines ~1390, 1451)
- Modify: `workflows/code_review/status.py` (lines ~546-547)

- [ ] **Step 1: Replace write sites**

`actions.py:381-382, 417-418, 440-441` — three duplicate write blocks of the form:
```python
ledger['claudeModel'] = inter_review_agent_model
ledger['interReviewAgentModel'] = inter_review_agent_model
```
Replace each pair with:
```python
ledger['internalReviewerModel'] = inter_review_agent_model
ledger.pop('claudeModel', None)
ledger.pop('interReviewAgentModel', None)
```

`actions.py:449-450` — dict-literal construction in a `prePublishGate` payload:
```python
'claudeModel': inter_review_agent_model,
'interReviewAgentModel': inter_review_agent_model,
```
Replace with:
```python
'internalReviewerModel': inter_review_agent_model,
```

`orchestrator.py:495, 513` — `ledger["codexCloudAutoResolved"] = resolution_event` → `ledger["externalReviewAutoResolved"] = resolution_event` plus `ledger.pop("codexCloudAutoResolved", None)`.

`reviews.py:1390` — `ledger["claudeRepairHandoff"] = repair_payload` → `ledger["internalReviewRepairHandoff"] = repair_payload; ledger.pop("claudeRepairHandoff", None)`.

`reviews.py:1451` — same pattern with `codexCloudRepairHandoff` → `externalReviewRepairHandoff`.

`status.py:546-547`:
```python
ledger["claudeModel"] = inter_review_agent_model
ledger["interReviewAgentModel"] = inter_review_agent_model
```
Replace with:
```python
ledger["internalReviewerModel"] = inter_review_agent_model
ledger.pop("claudeModel", None)
ledger.pop("interReviewAgentModel", None)
```

- [ ] **Step 2: Sanity grep**

```bash
grep -rn '"claudeRepairHandoff"\|"codexCloudRepairHandoff"\|"codexCloudAutoResolved"\|"interReviewAgentModel"\|"claudeModel"\|"lastClaudeVerdict"' workflows/code_review/*.py | grep -v test_ | grep -v migrations.py
```

Expected: only `pop(..., None)` cleanup calls and string-literal references in docstrings/comments. No live writes to legacy keys.

- [ ] **Step 3: Update tests that asserted on legacy keys**

Run `/usr/bin/python3 -m pytest tests/ 2>&1 | tail -30` and inspect failures. Test fixtures or assertions referencing the legacy keys need updating to new keys. Likely candidates:
- `tests/test_workflows_code_review_adapter_status.py` — status output keys
- `tests/test_workflows_code_review_actions.py` — ledger writes
- `tests/test_workflows_code_review_workflow.py` — derive_next_action context

For each failing test, update the literal key name in the assertion / fixture from the legacy form to the new form.

- [ ] **Step 4: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```

Expected: 582 passing.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: write top-level ledger fields via new keys (drop legacy)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Workspace shim renames

**Files:**
- Modify: `workflows/code_review/workspace.py` (lines ~1565, 1576, 1587, 1596)
- Test: `tests/test_workflows_code_review_workspace.py` (any test asserting on shim names)

- [ ] **Step 1: Rename four workspace shims**

In `workflows/code_review/workspace.py`:
- `should_dispatch_codex_cloud_repair_handoff` → `should_dispatch_external_review_repair_handoff` (line 1565)
- `build_codex_cloud_repair_handoff_payload` → `build_external_review_repair_handoff_payload` (line 1576)
- `record_codex_cloud_repair_handoff` → `record_external_review_repair_handoff` (line 1587)
- `_render_codex_cloud_repair_handoff_prompt` → `_render_external_review_repair_handoff_prompt` (line 1596)

Each shim's body delegates to the renamed function in `reviews.py` (which has D-2 aliases — call the new name). Update calls inside the shim body.

Search for callers of these shim names elsewhere in workspace.py + the broader codebase:
```bash
grep -rn "should_dispatch_codex_cloud_repair_handoff\|build_codex_cloud_repair_handoff_payload\|record_codex_cloud_repair_handoff\|_render_codex_cloud_repair_handoff_prompt" workflows/ tests/
```

Update each.

- [ ] **Step 2: Update tests**

`tests/test_workflows_code_review_workspace.py:216` (or wherever) likely asserts these shim names exist. Update to assert the new names. Search:
```bash
grep -rn "should_dispatch_codex_cloud_repair_handoff\|build_codex_cloud_repair_handoff_payload\|record_codex_cloud_repair_handoff\|_render_codex_cloud_repair_handoff_prompt" tests/
```

- [ ] **Step 3: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```

Expected: 582 passing.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(workspace): rename codex_cloud repair-handoff shims to external_review

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Operator docs

**Files:**
- Modify: `skills/operator/SKILL.md`

- [ ] **Step 1: Append a section**

Append to `skills/operator/SKILL.md`:

````markdown
## Persisted-state migration round 2 (Phase D-3)

Five additional top-level ledger fields renamed for provider neutrality:
- `claudeRepairHandoff` → `internalReviewRepairHandoff`
- `codexCloudRepairHandoff` → `externalReviewRepairHandoff`
- `codexCloudAutoResolved` → `externalReviewAutoResolved`
- `interReviewAgentModel` → `internalReviewerModel`
- `lastClaudeVerdict` → `lastInternalVerdict`

Plus `claudeModel` is dropped entirely — its value lives in `internalReviewerModel` after the rename.

**Migration is automatic** on workspace bootstrap (atomic temp+rename, idempotent), same mechanism as Phase D-1.

**Read-both / write-new** for one release via the new `get_ledger_field(ledger, new_key)` helper.

**Status output keys also renamed** — external tooling that parsed `claudeModel` / `interReviewAgentModel` / `codexCloudAutoResolved` / `lastClaudeVerdict` from `yoyopod-workflow-status.json` should switch to the new names.

**Workspace internals.** Four `_codex_cloud_repair_handoff_*` shims in `workflows/code_review/workspace.py` renamed to `_external_review_repair_handoff_*`. Workspace-internal API; affects subagent test fixtures only.
````

- [ ] **Step 2: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -3
```

Expected: 582 passing.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs(operator): note Phase D-3 top-level ledger field migration

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

```bash
cd /home/radxa/WS/hermes-relay/.claude/worktrees/rename-pass-phase-d-3
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```

Expected: 582 passing.

Live yoyopod ledger smoke test:
```bash
/usr/bin/python3 -c "
import json, shutil, tempfile
from pathlib import Path
from workflows.code_review.migrations import migrate_persisted_ledger, get_ledger_field

src = Path.home() / '.hermes/workflows/yoyopod/memory/yoyopod-workflow-status.json'
with tempfile.TemporaryDirectory() as td:
    dst = Path(td) / 'l.json'
    shutil.copy2(src, dst)
    changed = migrate_persisted_ledger(dst)
    out = json.loads(dst.read_text())
    for old in ('claudeRepairHandoff', 'codexCloudRepairHandoff', 'codexCloudAutoResolved',
                'interReviewAgentModel', 'lastClaudeVerdict', 'claudeModel'):
        assert old not in out, f'{old} still present'
    print('migration:', 'rewrote' if changed else 'no-op')
    print('internalReviewerModel:', out.get('internalReviewerModel'))
"
```
