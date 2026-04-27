# Rename Pass Phase D-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**Goal:** Rename 8 `*_codex_cloud_*` functions in `reviews.py` (with one-release aliases), rename 3 workspace shims, drop 6 Phase B/D-1 back-compat aliases, rename `run_acpx_prompt_fn` parameter to `run_prompt_fn`.

**Spec:** `docs/superpowers/specs/2026-04-27-rename-pass-phase-d-2-design.md`

**Worktree:** `/home/radxa/WS/hermes-relay/.claude/worktrees/rename-pass-phase-d-2` on `claude/rename-pass-phase-d-2` from main `32dee92`. Baseline 564 passing. Use `/usr/bin/python3`.

---

## Task 1: Function renames in reviews.py with aliases

**Files:**
- Modify: `workflows/code_review/reviews.py`
- Test: `tests/test_rename_pass_phase_d_2.py` (new)

- [ ] **Step 1: Rename each function definition + add alias**

In `workflows/code_review/reviews.py`, locate each `def <old_name>(...)` and rename. After each rename, add a module-level alias line:

```python
def fetch_external_review(pr_number, *, ...):
    ...
    # body unchanged, just renamed

# Phase D-2 alias — drop next release
fetch_codex_cloud_review = fetch_external_review
```

Apply to all 8:
1. `fetch_codex_cloud_review` → `fetch_external_review` (line ~774)
2. `summarize_codex_cloud_review` → `summarize_external_review` (line ~529)
3. `build_codex_cloud_thread` → `build_external_review_thread` (line ~496)
4. `should_dispatch_codex_cloud_repair_handoff` → `should_dispatch_external_review_repair_handoff` (line ~1229)
5. `codex_cloud_placeholder` → `external_review_placeholder` (line ~470)
6. `build_codex_cloud_repair_handoff_payload` → `build_external_review_repair_handoff_payload` (line ~997)
7. `record_codex_cloud_repair_handoff` → `record_external_review_repair_handoff` (line ~1025)
8. `fetch_codex_pr_body_signal` → `fetch_external_review_pr_body_signal` (line ~729)

**Important:** internal cross-references between these functions (e.g. `fetch_codex_cloud_review` calls `fetch_codex_pr_body_signal`, `summarize_codex_cloud_review`, `build_codex_cloud_thread`) must update to use the NEW names internally. Default kwargs like `build_thread_fn: Callable = build_codex_cloud_thread` become `build_thread_fn: Callable = build_external_review_thread`.

- [ ] **Step 2: Update parameter default values**

Search for default values that reference the old function names:
```bash
grep -n "= build_codex_cloud_thread\|= summarize_codex_cloud_review\|= fetch_codex_pr_body_signal" workflows/code_review/reviews.py
```
Replace with the new names.

- [ ] **Step 3: Write alias-equivalence tests**

Create `tests/test_rename_pass_phase_d_2.py`:

```python
"""Phase D-2 tests: function renames + alias drops."""
from __future__ import annotations

import pytest


def test_fetch_external_review_aliased():
    from workflows.code_review.reviews import fetch_external_review, fetch_codex_cloud_review
    assert fetch_codex_cloud_review is fetch_external_review


def test_summarize_external_review_aliased():
    from workflows.code_review.reviews import summarize_external_review, summarize_codex_cloud_review
    assert summarize_codex_cloud_review is summarize_external_review


def test_build_external_review_thread_aliased():
    from workflows.code_review.reviews import build_external_review_thread, build_codex_cloud_thread
    assert build_codex_cloud_thread is build_external_review_thread


def test_should_dispatch_external_review_repair_handoff_aliased():
    from workflows.code_review.reviews import (
        should_dispatch_external_review_repair_handoff,
        should_dispatch_codex_cloud_repair_handoff,
    )
    assert should_dispatch_codex_cloud_repair_handoff is should_dispatch_external_review_repair_handoff


def test_external_review_placeholder_aliased():
    from workflows.code_review.reviews import external_review_placeholder, codex_cloud_placeholder
    assert codex_cloud_placeholder is external_review_placeholder


def test_build_external_review_repair_handoff_payload_aliased():
    from workflows.code_review.reviews import (
        build_external_review_repair_handoff_payload,
        build_codex_cloud_repair_handoff_payload,
    )
    assert build_codex_cloud_repair_handoff_payload is build_external_review_repair_handoff_payload


def test_record_external_review_repair_handoff_aliased():
    from workflows.code_review.reviews import (
        record_external_review_repair_handoff,
        record_codex_cloud_repair_handoff,
    )
    assert record_codex_cloud_repair_handoff is record_external_review_repair_handoff


def test_fetch_external_review_pr_body_signal_aliased():
    from workflows.code_review.reviews import (
        fetch_external_review_pr_body_signal,
        fetch_codex_pr_body_signal,
    )
    assert fetch_codex_pr_body_signal is fetch_external_review_pr_body_signal
```

- [ ] **Step 4: Run target + full suite**

```bash
cd /home/radxa/WS/hermes-relay/.claude/worktrees/rename-pass-phase-d-2
/usr/bin/python3 -m pytest tests/test_rename_pass_phase_d_2.py -v
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -3
```
Expected: 8 in target, 572 total (564 + 8 new).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(reviews): rename codex_cloud functions to external_review (aliases retained)

Renames eight functions in workflows/code_review/reviews.py:
  fetch_codex_cloud_review                         -> fetch_external_review
  summarize_codex_cloud_review                     -> summarize_external_review
  build_codex_cloud_thread                         -> build_external_review_thread
  should_dispatch_codex_cloud_repair_handoff       -> should_dispatch_external_review_repair_handoff
  codex_cloud_placeholder                          -> external_review_placeholder
  build_codex_cloud_repair_handoff_payload         -> build_external_review_repair_handoff_payload
  record_codex_cloud_repair_handoff                -> record_external_review_repair_handoff
  fetch_codex_pr_body_signal                       -> fetch_external_review_pr_body_signal

Old names kept as module-level aliases for one release. Default
kwargs that pointed at the old names now point at the new ones.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Workspace shim renames + caller updates

**Files:**
- Modify: `workflows/code_review/workspace.py`

- [ ] **Step 1: Rename the three workspace shims**

In `workflows/code_review/workspace.py`:
- `_fetch_codex_cloud_review` → `_fetch_external_review`
- `_fetch_codex_pr_body_signal` → `_fetch_external_review_pr_body_signal`
- `_codex_cloud_placeholder` → `_external_review_placeholder`

Update all callers within workspace.py (the `ns.` namespace bindings, any local references). Search:
```bash
grep -n "_fetch_codex_cloud_review\|_fetch_codex_pr_body_signal\|_codex_cloud_placeholder" workflows/code_review/workspace.py
```

For external callers (orchestrator.py, reviews.py, etc.), search the codebase:
```bash
grep -rn "_fetch_codex_cloud_review\|_fetch_codex_pr_body_signal\|_codex_cloud_placeholder" workflows/code_review/
```

Update each. The shims call `ns.reviewer.fetch_review(...)` etc. — only the function/method name on the workspace side changes.

- [ ] **Step 2: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```
Expected: 572 passing. If existing tests mock the old shim names via `monkeypatch`, update those tests to use the new names.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor(workspace): rename codex_cloud shims to external_review

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Drop Phase B + D-1 back-compat aliases

**Files:**
- Modify: `workflows/code_review/prompts.py` (drop alias)
- Modify: `workflows/code_review/workspace.py` (drop codex-bot fallback)
- Modify: `workflows/code_review/actions.py` (tighten action-type check)
- Modify: `workflows/code_review/reviews.py` (tighten synthesize_repair_brief source check)
- Modify: `runtime.py`, `tools.py` (drop parity tuple)
- Modify: `workflows/code_review/migrations.py` (drop get_review legacy fallback)
- Test: `tests/test_rename_pass_phase_d_2.py` (extend)

- [ ] **Step 1: Append failing tests for dropped aliases**

```python
def test_render_codex_cloud_repair_handoff_prompt_alias_dropped():
    from workflows.code_review import prompts
    assert not hasattr(prompts, "render_codex_cloud_repair_handoff_prompt")


def test_action_dispatcher_only_accepts_run_internal_review():
    """The 'run_claude_review' alias is dropped — dispatcher matches only the new name."""
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "workflows/code_review/actions.py").read_text()
    assert "'run_internal_review'" in src or '"run_internal_review"' in src
    assert "'run_claude_review'" not in src
    assert '"run_claude_review"' not in src


def test_get_review_no_longer_falls_back_to_legacy_key():
    from workflows.code_review.migrations import get_review
    # With the legacy fallback dropped, only the new key is found.
    assert get_review({"claudeCode": {"v": 1}}, "internalReview") == {}
    assert get_review({"codexCloud": {"v": 2}}, "externalReview") == {}


def test_parity_map_no_longer_includes_run_claude_review_pair():
    from pathlib import Path
    runtime_src = (Path(__file__).resolve().parent.parent / "runtime.py").read_text()
    tools_src = (Path(__file__).resolve().parent.parent / "tools.py").read_text()
    legacy = '("run_claude_review", "request_internal_review")'
    assert legacy not in runtime_src
    assert legacy not in tools_src


def test_synthesize_repair_brief_no_longer_routes_codex_cloud_key():
    """After the alias drop, source='codexCloud' falls through to the else branch."""
    from workflows.code_review.reviews import synthesize_repair_brief
    reviews = {"codexCloud": {"threads": [{"id": "t1", "severity": "critical", "status": "open", "summary": "x"}]}}
    out = synthesize_repair_brief(reviews=reviews, local_findings=[])
    # The threads should NOT appear as externalReview-prefixed must-fix items.
    must_fix_ids = [item.get("id", "") for item in out.get("mustFix", [])]
    assert not any(i.startswith("externalReview:") for i in must_fix_ids)
    assert not any(i.startswith("codexCloud:") for i in must_fix_ids)
```

- [ ] **Step 2: Verify failures**

```bash
/usr/bin/python3 -m pytest tests/test_rename_pass_phase_d_2.py -v
```
Expected: 5 new tests fail.

- [ ] **Step 3: Drop the prompts.py alias**

In `workflows/code_review/prompts.py`, delete the line:
```python
render_codex_cloud_repair_handoff_prompt = render_external_reviewer_repair_handoff_prompt
```

If anything still imports `render_codex_cloud_repair_handoff_prompt`, update those imports.

- [ ] **Step 4: Drop the codex-bot fallback in workspace.py**

In the reviewer-build block in `workspace.py` (around the `for legacy_key, modern_key in (...)` loop), DELETE the loop that copies `codex-bot.*` keys into `ext_reviewer_cfg`. Operators must use the modern `agents.external-reviewer.{logins,clean-reactions,pending-reactions}` form.

- [ ] **Step 5: Tighten action-type dispatcher**

In `workflows/code_review/actions.py:477`, change:
```python
if action_type in ('run_internal_review', 'run_claude_review'):
```
to:
```python
if action_type == 'run_internal_review':
```

- [ ] **Step 6: Drop parity tuple**

In `runtime.py:3288`, remove the line `("run_claude_review", "request_internal_review"),` from the compatibility set. Same in `tools.py:86`.

- [ ] **Step 7: Drop get_review legacy fallback**

In `workflows/code_review/migrations.py`, simplify `get_review`:
```python
def get_review(reviews: dict | None, new_key: str) -> dict:
    """Read a review by its new key. Returns empty dict if absent."""
    return ((reviews or {}).get(new_key)) or {}
```

Drop the `_LEGACY_KEY_FOR` import inside it. The `_LEGACY_KEY_FOR` constant can stay (unused but harmless) or be removed for cleanliness.

- [ ] **Step 8: Tighten synthesize_repair_brief source check**

In `workflows/code_review/reviews.py`, find `if source in ("externalReview", "codexCloud"):` and change to `if source == "externalReview":`.

- [ ] **Step 9: Update or remove tests that exercise dropped aliases**

Search for tests that depend on the dropped aliases and update them:
```bash
grep -rn "run_claude_review\|render_codex_cloud_repair_handoff_prompt\|test_synthesize_repair_brief_accepts_legacy_codex_cloud_key" tests/
```

Specifically:
- `tests/test_rename_pass_phase_d_1.py` — `test_action_dispatcher_accepts_run_claude_review_alias` and any test asserting both literals are present in actions.py — REMOVE or convert to "alias dropped" assertion.
- `tests/test_workflows_code_review_reviews.py` — `test_synthesize_repair_brief_accepts_legacy_codex_cloud_key` — REMOVE.

- [ ] **Step 10: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```
Expected: ~575 passing (572 + 5 new alias-dropped tests, minus 2 removed legacy-alias tests).

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "refactor: drop Phase B + D-1 back-compat aliases

The one-release deprecation window has elapsed. Removed:
- prompts.render_codex_cloud_repair_handoff_prompt alias (Phase B)
- top-level codex-bot block fallback in workspace.py (Phase B)
- 'run_claude_review' action-type alias in actions.py dispatcher (D-1)
- 'codexCloud' source alias in synthesize_repair_brief (D-1)
- ('run_claude_review', 'request_internal_review') parity tuple (D-1)
- get_review legacy-key fallback in migrations.py (D-1)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Rename run_acpx_prompt_fn -> run_prompt_fn

**Files:**
- Modify: `workflows/code_review/actions.py`
- Modify: `workflows/code_review/reviews.py`
- Modify: `workflows/code_review/workspace.py` (call sites that pass kwarg)

- [ ] **Step 1: Find all references**

```bash
grep -rn "run_acpx_prompt_fn" workflows/code_review/
```

- [ ] **Step 2: Mechanical rename**

In each file, rename `run_acpx_prompt_fn` → `run_prompt_fn`:
- Function parameter declarations
- Function bodies that reference the parameter
- Call sites that pass it as a kwarg

Also rename any related helper variable / docstring mentions.

- [ ] **Step 3: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```
Expected: ~575 passing.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor: rename run_acpx_prompt_fn parameter to run_prompt_fn

Internal Python API; no operator-visible surface. Reflects the
runtime-agnostic dispatch (Phase A): the prompt-running primitive
isn't tied to acpx anymore.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Operator docs

**Files:**
- Modify: `skills/operator/SKILL.md`

- [ ] **Step 1: Append a note**

Append:

````markdown
## Deprecation cleanup (Phase D-2)

The one-release back-compat aliases introduced in Phases B / D-1 have been removed:
- `render_codex_cloud_repair_handoff_prompt` no longer importable — use `render_external_reviewer_repair_handoff_prompt`
- Top-level `codex-bot:` block in `workflow.yaml` is no longer honored — move `logins` / `clean-reactions` / `pending-reactions` into `agents.external-reviewer:`
- The `run_claude_review` action-type literal is no longer dispatched — only `run_internal_review`
- `get_review(reviews, key)` no longer falls back to legacy ledger keys — `migrate_persisted_ledger` already ran on D-1 boot
- 8 functions in `workflows/code_review/reviews.py` were renamed (`fetch_codex_cloud_review` → `fetch_external_review`, etc.); old names retained as one-release aliases
````

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "docs(operator): note Phase D-2 deprecation cleanup

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

```bash
cd /home/radxa/WS/hermes-relay/.claude/worktrees/rename-pass-phase-d-2
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```
Expected: ~575 passing.

Verify yoyopod ledger is still readable:
```bash
/usr/bin/python3 -c "
import json
from pathlib import Path
from workflows.code_review.migrations import get_review
data = json.loads(Path.home().joinpath('.hermes/workflows/yoyopod/memory/yoyopod-workflow-status.json').read_text())
reviews = data.get('reviews') or {}
print('internalReview:', bool(get_review(reviews, 'internalReview')))
print('externalReview:', bool(get_review(reviews, 'externalReview')))
"
```
