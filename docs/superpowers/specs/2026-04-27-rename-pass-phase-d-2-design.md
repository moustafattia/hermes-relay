# Rename Pass Phase D-2 — Function Renames + Drop Aliases

**Status:** Approved
**Date:** 2026-04-27
**Branch:** `claude/rename-pass-phase-d-2` from main `32dee92`. Baseline 564 tests passing.

## Problem

Phases A–C made runtimes / reviewers / webhooks pluggable. Phase D-1 migrated the persisted ledger keys (`reviews.claudeCode` → `reviews.internalReview`, `reviews.codexCloud` → `reviews.externalReview`) with one-release back-compat aliases. The aliases have served their purpose — live ledgers migrated on Phase D-1 boot. D-2 drops the aliases and finishes the cleanup: function names in `reviews.py` and workspace shims still carry `codex_cloud_*` / `claudeCode` history; the internal `run_acpx_prompt_fn` parameter still names the original runtime in its signature.

## Scope

### In scope (this PR)
1. **Function renames** in `workflows/code_review/reviews.py` (with new one-release aliases):
   - `fetch_codex_cloud_review` → `fetch_external_review`
   - `summarize_codex_cloud_review` → `summarize_external_review`
   - `build_codex_cloud_thread` → `build_external_review_thread`
   - `should_dispatch_codex_cloud_repair_handoff` → `should_dispatch_external_review_repair_handoff`
   - `codex_cloud_placeholder` → `external_review_placeholder`
   - `build_codex_cloud_repair_handoff_payload` → `build_external_review_repair_handoff_payload`
   - `record_codex_cloud_repair_handoff` → `record_external_review_repair_handoff`
   - `fetch_codex_pr_body_signal` → `fetch_external_review_pr_body_signal`
   - Each old name kept as a module-level alias (`old = new`) for one release.

2. **Workspace shim renames** in `workflows/code_review/workspace.py`:
   - `_fetch_codex_cloud_review` → `_fetch_external_review`
   - `_fetch_codex_pr_body_signal` → `_fetch_external_review_pr_body_signal`
   - `_codex_cloud_placeholder` → `_external_review_placeholder`
   - All callers updated.

3. **Drop Phase B + D-1 back-compat aliases** (one-release window has elapsed):
   - `render_codex_cloud_repair_handoff_prompt` alias in `prompts.py` (B)
   - Top-level `codex-bot:` block fallback in workspace.py (B)
   - `run_claude_review` action-type alias in `actions.py` dispatcher (D-1)
   - `synthesize_repair_brief` `codexCloud` source alias in `reviews.py` (D-1)
   - Parity compatibility tuple `("run_claude_review", "request_internal_review")` in `runtime.py` and `tools.py` (D-1)
   - `get_review` legacy-key fallback in `migrations.py` (D-1)

4. **Internal param rename** in `actions.py` and call sites:
   - `run_acpx_prompt_fn` → `run_prompt_fn`
   - Internal Python API; no operator-visible surface.

5. **Tests**: alias-equivalence tests for new function aliases; alias-removed tests for dropped aliases; updated mocks pointing at new names.

6. **Operator docs**: short note in `skills/operator/SKILL.md` that the deprecation window has closed.

### Out of scope (Phase D-3, later)
- Other top-level ledger field renames: `claudeRepairHandoff`, `codexCloudRepairHandoff`, `codexCloudAutoResolved`, `claudeModel`, `interReviewAgentModel`, `lastClaudeVerdict`. Same migration pattern as D-1; deferred to keep D-2 scoped.
- Variable-name renames: `claude_review`, `existing_claude_review`, `previous_claude_review`, `codex_review`, `codex_cloud_review`. Pure cosmetic; not operator-visible.
- Drop the function-name aliases added by D-2 (would happen in a future D-3 or D-4).

## Architecture

### Function alias pattern
For each renamed function, source code uses the new name everywhere. The old name becomes a module-level binding for one release:

```python
# workflows/code_review/reviews.py

def fetch_external_review(pr_number, *, ...):
    ...

# Phase D-2 alias — drop next release
fetch_codex_cloud_review = fetch_external_review
```

Callers that import the function (`from .reviews import fetch_codex_cloud_review`) continue to work. New code uses `fetch_external_review`.

### Drop-alias pattern
- **Action-type alias:** `actions.py:477` currently reads `if action_type in ('run_internal_review', 'run_claude_review'):`. Becomes `if action_type == 'run_internal_review':`.
- **`synthesize_repair_brief` source alias:** currently `if source in ("externalReview", "codexCloud"):`. Becomes `if source == "externalReview":`.
- **Parity tuple:** drop `("run_claude_review", "request_internal_review")` from compatibility set in `runtime.py:3288` and `tools.py:86`.
- **`get_review`:** drop the `_LEGACY_KEY_FOR` fallback. The function becomes:
  ```python
  def get_review(reviews, new_key):
      return (reviews or {}).get(new_key) or {}
  ```
- **`render_codex_cloud_repair_handoff_prompt`:** delete the `render_codex_cloud_repair_handoff_prompt = render_external_reviewer_repair_handoff_prompt` line in `prompts.py`.
- **`codex-bot:` fallback:** delete the for-loop in workspace.py that copies legacy `codex-bot.*` keys into `ext_reviewer_cfg`.

### Migration safety
The `migrate_persisted_ledger` call still runs at workspace bootstrap. Even if a stale ledger somewhere still has `claudeCode` keys, the migration rewrites them on first boot. The risk is one tick where `get_review` reads `internalReview` (returns `{}`) before migration runs and code expects to find data. **Mitigation:** the migration call at `workspace.py:450` runs BEFORE the workspace's read closures are constructed (verified in D-1 review), so this race window does not exist in practice.

## Tests

New file `tests/test_rename_pass_phase_d_2.py`:

**Function alias equivalence:**
- `test_fetch_external_review_aliased_as_fetch_codex_cloud_review` — `fetch_codex_cloud_review is fetch_external_review`.
- Same for the other 7 function pairs.

**Aliases dropped:**
- `test_render_codex_cloud_repair_handoff_prompt_alias_dropped` — importing it now raises `ImportError`.
- `test_action_dispatcher_no_longer_accepts_run_claude_review` — feeding `'run_claude_review'` raises (or the dispatcher path bypasses it; assert via behavior).
- `test_synthesize_repair_brief_no_longer_accepts_codex_cloud_source` — feeding `source="codexCloud"` falls through to the else branch (legacy behavior pre-rename); existing alias test (`test_synthesize_repair_brief_accepts_legacy_codex_cloud_key`) needs to be updated or removed.
- `test_parity_map_no_longer_includes_run_claude_review_pair`
- `test_get_review_no_longer_falls_back_to_legacy_key` — `get_review({"claudeCode": {...}}, "internalReview")` returns `{}`, not the legacy value.
- `test_codex_bot_top_level_fallback_dropped` — the workspace builder no longer reads `codex-bot.logins` etc.

**Param rename:**
- `test_run_acpx_prompt_fn_renamed_to_run_prompt_fn` — actions.py signature uses `run_prompt_fn`; old kwarg name passed to the action raises TypeError.

**Existing tests:** any test that mocks `fetch_codex_cloud_review` directly continues to work via the alias. Any test that asserts `'run_claude_review'` in the dispatcher needs to be updated to `'run_internal_review'` (or removed if redundant). Same for the legacy-key migration tests in `tests/test_rename_pass_phase_d_1.py`.

Target: 564 + ~12 new = ~576 passing.

## Risks

1. **Test regressions** — existing tests may rely on dropped aliases. Plan: run full suite after each task; fix in place.
2. **External callers of the renamed functions** — none in this codebase (all callers are workspace shims). External tooling that imports `from workflows.code_review.reviews import fetch_codex_cloud_review` continues to work via the alias for one release.
3. **Live yoyopod ledger** — already migrated on D-1 boot. Dropping `get_review`'s legacy fallback affects only restored backups or downgrade-and-reupgrade scenarios. Operator must rerun migration in those cases.

## Open questions

None. Going ahead with the full scope listed above.
