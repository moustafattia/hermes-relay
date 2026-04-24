# Workflows contract + Code-Review workflow — design spec

**Date:** 2026-04-24
**Status:** approved, ready for implementation plan
**Scope:** hermes-relay plugin
**Supersedes:** the `adapters/<project>/` layout introduced by ADR-0001

## Problem statement

The hermes-relay plugin currently hosts a single adapter at `adapters/yoyopod_core/`. That adapter is, in practice, a **Code-Review workflow configured for the YoYoPod project** — it takes a GitHub issue labeled `active-lane`, dispatches a Codex coder session, runs Claude as internal pre-publish reviewer, publishes the PR, waits for Codex Cloud external review, and merges when clean.

The naming (`adapters/yoyopod_core/`) conflates two orthogonal concepts:

- **Workflows** — the playbook/engine: `code-review`, future `testing`, `security-review`, `performance-review`
- **Workspaces** — runtime bindings: today's `yoyopod` is one workspace running the Code-Review workflow; future projects are other workspaces

Operators also cannot currently adjust workflow behavior without editing Python: which model plays coder, which plays reviewer, whether external review runs at all, how many internal review turns before publish, etc. All of those knobs exist in the code but are only partially configurable via a JSON file whose shape leaks implementation history (Claude-prefixed and inter-review-agent-prefixed aliases for the same concept).

This spec re-frames the plugin around a **workflow-plugin contract** and introduces a **YAML configuration surface** so new workflows can be added by implementing the contract, and existing workflows can be tuned without code edits.

## Non-goals

The following are explicitly out of scope for this design; each becomes a candidate for a later spec:

1. **Multi-workflow composition** — one workspace binds to exactly one workflow in the YAML. Running Code-Review + Security-Review concurrently on the same workspace is a later design.
2. **New runtime implementations** beyond `acpx-codex` and `claude-cli`. The runtime protocol accommodates future runtimes (Kimi, Gemini, generic HTTP-API), but only the two runtimes currently in use are implemented.
3. **New workflows** (Testing, Security-Review, Performance-Review). They slot in after the contract ships; this spec delivers Code-Review as the proof that the contract is sound.
4. **Hot-reload of config.** The current process reads config at start-up and requires a restart on config change. That behavior is preserved.
5. **Operator-written hooks/scripts referenced from YAML.** Imperative-in-YAML is a trap; custom behavior = new workflow module.
6. **Lockfile / config pinning beyond `schema-version`.** Single-version pinning in the YAML is sufficient for the first iteration.

## Decision summary

### 1. Terminology + layout

- **Workflow:** a pluggable engine, at `workflows/<name>/`, declaring a required 5-attribute contract in its package `__init__.py`.
- **Workspace:** a runtime directory (e.g., `~/.hermes/workflows/yoyopod`) that binds to exactly one workflow via `config/workflow.yaml`.
- **Repo layout:**
  ```
  hermes-relay/
  ├── plugin.yaml
  ├── runtime.py                # unchanged
  ├── alerts.py                 # unchanged
  ├── tools.py                  # unchanged (slash-command surface)
  ├── schemas.py                # unchanged
  ├── workflows/                # NEW — replaces adapters/
  │   ├── __init__.py           # load_workflow + run_cli dispatcher
  │   ├── __main__.py           # generic CLI: python3 -m workflows ...
  │   └── code_review/
  │       ├── __init__.py       # NAME, SUPPORTED_SCHEMA_VERSIONS,
  │       │                     # CONFIG_SCHEMA_PATH, make_workspace, cli_main
  │       ├── __main__.py       # per-workflow direct form
  │       ├── cli.py
  │       ├── workspace.py      # workspace factory (takes YAML dict)
  │       ├── orchestrator.py
  │       ├── actions.py
  │       ├── reviews.py
  │       ├── sessions.py
  │       ├── prompts.py
  │       ├── github.py
  │       ├── status.py
  │       ├── workflow.py
  │       ├── health.py
  │       ├── paths.py
  │       ├── runtimes/
  │       │   ├── __init__.py   # Runtime Protocol
  │       │   ├── acpx_codex.py
  │       │   └── claude_cli.py
  │       ├── prompts/
  │       │   ├── internal-review-strict.md
  │       │   ├── internal-review-advisory.md
  │       │   ├── coder-dispatch.md
  │       │   └── repair-handoff.md
  │       └── schema.yaml       # JSON Schema for the YAML config
  ├── projects/
  │   └── yoyopod/              # one workspace binding
  │       └── config/
  │           └── workflow.yaml
  ├── scripts/                  # install.py/.sh + migrate_config.py
  ├── tests/
  ├── skills/
  └── docs/
  ```
- **Name mapping:** YAML + operator surface + `NAME` attribute all use **hyphens** (`code-review`); Python package uses **underscores** (`code_review`). A single `.replace("-", "_")` bridges them.

### 2. The workflow-plugin contract

Every workflow is a Python package at `workflows/<name>/` that exposes **five** attributes in its `__init__.py`:

```python
# workflows/code_review/__init__.py
from pathlib import Path

NAME = "code-review"
SUPPORTED_SCHEMA_VERSIONS = (1,)
CONFIG_SCHEMA_PATH = Path(__file__).parent / "schema.yaml"

from .workspace import make_workspace as make_workspace
from .cli import main as cli_main
```

Rationale:

- `NAME` — cross-checks the module name against the YAML's `workflow:` field; catches package-rename mistakes.
- `SUPPORTED_SCHEMA_VERSIONS` — explicit handshake so old configs do not silently run against new code.
- `CONFIG_SCHEMA_PATH` — validation happens before the workflow code runs; bad configs fail fast at the offending JSON-pointer path.
- `make_workspace(workflow_root, config)` — the workflow owns the shape of its workspace accessor; the plugin dispatcher knows only how to call this factory.
- `cli_main(workspace, argv)` — the workflow owns its CLI; the plugin passes argv through unchanged.

Not in the contract:

- The workspace accessor's attribute surface — internal to each workflow. Callers use the CLI; they do not import the package.
- The Runtime protocol — lives inside each workflow at `workflows/<name>/runtimes/`; not a plugin-level concern.

### 3. The dispatcher

`workflows/__init__.py` — small, readable in one screen:

```python
import importlib, yaml, jsonschema
from pathlib import Path
from types import ModuleType

class WorkflowContractError(RuntimeError):
    pass

_REQUIRED_ATTRS = (
    "NAME",
    "SUPPORTED_SCHEMA_VERSIONS",
    "CONFIG_SCHEMA_PATH",
    "make_workspace",
    "cli_main",
)

def load_workflow(name: str) -> ModuleType:
    """Import workflows.<slug> and verify it meets the contract."""
    slug = name.replace("-", "_")
    module = importlib.import_module(f"workflows.{slug}")
    missing = [attr for attr in _REQUIRED_ATTRS if not hasattr(module, attr)]
    if missing:
        raise WorkflowContractError(
            f"workflow '{name}' missing required attributes: {missing}"
        )
    if module.NAME != name:
        raise WorkflowContractError(
            f"workflow module workflows/{slug} declares NAME={module.NAME!r}, "
            f"which does not match the directory '{name}'"
        )
    return module


def run_cli(workflow_root: Path, argv: list[str],
            *, require_workflow: str | None = None) -> int:
    """Read config/workflow.yaml, dispatch to the named workflow.

    When ``require_workflow`` is set, the dispatcher asserts that the YAML's
    ``workflow:`` field matches before dispatching. Used by the per-workflow
    direct form (``python3 -m workflows.code_review ...``) to pin the module
    regardless of what the YAML declares.
    """
    config_path = workflow_root / "config" / "workflow.yaml"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    workflow_name = cfg.get("workflow")
    if not workflow_name:
        raise WorkflowContractError(
            f"{config_path} is missing top-level `workflow:` field"
        )
    if require_workflow and workflow_name != require_workflow:
        raise WorkflowContractError(
            f"{config_path} declares workflow={workflow_name!r}, "
            f"but invocation pins require_workflow={require_workflow!r}"
        )

    module = load_workflow(workflow_name)

    schema_version = int(cfg.get("schema-version", 1))
    if schema_version not in module.SUPPORTED_SCHEMA_VERSIONS:
        raise WorkflowContractError(
            f"workflow '{workflow_name}' does not support "
            f"schema-version={schema_version}; "
            f"supported: {list(module.SUPPORTED_SCHEMA_VERSIONS)}"
        )

    schema = yaml.safe_load(module.CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(cfg, schema)

    workspace = module.make_workspace(workflow_root=workflow_root, config=cfg)
    return module.cli_main(workspace, argv)
```

`workflows/__main__.py` is a ~20-line wrapper that parses `--workflow-root`, honors env fallbacks (`YOYOPOD_WORKFLOW_ROOT`, `HERMES_RELAY_WORKFLOW_ROOT`), and delegates to `run_cli`.

### 4. Invocation surfaces

Two forms are supported; each has a clear use case.

**Generic (recommended default):**

```bash
python3 -m workflows --workflow-root ~/.hermes/workflows/yoyopod status --json
python3 -m workflows --workflow-root ~/.hermes/workflows/yoyopod tick --json
```

- Reads `<root>/config/workflow.yaml`, dispatches on `workflow:` key.
- Portable across workspaces regardless of which workflow is bound.
- Used by cron job prompts, skill docs, ad-hoc operator commands.

**Per-workflow direct form (explicit, for debugging/testing):**

```bash
python3 -m workflows.code_review --workflow-root ~/.hermes/workflows/yoyopod status --json
```

- Pins the workflow module; still parses + validates the YAML.
- Behavior: `workflows/code_review/__main__.py` calls `workflows.run_cli(workflow_root, argv, require_workflow="code-review")`. The dispatcher loads the YAML as usual, then asserts `cfg["workflow"] == require_workflow` before dispatching. Mismatch raises `WorkflowContractError` with both the expected and actual names.
- Use case: developing a new workflow against a workspace whose YAML still declares the old one, or asserting a test harness is pointing at the correct module.

**Installed plugin paths (stable external-caller surface):**

- `~/.hermes/plugins/hermes-relay/workflows/` — the package.
- External callers (cron job prompts, skill docs, operator cheat sheet) standardize on:
  ```bash
  python3 /home/radxa/.hermes/plugins/hermes-relay/workflows/__main__.py \
    --workflow-root <root> <cmd>
  ```
- systemd service (`yoyopod-relay-active.service`) is unchanged — it continues to target `runtime.py run-active`, which internally uses the helper currently named `yoyopod_cli_argv` (renamed to `workflow_cli_argv` and moved to `workflows/code_review/paths.py`; runtime.py / tools.py import from the new location).

### 5. YAML config schema

Canonical file: `<workspace>/config/workflow.yaml`. Replaces the current `yoyopod-workflow.json`.

```yaml
workflow: code-review
schema-version: 1

instance:
  name: yoyopod
  engine-owner: hermes          # hermes | openclaw — selects cron-store backend

repository:
  local-path: /home/radxa/.hermes/workspaces/YoyoPod_Core
  github-slug: moustafattia/YoyoPod_Core
  active-lane-label: active-lane

# ── RUNTIMES — how we talk to models ─────────────────────────────
# Agents reference runtimes by name. Each runtime kind has its own
# shape; adding a new kind is a code change in
# workflows/code_review/runtimes/<kind>.py, not just a YAML edit.
runtimes:
  acpx-codex:                   # persistent-session runtime (Codex via acpx)
    kind: acpx-codex
    session-idle-freshness-seconds: 900
    session-idle-grace-seconds: 1800
    session-nudge-cooldown-seconds: 600

  claude-cli:                   # one-shot runtime (Claude via claude CLI)
    kind: claude-cli
    max-turns-per-invocation: 24
    timeout-seconds: 1200

# ── AGENTS — role → identity → runtime ───────────────────────────
agents:
  coder:                        # tiers; engine picks one per escalation state
    default:
      name: Internal_Coder_Agent
      model: gpt-5.3-codex-spark/high
      runtime: acpx-codex
    high-effort:
      name: Internal_Coder_Agent
      model: gpt-5.3-codex
      runtime: acpx-codex
    escalated:
      name: Escalation_Coder_Agent
      model: gpt-5.4
      runtime: acpx-codex

  internal-reviewer:
    name: Internal_Reviewer_Agent
    model: claude-sonnet-4-6
    runtime: claude-cli
    freeze-coder-while-running: true

  external-reviewer:            # polls GitHub for bot verdicts, not a runtime
    enabled: true
    name: External_Reviewer_Agent
    provider: codex-cloud
    cache-seconds: 1800

  advisory-reviewer:
    enabled: false
    name: Advisory_Reviewer_Agent

# ── GATES — when to publish / merge ──────────────────────────────
gates:
  internal-review:
    pass-with-findings-tolerance: 1
    require-pass-clean-before-publish: true
    request-cooldown-seconds: 1200
  external-review:
    required-for-merge: true    # only consulted when external-reviewer.enabled
  merge:
    require-ci-acceptable: true

# ── TRIGGERS — what starts a lane ───────────────────────────────
triggers:
  lane-selector:
    type: github-label
    label: active-lane
  start-conditions:
    - issue-state: open
    - has-open-pr: false

# ── ESCALATION — when to upgrade coder / ask for operator help ──
escalation:
  restart-count-threshold: 2
  local-review-count-threshold: 2
  postpublish-finding-threshold: 3
  lane-failure-retry-budget: 3
  no-progress-tick-budget: 3
  operator-attention-retry-threshold: 5
  operator-attention-no-progress-threshold: 5
  lane-counter-increment-min-seconds: 240

# ── SCHEDULES — cron cadence ────────────────────────────────────
schedules:
  watchdog-tick:
    interval-minutes: 5
  milestone-notifier:
    interval-hours: 1
    delivery:
      channel: telegram
      chat-id: "-1003651617977"

# ── PROMPTS — bundled template selection ────────────────────────
prompts:
  internal-review: internal-review-strict
  coder-dispatch: coder-dispatch
  repair-handoff: repair-handoff

# ── STORAGE — workspace-relative paths ──────────────────────────
storage:
  ledger: memory/workflow-status.json
  health: memory/workflow-health.json
  audit-log: memory/workflow-audit.jsonl
  cron-jobs-path: archive/openclaw-cron-jobs.json
  hermes-cron-jobs-path: ~/.hermes/cron/jobs.json
  sessions-state: state/sessions

# ── CODEX-BOT signals (external reviewer recognition) ───────────
codex-bot:
  logins: [chatgpt-codex-connector, "chatgpt-codex-connector[bot]"]
  clean-reactions: ["+1"]
  pending-reactions: [eyes]
```

### 6. Runtime protocol

`workflows/code_review/runtimes/__init__.py` defines a `Protocol` that every runtime kind implements:

```python
from typing import Protocol

class SessionHandle(Protocol):
    record_id: str | None
    session_id: str | None
    name: str

class SessionHealth(Protocol):
    healthy: bool
    reason: str | None
    last_used_at: str | None

class Runtime(Protocol):
    def ensure_session(self, *, worktree: Path, session_name: str,
                       model: str, resume_session_id: str | None) -> SessionHandle: ...
    def run_prompt(self, *, worktree: Path, session_name: str,
                   prompt: str, model: str) -> str: ...
    def assess_health(self, session_meta: dict, *, worktree: Path,
                      now_epoch: int | None = None) -> SessionHealth: ...
    def close_session(self, *, worktree: Path, session_name: str) -> None: ...
```

- **`acpx-codex` runtime** wraps today's `ensure_acpx_session` / `run_acpx_prompt` / `close_acpx_session` / session-health assessment from `sessions.py`.
- **`claude-cli` runtime** wraps the `claude`-CLI invocation currently inlined in `reviews.run_inter_review_agent_review`. `ensure_session` and `close_session` are no-ops; `assess_health` always returns healthy (one-shot runtime).

**How the workspace exposes runtimes.** `make_workspace` inspects the YAML's `runtimes:` section and instantiates one `Runtime` instance per entry, keyed by the profile name. The workspace accessor exposes them via a single method:

```python
ws.runtime("acpx-codex")  # -> AcpxCodexRuntime instance
ws.runtime("claude-cli")  # -> ClaudeCliRuntime instance
```

Callers that need the coder's runtime look up the agent tier first, then fetch the runtime by the agent's `runtime:` field:

```python
tier = ws.coder_tier_for_lane(lane)            # returns agents.coder.<tier> dict
runtime = ws.runtime(tier["runtime"])          # "acpx-codex"
runtime.run_prompt(worktree=..., session_name=..., prompt=..., model=tier["model"])
```

No caller constructs a runtime directly. Runtimes are instantiated once per workspace, reused across calls.
- **Future runtimes** (Kimi, Gemini, generic HTTP-API) add a file under `workflows/code_review/runtimes/` that implements the protocol; no dispatcher change required.

## Migration plan

Six mergeable slices, each green at HEAD:

**Slice 1 — Scaffold dispatcher (no workflow migrated yet)**

- New: `workflows/__init__.py`, `workflows/__main__.py`
- New: `tests/test_workflows_dispatcher.py` (5 tests: discovery, missing-attr, name/dir mismatch, unsupported schema-version, invalid YAML)
- `adapters/` untouched

**Slice 2 — Copy `adapters/yoyopod_core/` → `workflows/code_review/`**

- Literal copy of all 14 modules; internal imports updated
- Add the 5 contract attributes to `workflows/code_review/__init__.py`
- New: `workflows/code_review/schema.yaml` (JSON Schema covering the full YAML)
- New: `workflows/code_review/__main__.py` (per-workflow direct form)
- Copy tests: `tests/test_yoyopod_core_*.py` → `tests/test_workflows_code_review_*.py`
- Both paths exist temporarily; both pass tests

**Slice 3 — Extract runtime protocol**

- New: `workflows/code_review/runtimes/__init__.py` (Protocol)
- New: `workflows/code_review/runtimes/acpx_codex.py`
- New: `workflows/code_review/runtimes/claude_cli.py`
- Rewire `sessions.py` + `reviews.py` to use `workspace.runtime(name)`
- New tests: `tests/test_workflows_code_review_runtimes_*.py`

**Slice 4 — Switch config to YAML + new schema shape**

- New: `scripts/migrate_config.py` — reads old JSON, writes new YAML
- `workflows/code_review/workspace.py` consumes the new YAML dict
- `workflows/code_review/schema.yaml` enforces the shape
- Test fixtures updated to new YAML shape
- Run migration on the live workspace config; delete the old JSON

**Slice 5 — Delete `adapters/`, re-wire external callers**

- `git rm -r adapters/`
- `runtime.py`, `tools.py`, `alerts.py`: rewire imports from `adapters.yoyopod_core.paths` → `workflows.code_review.paths`
- `paths.plugin_entrypoint_path` now returns `.../workflows/__main__.py`
- Skill docs, cron job prompts, operator cheat sheet: new CLI path
- Installer: `PAYLOAD_ITEMS`: `"adapters"` → `"workflows"`
- Run `./scripts/install.sh`; run live `tick --json` via new entrypoint; assert parity
- Delete `tests/test_yoyopod_core_*.py`

**Slice 6 — Polish**

- README, CLAUDE.md, `docs/architecture.md`, `docs/operator-cheat-sheet.md` updated
- Bump `plugin.yaml` version 0.1.0 → 0.2.0
- Add `docs/adr/ADR-0002-workflows-contract.md`

## Test strategy

- **Carried over:** all 203 existing `tests/test_yoyopod_core_*.py` tests, renamed + re-imported. No assertion changes.
- **New:**
  - `tests/test_workflows_dispatcher.py` — 5 tests (contract validation)
  - `tests/test_workflows_code_review_runtimes_acpx_codex.py` — ~6 tests
  - `tests/test_workflows_code_review_runtimes_claude_cli.py` — ~4 tests
  - `tests/test_workflows_code_review_yaml_config.py` — ~6 tests (YAML parsing, schema validation, error paths, migration one-shot)
  - `tests/test_workflows_code_review_schema.py` — ~5 tests (every old JSON setting has a clean YAML mapping, required fields enforced, type constraints)
- **Target total:** ~230 tests.

## Acceptance criteria

1. `./scripts/install.sh` installs a `workflows/` tree; the old `adapters/` path is gone.
2. `python3 -m workflows --workflow-root ~/.hermes/workflows/yoyopod status --json` produces output identical to today's `python3 -m adapters.yoyopod_core status --json`.
3. `python3 -m workflows.code_review --workflow-root ~/.hermes/workflows/yoyopod tick --json` works as the explicit form.
4. `~/.hermes/workflows/yoyopod/config/workflow.yaml` exists; `yoyopod-workflow.json` does not.
5. Live YoYoPod workflow operates end-to-end (reconcile, tick, dispatch, review, publish, merge) with no behavior change.
6. `pytest` reports ≥ 225 passing tests, no pre-existing tests broken.
7. Adding a hypothetical new runtime (e.g., `http-api`) requires only a new file under `workflows/code_review/runtimes/` plus a config entry; no changes to the dispatcher or the workspace factory.

## Resolved decisions

1. **Compat alias for `adapters/`?** No. Clean break. Installer removes any pre-existing `adapters/` directory from the installed plugin tree.
2. **Config filename?** `workflow.yaml` at `<workflow_root>/config/workflow.yaml`. `migrate_config.py` writes this and deletes the old `yoyopod-workflow.json`.
3. **YAML `!include` support?** No. One file per workspace.
4. **Lockfile (`workflow.lock.yaml`)?** No. `schema-version` in the config is sufficient.
5. **Plugin version bump?** 0.1.0 → 0.2.0.
6. **Workspace accessor retained?** Yes. Factory builds a SimpleNamespace accessor per workflow; internal shape is workflow-private and not part of the plugin contract.
7. **Runtime choice per agent vs per role vs globally?** Per agent. `agents.<role>.runtime: <name>` references a named profile in `runtimes:`. Each coder tier can choose its own runtime if needed.
8. **External-reviewer shape?** `provider:` field, not `runtime:` field. External review polls a bot's PR comments rather than invoking a model — different abstraction.

## Future work (explicitly deferred)

- Multi-workflow-per-workspace composition
- Testing / Security-Review / Performance-Review workflows implementing the contract
- HTTP-API runtime (Kimi, Gemini, OpenAI-compatible providers)
- Hot-reload of config
- Operator-facing workflow packaging / sharing (once the design is validated on YoYoPod)
