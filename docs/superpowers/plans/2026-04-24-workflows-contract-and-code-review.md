# Workflows contract + Code-Review workflow — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-frame `hermes-relay` around a workflow-plugin contract: `adapters/yoyopod_core/` becomes `workflows/code_review/`, a dispatcher routes invocations based on a YAML config, the coder/reviewer plumbing is extracted behind a runtime Protocol, and the config moves from JSON to YAML with a cleaner structure.

**Architecture:** Each workflow is a Python package at `workflows/<name>/` exposing five required attributes (`NAME`, `SUPPORTED_SCHEMA_VERSIONS`, `CONFIG_SCHEMA_PATH`, `make_workspace`, `cli_main`). A plugin-level dispatcher at `workflows/__init__.py` reads `<workspace>/config/workflow.yaml`, validates against the workflow's JSON Schema, and hands off to its `cli_main`. Runtimes (`acpx-codex`, `claude-cli`) are pluggable behind a `Runtime` Protocol; the workspace factory instantiates runtimes from YAML and exposes them via `ws.runtime(name)`.

**Tech Stack:** Python 3.11+, pytest 9.x, PyYAML 6.x (already on the host), jsonschema (installed via apt package `python3-jsonschema` — adding the dep check in Phase 1).

**Design spec:** `docs/superpowers/specs/2026-04-24-workflows-contract-and-code-review-design.md`. Read it first.

---

## 0. Context for the implementing engineer

- The plugin repo lives at **`/home/radxa/WS/hermes-relay`**. All file paths in this plan are relative to that root unless absolute.
- The live workspace used for integration testing is **`/home/radxa/.hermes/workflows/yoyopod`**. Its plugin tree is a symlink at `~/.hermes/plugins/hermes-relay` → `~/.hermes/workflows/yoyopod/.hermes/plugins/hermes-relay/`.
- The current adapter package is **`adapters/yoyopod_core/`** (14 modules, ~9 kloc). It holds the Code-Review workflow logic and will be literally copied to `workflows/code_review/` in Phase 2, then deleted in Phase 5.
- Tests live at **`tests/`** with `pytest.ini` setting `testpaths = tests`. Baseline: 203 passing tests (excluding the pre-existing `tests/test_runtime_tools_alerts.py` sqlite-fixture failure which is outside this work).
- Terminology: **workflow** = engine type (e.g. `code-review`); **workspace** = runtime directory (e.g. `yoyopod`); **runtime** = plumbing to talk to a model (`acpx-codex`, `claude-cli`). The workspace **accessor** is a `types.SimpleNamespace` holding constants, primitives, and closures — returned by `make_workspace(workflow_root, config)`.
- `acpx` is the persistent-session layer for Codex (`acpx codex sessions ensure`, `acpx codex prompt`). `claude` CLI is the one-shot Claude Code invocation. Both are already on the host.
- Run tests with: `cd /home/radxa/WS/hermes-relay && python -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q`.
- The `python3` on `$PATH` may be a homebrew build without pyyaml; the system `/usr/bin/python3` is 3.11 with pyyaml installed. Plan commands use `python3` (resolve via `$PATH`) — if pyyaml is missing, install via `sudo apt install python3-yaml python3-jsonschema` first.

## File structure

Files created or modified by this plan. Each listed once.

### New files

| Path | Purpose |
|---|---|
| `workflows/__init__.py` | Dispatcher: `load_workflow()`, `run_cli()`, `WorkflowContractError` |
| `workflows/__main__.py` | Generic CLI: `python3 -m workflows --workflow-root <root> <cmd>` |
| `workflows/code_review/__init__.py` | Exports `NAME`, `SUPPORTED_SCHEMA_VERSIONS`, `CONFIG_SCHEMA_PATH`, `make_workspace`, `cli_main` |
| `workflows/code_review/__main__.py` | Per-workflow direct-form entry (pins workflow via `require_workflow`) |
| `workflows/code_review/schema.yaml` | JSON Schema validating `workflow.yaml` |
| `workflows/code_review/runtimes/__init__.py` | `Runtime`, `SessionHandle`, `SessionHealth` Protocols + `build_runtimes(runtimes_cfg)` factory |
| `workflows/code_review/runtimes/acpx_codex.py` | Persistent-session runtime for Codex via `acpx codex` |
| `workflows/code_review/runtimes/claude_cli.py` | One-shot runtime for Claude via `claude` CLI |
| `workflows/code_review/prompts/internal-review-strict.md` | Strict internal-reviewer prompt template |
| `workflows/code_review/prompts/coder-dispatch.md` | Coder-dispatch prompt template |
| `workflows/code_review/prompts/repair-handoff.md` | Post-publish repair-handoff prompt template |
| `scripts/migrate_config.py` | One-shot JSON → YAML config migrator |
| `docs/adr/ADR-0002-workflows-contract.md` | ADR capturing this decision |
| `tests/test_workflows_dispatcher.py` | Contract + dispatcher tests |
| `tests/test_workflows_code_review_init.py` | Asserts code-review exposes the 5 contract attributes |
| `tests/test_workflows_code_review_runtimes_acpx_codex.py` | AcpxCodexRuntime Protocol conformance |
| `tests/test_workflows_code_review_runtimes_claude_cli.py` | ClaudeCliRuntime Protocol conformance |
| `tests/test_workflows_code_review_schema.py` | schema.yaml shape correctness (YAML validation paths covered here) |
| `tests/test_migrate_config.py` | migrate_config.py golden-file tests |
| `tests/test_workflows_code_review_workspace.py` | workspace factory against new YAML shape (supersedes the copied adapters test) |
| `tests/test_workflows_code_review_*.py` (15 files) | Copies of `tests/test_yoyopod_core_*.py` |

### Modified files

| Path | Change |
|---|---|
| `scripts/install.py` | Add jsonschema/pyyaml dependency check; update `PAYLOAD_ITEMS` (Phase 5) |
| `scripts/install.sh` | Update comment block to reflect workflows/ (Phase 6) |
| `runtime.py` | Rewire imports from `adapters.yoyopod_core.paths` → `workflows.code_review.paths` (Phase 5) |
| `tools.py` | Same import rewire (Phase 5) |
| `alerts.py` | Same import rewire (Phase 5) |
| `plugin.yaml` | Bump `version: 0.1.0` → `0.2.0` (Phase 6) |
| `README.md` | Replace `adapters/` layout description with `workflows/` (Phase 6) |
| `docs/architecture.md` | Update diagrams + prose (Phase 6) |
| `docs/operator-cheat-sheet.md` | Update commands (Phase 6) |
| `skills/yoyopod-workflow-watchdog-tick/SKILL.md` | Replace CLI path (Phase 6) |
| `skills/yoyopod-closeout-notifier/SKILL.md` | Replace CLI path (Phase 6) |
| `skills/yoyopod-lane-automation/SKILL.md` | Replace CLI path (Phase 6) |

### Deleted files (Phase 5)

| Path | Reason |
|---|---|
| `adapters/` (entire tree) | Replaced by `workflows/` |
| `tests/test_yoyopod_core_*.py` (15 files) | Replaced by `tests/test_workflows_code_review_*.py` |

---

## Dependencies

Phase 1, Task 1 verifies these are installed. If missing, install once via:

```bash
sudo apt install python3-yaml python3-jsonschema
```

- **PyYAML ≥ 6.0** — YAML parser (`yaml.safe_load`, `yaml.safe_dump`)
- **jsonschema ≥ 4.0** — Draft 7+ schema validator (`jsonschema.validate`)
- **pytest 9.x** — already in use

---

## Phase 1 — Dispatcher scaffold (no workflow migrated yet)

Establish `workflows/__init__.py` with `load_workflow()` and `run_cli()`, and `workflows/__main__.py` as the generic CLI. No existing code changes.

### Task 1.1: Verify runtime dependencies present

**Files:** none (verification only)

- [ ] **Step 1: Run the dependency probe**

```bash
cd /home/radxa/WS/hermes-relay
python3 -c "import yaml, jsonschema; print(f'yaml={yaml.__version__} jsonschema={jsonschema.__version__}')"
```

Expected: a line like `yaml=6.0 jsonschema=4.10.3`.

If it fails with `ModuleNotFoundError: No module named 'yaml'` or `'jsonschema'`:

```bash
sudo apt install python3-yaml python3-jsonschema
```

Then re-run the probe. Do not proceed until both modules import cleanly.

- [ ] **Step 2: Pin the python used for tests**

```bash
which python3 && python3 --version
```

If `python3` resolves to a homebrew build without pyyaml, force system python for this project:

```bash
alias python3=/usr/bin/python3
```

Or always invoke tests with `/usr/bin/python3 -m pytest ...`. Note: the rest of this plan uses `python3` — adjust if your shell alias differs.

### Task 1.2: Write failing test for `load_workflow()` contract validation

**Files:**
- Create: `tests/test_workflows_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workflows_dispatcher.py
import importlib
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _import_workflows():
    """Import workflows/__init__.py without poisoning sys.modules for later tests."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if "workflows" in sys.modules:
        del sys.modules["workflows"]
    return importlib.import_module("workflows")


def test_load_workflow_returns_module_when_contract_is_complete(tmp_path, monkeypatch):
    """A package exposing all five required attributes loads and is returned as-is."""
    wf_root = tmp_path / "workflows"
    (wf_root / "fake_wf").mkdir(parents=True)
    (wf_root / "__init__.py").write_text("", encoding="utf-8")
    (wf_root / "fake_wf" / "__init__.py").write_text(
        "from pathlib import Path\n"
        "NAME = 'fake-wf'\n"
        "SUPPORTED_SCHEMA_VERSIONS = (1,)\n"
        "CONFIG_SCHEMA_PATH = Path(__file__).parent / 'schema.yaml'\n"
        "def make_workspace(*, workflow_root, config): return {}\n"
        "def cli_main(ws, argv): return 0\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    # Ensure our shadow 'workflows' package beats the repo one
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows = importlib.import_module("workflows")
    module = workflows.load_workflow("fake-wf")

    assert module.NAME == "fake-wf"
    assert module.SUPPORTED_SCHEMA_VERSIONS == (1,)
    assert callable(module.make_workspace)
    assert callable(module.cli_main)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_workflows_dispatcher.py::test_load_workflow_returns_module_when_contract_is_complete -v
```

Expected: `ModuleNotFoundError: No module named 'workflows'` — the package does not yet exist.

- [ ] **Step 3: Create the workflows package with minimal `load_workflow`**

Create `workflows/__init__.py`:

```python
"""Workflow-plugin dispatcher for hermes-relay.

A workflow is a Python package at ``workflows/<name>/`` (hyphens in the
canonical name map to underscores in the Python slug). Every workflow
must expose these five attributes in its package ``__init__.py``:

- NAME: str                     — canonical hyphenated name
- SUPPORTED_SCHEMA_VERSIONS: tuple[int, ...]  — YAML schema versions this module can load
- CONFIG_SCHEMA_PATH: Path      — path to JSON Schema for the workflow's config
- make_workspace(*, workflow_root: Path, config: dict) -> object
- cli_main(workspace: object, argv: list[str]) -> int
"""
from __future__ import annotations

import importlib
from types import ModuleType


class WorkflowContractError(RuntimeError):
    """Raised when a workflow package does not meet the required contract."""


_REQUIRED_ATTRS = (
    "NAME",
    "SUPPORTED_SCHEMA_VERSIONS",
    "CONFIG_SCHEMA_PATH",
    "make_workspace",
    "cli_main",
)


def load_workflow(name: str) -> ModuleType:
    """Import ``workflows.<slug>`` and verify it meets the contract.

    ``name`` is the canonical hyphenated form (``code-review``);
    internally it maps to the Python slug (``code_review``).
    """
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_workflows_dispatcher.py::test_load_workflow_returns_module_when_contract_is_complete -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /home/radxa/WS/hermes-relay
git add workflows/__init__.py tests/test_workflows_dispatcher.py
git commit -m "$(cat <<'EOF'
feat(workflows): introduce dispatcher with load_workflow contract validator

First cut of the workflow-plugin contract. load_workflow('code-review')
imports workflows.code_review, checks for the five required attributes
(NAME, SUPPORTED_SCHEMA_VERSIONS, CONFIG_SCHEMA_PATH, make_workspace,
cli_main), and cross-checks module.NAME against the directory. Missing
attrs or name/dir mismatches raise WorkflowContractError with the
offending attribute list or names.

No workflows are migrated yet; only the scaffold + first passing test.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 1.3: Add test coverage for contract-violation cases

**Files:**
- Modify: `tests/test_workflows_dispatcher.py` (append tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_workflows_dispatcher.py`:

```python
def test_load_workflow_raises_on_missing_attributes(tmp_path, monkeypatch):
    (tmp_path / "workflows" / "incomplete").mkdir(parents=True)
    (tmp_path / "workflows" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "workflows" / "incomplete" / "__init__.py").write_text(
        "NAME = 'incomplete'\n",  # missing the other four attrs
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows = importlib.import_module("workflows")
    with pytest.raises(workflows.WorkflowContractError) as exc:
        workflows.load_workflow("incomplete")
    msg = str(exc.value)
    assert "missing required attributes" in msg
    assert "SUPPORTED_SCHEMA_VERSIONS" in msg
    assert "CONFIG_SCHEMA_PATH" in msg
    assert "make_workspace" in msg
    assert "cli_main" in msg


def test_load_workflow_raises_when_name_does_not_match_directory(tmp_path, monkeypatch):
    (tmp_path / "workflows" / "mismatched").mkdir(parents=True)
    (tmp_path / "workflows" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "workflows" / "mismatched" / "__init__.py").write_text(
        "from pathlib import Path\n"
        "NAME = 'some-other-name'\n"
        "SUPPORTED_SCHEMA_VERSIONS = (1,)\n"
        "CONFIG_SCHEMA_PATH = Path(__file__).parent / 's.yaml'\n"
        "def make_workspace(*, workflow_root, config): return None\n"
        "def cli_main(ws, argv): return 0\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows = importlib.import_module("workflows")
    with pytest.raises(workflows.WorkflowContractError) as exc:
        workflows.load_workflow("mismatched")
    assert "declares NAME='some-other-name'" in str(exc.value)
    assert "'mismatched'" in str(exc.value)
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_workflows_dispatcher.py -v
```

Expected: 3 PASS (the existing one + 2 new ones). The missing-attr + name-mismatch paths are already implemented in `load_workflow`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_workflows_dispatcher.py
git commit -m "test(workflows): cover load_workflow contract-violation branches

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 1.4: Implement `run_cli()` with YAML load + schema validation + dispatch

**Files:**
- Modify: `workflows/__init__.py`
- Modify: `tests/test_workflows_dispatcher.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_workflows_dispatcher.py`:

```python
def _write_stub_workflow(tmp_path, *, name="stub-wf", supported=(1,), raises=None):
    """Drop a minimal workflow package under tmp_path/workflows/<slug>/ + schema.yaml."""
    slug = name.replace("-", "_")
    (tmp_path / "workflows" / slug).mkdir(parents=True, exist_ok=True)
    (tmp_path / "workflows" / "__init__.py").write_text("", encoding="utf-8")
    # Minimal schema: require top-level 'workflow' + 'schema-version' keys
    schema = (
        "$schema: http://json-schema.org/draft-07/schema#\n"
        "type: object\n"
        "required: [workflow, schema-version]\n"
        "properties:\n"
        "  workflow: {type: string}\n"
        "  schema-version: {type: integer}\n"
    )
    (tmp_path / "workflows" / slug / "schema.yaml").write_text(schema, encoding="utf-8")
    supported_tuple = f"({', '.join(str(v) for v in supported)},)"
    raise_line = f"    raise {raises}('boom')\n" if raises else ""
    (tmp_path / "workflows" / slug / "__init__.py").write_text(
        f"from pathlib import Path\n"
        f"NAME = {name!r}\n"
        f"SUPPORTED_SCHEMA_VERSIONS = {supported_tuple}\n"
        f"CONFIG_SCHEMA_PATH = Path(__file__).parent / 'schema.yaml'\n"
        f"def make_workspace(*, workflow_root, config):\n"
        f"    return {{'cfg': config, 'root': str(workflow_root)}}\n"
        f"def cli_main(ws, argv):\n"
        f"{raise_line}    print(f'ran {name} with argv={{argv}}')\n"
        f"    return 0\n",
        encoding="utf-8",
    )


def test_run_cli_dispatches_to_named_workflow_and_returns_its_exit_code(tmp_path, monkeypatch, capsys):
    _write_stub_workflow(tmp_path, name="demo-wf")
    workspace_root = tmp_path / "workspace"
    (workspace_root / "config").mkdir(parents=True)
    (workspace_root / "config" / "workflow.yaml").write_text(
        "workflow: demo-wf\nschema-version: 1\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows = importlib.import_module("workflows")
    code = workflows.run_cli(workspace_root, ["status", "--json"])

    assert code == 0
    assert "ran demo-wf with argv=['status', '--json']" in capsys.readouterr().out


def test_run_cli_raises_when_workflow_key_missing(tmp_path, monkeypatch):
    workspace_root = tmp_path / "workspace"
    (workspace_root / "config").mkdir(parents=True)
    (workspace_root / "config" / "workflow.yaml").write_text(
        "schema-version: 1\n",  # missing 'workflow:'
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows = importlib.import_module("workflows")
    with pytest.raises(workflows.WorkflowContractError) as exc:
        workflows.run_cli(workspace_root, [])
    assert "missing top-level `workflow:` field" in str(exc.value)


def test_run_cli_raises_on_unsupported_schema_version(tmp_path, monkeypatch):
    _write_stub_workflow(tmp_path, name="demo-wf", supported=(1, 2))
    workspace_root = tmp_path / "workspace"
    (workspace_root / "config").mkdir(parents=True)
    (workspace_root / "config" / "workflow.yaml").write_text(
        "workflow: demo-wf\nschema-version: 99\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows = importlib.import_module("workflows")
    with pytest.raises(workflows.WorkflowContractError) as exc:
        workflows.run_cli(workspace_root, [])
    assert "does not support schema-version=99" in str(exc.value)
    assert "[1, 2]" in str(exc.value)


def test_run_cli_raises_when_require_workflow_does_not_match_yaml(tmp_path, monkeypatch):
    _write_stub_workflow(tmp_path, name="demo-wf")
    workspace_root = tmp_path / "workspace"
    (workspace_root / "config").mkdir(parents=True)
    (workspace_root / "config" / "workflow.yaml").write_text(
        "workflow: demo-wf\nschema-version: 1\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows = importlib.import_module("workflows")
    with pytest.raises(workflows.WorkflowContractError) as exc:
        workflows.run_cli(workspace_root, [], require_workflow="other-wf")
    assert "declares workflow='demo-wf'" in str(exc.value)
    assert "require_workflow='other-wf'" in str(exc.value)


def test_run_cli_raises_on_schema_validation_error(tmp_path, monkeypatch):
    _write_stub_workflow(tmp_path, name="demo-wf")
    # schema requires 'workflow' AND 'schema-version', both strings/ints.
    # Drop 'schema-version' to trigger a jsonschema validation error.
    workspace_root = tmp_path / "workspace"
    (workspace_root / "config").mkdir(parents=True)
    (workspace_root / "config" / "workflow.yaml").write_text(
        "workflow: demo-wf\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    import jsonschema
    workflows = importlib.import_module("workflows")
    # run_cli defaults schema-version=1 when missing, so to trigger validation,
    # add a property the schema disallows.
    (workspace_root / "config" / "workflow.yaml").write_text(
        "workflow: demo-wf\nschema-version: not-an-integer\n",
        encoding="utf-8",
    )
    with pytest.raises(jsonschema.ValidationError):
        workflows.run_cli(workspace_root, [])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_workflows_dispatcher.py -v
```

Expected: 5 FAIL (the new ones) — `run_cli` does not exist yet.

- [ ] **Step 3: Implement `run_cli`**

Append to `workflows/__init__.py`:

```python
from pathlib import Path

import yaml
import jsonschema


def run_cli(
    workflow_root: Path,
    argv: list[str],
    *,
    require_workflow: str | None = None,
) -> int:
    """Read <workflow_root>/config/workflow.yaml, dispatch to the named workflow.

    When ``require_workflow`` is set, the dispatcher asserts that the YAML's
    ``workflow:`` field matches before dispatching. Used by the per-workflow
    direct form (``python3 -m workflows.code_review ...``) to pin the module
    regardless of what the YAML declares.
    """
    config_path = workflow_root / "config" / "workflow.yaml"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise WorkflowContractError(
            f"{config_path} must contain a YAML mapping at the top level"
        )
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
            f"workflow {workflow_name!r} does not support "
            f"schema-version={schema_version}; "
            f"supported: {list(module.SUPPORTED_SCHEMA_VERSIONS)}"
        )

    schema = yaml.safe_load(module.CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(cfg, schema)

    workspace = module.make_workspace(workflow_root=workflow_root, config=cfg)
    return module.cli_main(workspace, argv)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_workflows_dispatcher.py -v
```

Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/__init__.py tests/test_workflows_dispatcher.py
git commit -m "$(cat <<'EOF'
feat(workflows): implement run_cli with YAML load + schema validation

run_cli(workflow_root, argv, require_workflow=) reads
<workflow_root>/config/workflow.yaml, looks up the workflow by name,
checks schema-version compatibility, validates the config against the
workflow's JSON Schema via jsonschema, and hands off to the module's
cli_main. The require_workflow kwarg lets the per-workflow direct form
pin a module regardless of what the YAML declares.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 1.5: Implement `workflows/__main__.py` (generic CLI entrypoint)

**Files:**
- Create: `workflows/__main__.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_workflows_dispatcher.py`:

```python
def test_main_parses_workflow_root_flag_and_invokes_run_cli(tmp_path, monkeypatch, capsys):
    _write_stub_workflow(tmp_path, name="demo-wf")
    workspace_root = tmp_path / "workspace"
    (workspace_root / "config").mkdir(parents=True)
    (workspace_root / "config" / "workflow.yaml").write_text(
        "workflow: demo-wf\nschema-version: 1\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows_main = importlib.import_module("workflows.__main__")
    code = workflows_main.main([
        "--workflow-root", str(workspace_root),
        "status", "--json",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "ran demo-wf with argv=['status', '--json']" in out


def test_main_uses_env_fallback_when_no_workflow_root_flag(tmp_path, monkeypatch, capsys):
    _write_stub_workflow(tmp_path, name="demo-wf")
    workspace_root = tmp_path / "workspace"
    (workspace_root / "config").mkdir(parents=True)
    (workspace_root / "config" / "workflow.yaml").write_text(
        "workflow: demo-wf\nschema-version: 1\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("YOYOPOD_WORKFLOW_ROOT", str(workspace_root))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows_main = importlib.import_module("workflows.__main__")
    code = workflows_main.main(["tick"])
    assert code == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_workflows_dispatcher.py::test_main_parses_workflow_root_flag_and_invokes_run_cli -v
```

Expected: `ModuleNotFoundError: No module named 'workflows.__main__'`.

- [ ] **Step 3: Create `workflows/__main__.py`**

```python
"""Plugin-level CLI entrypoint for the workflow dispatcher.

Invocation:

    python3 -m workflows --workflow-root <path> <subcommand> [args ...]

If ``--workflow-root`` is omitted, the entrypoint honors these env vars
(first match wins): ``YOYOPOD_WORKFLOW_ROOT``, ``HERMES_RELAY_WORKFLOW_ROOT``.
If neither is set, ``~/.hermes/workflows/yoyopod`` is used as a last-resort
default (matches the historical layout).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from workflows import run_cli


_WORKFLOW_ROOT_ENV_VARS = ("YOYOPOD_WORKFLOW_ROOT", "HERMES_RELAY_WORKFLOW_ROOT")


def _resolve_workflow_root(argv: list[str]) -> tuple[Path, list[str]]:
    """Peel --workflow-root / --workflow-root=<path> out of argv; env fallback."""
    out: list[str] = []
    workflow_root: Path | None = None
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--workflow-root":
            if i + 1 >= len(argv):
                raise SystemExit("--workflow-root requires a path argument")
            workflow_root = Path(argv[i + 1]).expanduser().resolve()
            i += 2
            continue
        if arg.startswith("--workflow-root="):
            workflow_root = Path(arg.split("=", 1)[1]).expanduser().resolve()
            i += 1
            continue
        out.append(arg)
        i += 1

    if workflow_root is None:
        for env_var in _WORKFLOW_ROOT_ENV_VARS:
            value = os.environ.get(env_var)
            if value:
                workflow_root = Path(value).expanduser().resolve()
                break
    if workflow_root is None:
        workflow_root = (Path.home() / ".hermes" / "workflows" / "yoyopod").resolve()
    return workflow_root, out


def main(argv: list[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    workflow_root, command_argv = _resolve_workflow_root(raw)
    try:
        return run_cli(workflow_root, command_argv)
    except subprocess.CalledProcessError as exc:
        msg = f"Command failed with exit status {exc.returncode}"
        if exc.stderr:
            msg += f"\n{exc.stderr.strip()}"
        print(msg, file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_workflows_dispatcher.py -v
```

Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/__main__.py tests/test_workflows_dispatcher.py
git commit -m "$(cat <<'EOF'
feat(workflows): add generic CLI entrypoint (python3 -m workflows ...)

Parses --workflow-root (or =path form), falls back to YOYOPOD_WORKFLOW_ROOT /
HERMES_RELAY_WORKFLOW_ROOT env vars, then to ~/.hermes/workflows/yoyopod as
the default. Delegates to workflows.run_cli. Surfaces CalledProcessError as
a non-zero exit with a readable message.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Phase 1 verification

- [ ] **Run the full suite**

```bash
cd /home/radxa/WS/hermes-relay
python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q
```

Expected: all prior 203 tests still pass; add 10 new dispatcher tests; total ≥ 213 passed.

---

## Phase 2 — Copy `adapters/yoyopod_core/` → `workflows/code_review/`

Literal copy of 14 modules + import rewrite, add the five contract attributes, bundle prompt templates, write a placeholder JSON Schema, copy the 15 test files with updated imports. Both `adapters/yoyopod_core/` and `workflows/code_review/` exist and pass tests after this phase.

### Task 2.1: Copy the adapter package to `workflows/code_review/`

**Files:**
- Create: `workflows/code_review/*` (14 modules copied)

- [ ] **Step 1: Copy the directory**

```bash
cd /home/radxa/WS/hermes-relay
cp -r adapters/yoyopod_core workflows/code_review
```

- [ ] **Step 2: Rewrite internal imports**

```bash
cd /home/radxa/WS/hermes-relay
find workflows/code_review -name "*.py" -not -name "__pycache__*" -exec sed -i \
  -e 's|from adapters\.yoyopod_core|from workflows.code_review|g' \
  -e 's|import adapters\.yoyopod_core|import workflows.code_review|g' \
  -e 's|"adapters\.yoyopod_core|"workflows.code_review|g' \
  {} +
```

- [ ] **Step 3: Sanity-check the rewrite**

```bash
grep -rn "adapters\.yoyopod_core" workflows/code_review/
```

Expected: no matches (empty output, exit 1 from grep).

```bash
grep -rn "workflows\.code_review" workflows/code_review/ | head -5
```

Expected: several matches in `actions.py`, `status.py`, `workspace.py`, etc.

- [ ] **Step 4: Clean any __pycache__**

```bash
find workflows/code_review -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
```

- [ ] **Step 5: Commit (no tests yet; verification comes in Task 2.5)**

```bash
git add workflows/code_review/
git commit -m "$(cat <<'EOF'
refactor(workflows): copy adapters/yoyopod_core/ to workflows/code_review/

Literal copy of all 14 modules (__init__.py, __main__.py, actions.py,
cli.py, github.py, health.py, orchestrator.py, paths.py, prompts.py,
reviews.py, sessions.py, status.py, workflow.py, workspace.py). Internal
imports rewritten from adapters.yoyopod_core.* to workflows.code_review.*.

Both paths exist and are functional for this phase; adapters/ is deleted
in a later slice once external callers have been rewired.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2.2: Add the five contract attributes to `workflows/code_review/__init__.py`

**Files:**
- Modify: `workflows/code_review/__init__.py`
- Create: `workflows/code_review/schema.yaml` (minimal placeholder)
- Create: `tests/test_workflows_code_review_init.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_workflows_code_review_init.py`:

```python
import importlib
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_code_review_package_exposes_all_five_contract_attributes():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    module = importlib.import_module("workflows.code_review")

    assert module.NAME == "code-review"
    assert isinstance(module.SUPPORTED_SCHEMA_VERSIONS, tuple)
    assert 1 in module.SUPPORTED_SCHEMA_VERSIONS
    assert isinstance(module.CONFIG_SCHEMA_PATH, Path)
    assert module.CONFIG_SCHEMA_PATH.exists(), f"schema.yaml missing at {module.CONFIG_SCHEMA_PATH}"
    assert callable(module.make_workspace)
    assert callable(module.cli_main)


def test_code_review_load_workflow_succeeds():
    """The dispatcher must be able to load this workflow without error."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    workflows = importlib.import_module("workflows")
    module = workflows.load_workflow("code-review")
    assert module.NAME == "code-review"
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_workflows_code_review_init.py -v
```

Expected: FAIL with `AttributeError: module 'workflows.code_review' has no attribute 'NAME'`.

- [ ] **Step 3: Add the attributes**

Current `workflows/code_review/__init__.py` is likely just a docstring copied from `adapters/yoyopod_core/__init__.py`. Read it first:

```bash
cat workflows/code_review/__init__.py
```

Then rewrite (keep any existing docstring, add the contract attributes at the bottom):

```python
"""YoYoPod Core code-review workflow — plugin adapter package.

(retain original docstring from the copy, if any)
"""
from pathlib import Path

NAME = "code-review"
SUPPORTED_SCHEMA_VERSIONS = (1,)
CONFIG_SCHEMA_PATH = Path(__file__).parent / "schema.yaml"

# Re-export the two contract callables from their implementation modules.
from workflows.code_review.workspace import (
    load_workspace_from_config as _load_workspace_from_config,
)
from workflows.code_review.cli import main as cli_main


def make_workspace(*, workflow_root: Path, config: dict):
    """Plugin-contract factory. In this phase it ignores ``config`` and reads
    the workspace's live config file via ``load_workspace_from_config``; Phase 4
    replaces this with a factory that consumes ``config`` directly."""
    return _load_workspace_from_config(workspace_root=workflow_root)


__all__ = [
    "NAME",
    "SUPPORTED_SCHEMA_VERSIONS",
    "CONFIG_SCHEMA_PATH",
    "make_workspace",
    "cli_main",
]
```

- [ ] **Step 4: Create a minimal placeholder schema**

Create `workflows/code_review/schema.yaml`:

```yaml
# Code-Review workflow config schema (placeholder — full schema lands in Phase 4).
# For now this only enforces the dispatcher handshake fields so load_workflow
# + run_cli can validate. The real per-field schema arrives alongside the
# JSON → YAML config migration.
$schema: http://json-schema.org/draft-07/schema#
title: code-review workflow config (placeholder)
type: object
required: [workflow, schema-version]
properties:
  workflow:
    const: code-review
  schema-version:
    type: integer
    enum: [1]
additionalProperties: true
```

- [ ] **Step 5: Run tests to verify they pass + commit**

```bash
python3 -m pytest tests/test_workflows_code_review_init.py -v
```

Expected: 2 PASS.

```bash
git add workflows/code_review/__init__.py workflows/code_review/schema.yaml tests/test_workflows_code_review_init.py
git commit -m "$(cat <<'EOF'
feat(workflows/code-review): declare contract attributes + placeholder schema

Adds NAME='code-review', SUPPORTED_SCHEMA_VERSIONS=(1,),
CONFIG_SCHEMA_PATH, make_workspace, cli_main to
workflows/code_review/__init__.py so it satisfies the plugin contract.

schema.yaml is a placeholder that only validates the dispatcher-level
keys (workflow + schema-version); the full per-field schema lands in
Phase 4 alongside the JSON-to-YAML config migration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2.3: Rewrite `workflows/code_review/__main__.py` for the per-workflow direct form

**Files:**
- Modify: `workflows/code_review/__main__.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_workflows_code_review_init.py`:

```python
def test_code_review_main_pins_workflow_via_require_workflow(tmp_path, monkeypatch):
    """workflows.code_review.__main__ must pass require_workflow='code-review' to run_cli."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for mod in list(sys.modules):
        if mod == "workflows" or mod.startswith("workflows."):
            del sys.modules[mod]

    import workflows
    workspace_root = tmp_path / "workspace"
    (workspace_root / "config").mkdir(parents=True)
    (workspace_root / "config" / "workflow.yaml").write_text(
        "workflow: some-other-workflow\nschema-version: 1\n",
        encoding="utf-8",
    )

    main_mod = importlib.import_module("workflows.code_review.__main__")
    with pytest.raises(workflows.WorkflowContractError) as exc:
        main_mod.main(["--workflow-root", str(workspace_root), "status"])
    assert "require_workflow='code-review'" in str(exc.value)
```

Also add `import pytest` at the top of the file if not already present.

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_workflows_code_review_init.py::test_code_review_main_pins_workflow_via_require_workflow -v
```

Expected: FAIL — the current `__main__.py` was copied from `adapters/yoyopod_core/__main__.py` and does not yet use `require_workflow`.

- [ ] **Step 3: Rewrite `workflows/code_review/__main__.py`**

```python
"""Per-workflow direct-form entrypoint for the code-review workflow.

Invocation:

    python3 -m workflows.code_review --workflow-root <path> <cmd>

This form pins the workflow module to code-review regardless of what the
YAML declares. Used by developers + tests to force a specific module.
Normal operators should use the generic form instead:

    python3 -m workflows --workflow-root <path> <cmd>
"""
from __future__ import annotations

import subprocess
import sys

from workflows import run_cli
from workflows.__main__ import _resolve_workflow_root


def main(argv: list[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    workflow_root, command_argv = _resolve_workflow_root(raw)
    try:
        return run_cli(workflow_root, command_argv, require_workflow="code-review")
    except subprocess.CalledProcessError as exc:
        msg = f"Command failed with exit status {exc.returncode}"
        if exc.stderr:
            msg += f"\n{exc.stderr.strip()}"
        print(msg, file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify it passes + full init-test suite**

```bash
python3 -m pytest tests/test_workflows_code_review_init.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/code_review/__main__.py tests/test_workflows_code_review_init.py
git commit -m "$(cat <<'EOF'
feat(workflows/code-review): per-workflow direct-form entrypoint pins via require_workflow

workflows.code_review.__main__ calls run_cli(..., require_workflow='code-review').
Running it against a workspace whose workflow.yaml declares a different
workflow raises WorkflowContractError with both the expected and actual
names — useful for developers and test harnesses that need to pin the module.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2.4: Copy test files to `tests/test_workflows_code_review_*.py` with import rewrites

**Files:**
- Create: `tests/test_workflows_code_review_*.py` (15 files)

- [ ] **Step 1: Bulk-copy the test files**

```bash
cd /home/radxa/WS/hermes-relay
for f in tests/test_yoyopod_core_*.py; do
  newname="${f/test_yoyopod_core_/test_workflows_code_review_}"
  cp "$f" "$newname"
done
ls tests/test_workflows_code_review_*.py | wc -l
```

Expected: `15`.

- [ ] **Step 2: Rewrite the module paths**

```bash
find tests -name "test_workflows_code_review_*.py" -exec sed -i \
  -e 's|adapters/yoyopod_core|workflows/code_review|g' \
  -e 's|adapters\.yoyopod_core|workflows.code_review|g' \
  -e 's|"hermes_relay_yoyopod_core|"hermes_relay_workflows_code_review|g' \
  {} +
```

- [ ] **Step 3: Verify grep shows no leaks**

```bash
grep -n "adapters/yoyopod_core\|adapters\.yoyopod_core\|hermes_relay_yoyopod_core" tests/test_workflows_code_review_*.py | head
```

Expected: empty output.

- [ ] **Step 4: Run the new test suite**

```bash
python3 -m pytest tests/test_workflows_code_review_ -q 2>&1 | tail -10
```

Expected: the new 15 files run, ~203 tests pass (identical to the adapters-side suite). If any fail, inspect their imports — the sed above targets the common patterns; rare cases may need manual fixup.

Then confirm the **old** tests still pass too:

```bash
python3 -m pytest tests/test_yoyopod_core_ -q 2>&1 | tail -5
```

Expected: 203 tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_workflows_code_review_*.py
git commit -m "$(cat <<'EOF'
test(workflows/code-review): copy tests/test_yoyopod_core_*.py verbatim with path rewrites

Every adapters-side test now has a workflows-side twin that exercises
the exact same assertions against workflows/code_review/. Both suites
pass independently; adapters/ is deleted in a later slice.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 2.5: Externalize the inline prompt templates

The current `workflows/code_review/prompts.py` inlines ~3 large prompt templates as triple-quoted strings. Bundle them as Markdown files under `workflows/code_review/prompts/`.

**Files:**
- Create: `workflows/code_review/prompts/internal-review-strict.md`
- Create: `workflows/code_review/prompts/coder-dispatch.md`
- Create: `workflows/code_review/prompts/repair-handoff.md`
- Modify: `workflows/code_review/prompts.py` (load templates from `prompts/*.md` instead of inlining)

Note: Phase 2 keeps the prompt logic **unchanged** — we only externalize the template text. The `prompts:` section of the YAML (which selects a variant by name) lands in Phase 4.

- [ ] **Step 1: Inspect existing inline prompts**

```bash
grep -nE "^def render_" workflows/code_review/prompts.py
```

List the three template-returning functions (typically `render_internal_review_strict_prompt`, `render_coder_dispatch_prompt`, `render_repair_handoff_prompt` — names may differ; note the exact ones).

- [ ] **Step 2: Write a failing test for template loading**

Append to `tests/test_workflows_code_review_prompts.py` (if the file exists from the copy; else create):

```python
from pathlib import Path

import importlib
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_prompt_templates_bundle_exists_with_three_files():
    bundle = REPO_ROOT / "workflows" / "code_review" / "prompts"
    assert bundle.is_dir(), f"prompts bundle missing at {bundle}"
    names = sorted(p.name for p in bundle.glob("*.md"))
    assert names == [
        "coder-dispatch.md",
        "internal-review-strict.md",
        "repair-handoff.md",
    ]
```

- [ ] **Step 3: Run to verify it fails**

```bash
python3 -m pytest tests/test_workflows_code_review_prompts.py::test_prompt_templates_bundle_exists_with_three_files -v
```

Expected: FAIL — bundle dir does not exist.

- [ ] **Step 4: Extract the inline strings to Markdown files**

For each template-returning function in `workflows/code_review/prompts.py`:

1. Copy the multi-line string body verbatim into a new `workflows/code_review/prompts/<name>.md`.
2. Rewrite the function to load the file:

```python
_PROMPT_BUNDLE = Path(__file__).parent / "prompts"


def _load_template(name: str) -> str:
    return (_PROMPT_BUNDLE / f"{name}.md").read_text(encoding="utf-8")


def render_internal_review_strict_prompt(**kwargs) -> str:
    return _load_template("internal-review-strict").format(**kwargs)


def render_coder_dispatch_prompt(**kwargs) -> str:
    return _load_template("coder-dispatch").format(**kwargs)


def render_repair_handoff_prompt(**kwargs) -> str:
    return _load_template("repair-handoff").format(**kwargs)
```

If the existing renderers use string concatenation rather than `.format()`, preserve that pattern — just swap the source of the template string.

Preserve all existing function signatures and call-sites. The only change is where the template text comes from.

- [ ] **Step 5: Run full code-review test suite**

```bash
python3 -m pytest tests/test_workflows_code_review_ -q 2>&1 | tail -5
```

Expected: all prior tests still pass. If any fail, the template extraction probably lost a character (trailing newline, interpolation placeholder) — diff the Markdown file against the original inline string.

- [ ] **Step 6: Commit**

```bash
git add workflows/code_review/prompts/ workflows/code_review/prompts.py tests/test_workflows_code_review_prompts.py
git commit -m "$(cat <<'EOF'
refactor(workflows/code-review): externalize prompt templates to prompts/*.md

Three inline prompt templates (internal-review-strict, coder-dispatch,
repair-handoff) move from triple-quoted strings in prompts.py to
individual Markdown files under workflows/code_review/prompts/. The
renderer functions in prompts.py now load templates via read_text().

This sets up Phase 4's YAML 'prompts:' section, which will pick a
variant by filename. For now the selection is still hardcoded.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Phase 2 verification

- [ ] **Run the full suite**

```bash
cd /home/radxa/WS/hermes-relay
python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q
```

Expected: 203 adapters-side tests + 203 workflows-side tests + 10 dispatcher tests + 3 code-review init tests ≈ 419 passed (some tests may be shared via common fixtures so slight variance is OK). No failures.

- [ ] **Smoke-test the new CLI paths**

```bash
cd /home/radxa/WS/hermes-relay
python3 -m workflows.code_review --workflow-root /home/radxa/.hermes/workflows/yoyopod status 2>&1 | head -4
```

Note: this may fail at the schema-validation step because the placeholder schema only validates the top-level handshake keys, and the live config is still JSON, not YAML. That's expected in Phase 2; the full YAML migration is Phase 4. To smoke-test the dispatch path without the live workspace, you can point at a synthetic workspace:

```bash
mkdir -p /tmp/wf-smoke/config
cat > /tmp/wf-smoke/config/workflow.yaml <<'EOF'
workflow: code-review
schema-version: 1
EOF
python3 -m workflows.code_review --workflow-root /tmp/wf-smoke status 2>&1 | head -10
```

Expected: some error from inside `cli_main` (likely about missing live workspace files), but the dispatcher + schema validation + make_workspace factory plumbing all runs. If the error is a dispatcher/validation error (`WorkflowContractError` or `jsonschema.ValidationError`), fix before proceeding.

---

## Phase 3 — Extract the Runtime protocol

Introduce `workflows/code_review/runtimes/` with a `Runtime` Protocol and two implementations: `AcpxCodexRuntime` (wraps existing `acpx codex` session helpers) and `ClaudeCliRuntime` (wraps the one-shot `claude` CLI invocation). Rewire `sessions.py` + `reviews.py` callers to use `ws.runtime(name)`.

### Task 3.1: Define the `Runtime` Protocol and helper types

**Files:**
- Create: `workflows/code_review/runtimes/__init__.py`
- Create: `tests/test_workflows_code_review_runtimes_init.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_workflows_code_review_runtimes_init.py`:

```python
from pathlib import Path


def test_runtime_protocol_declares_four_methods():
    from workflows.code_review.runtimes import Runtime

    # Protocol bodies are duck-typed; we verify the required method names exist
    # in the Protocol's namespace.
    required = {"ensure_session", "run_prompt", "assess_health", "close_session"}
    declared = {name for name in dir(Runtime) if not name.startswith("_")}
    missing = required - declared
    assert not missing, f"Runtime protocol missing methods: {missing}"


def test_build_runtimes_returns_empty_dict_when_config_is_empty():
    from workflows.code_review.runtimes import build_runtimes

    assert build_runtimes({}) == {}
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_workflows_code_review_runtimes_init.py -v
```

Expected: `ModuleNotFoundError: No module named 'workflows.code_review.runtimes'`.

- [ ] **Step 3: Create the runtimes package**

```python
# workflows/code_review/runtimes/__init__.py
"""Runtime abstractions for the code-review workflow.

A Runtime encapsulates *how we talk to a model*: persistent ACPX session
management for Codex, one-shot subprocess invocation for Claude CLI,
plain HTTP request/response for future providers like Kimi or Gemini.

Agents in the YAML config reference runtimes by name; the workspace
factory instantiates one Runtime per named profile and exposes them via
``ws.runtime(name)``.

To add a new runtime kind:

1. Create a new module under ``workflows/code_review/runtimes/<kind>.py``
   whose primary export is a class implementing the ``Runtime`` protocol.
2. Register the class in ``_RUNTIME_KINDS`` below.
3. Add a corresponding branch to ``workflows/code_review/schema.yaml``
   so the YAML config validator knows what shape your kind accepts.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SessionHandle:
    record_id: str | None
    session_id: str | None
    name: str


@dataclass(frozen=True)
class SessionHealth:
    healthy: bool
    reason: str | None
    last_used_at: str | None


@runtime_checkable
class Runtime(Protocol):
    """Protocol every runtime kind implements.

    One-shot runtimes (e.g. claude-cli) implement ensure_session /
    close_session as no-ops and return a synthetic SessionHandle.
    """

    def ensure_session(
        self,
        *,
        worktree: Path,
        session_name: str,
        model: str,
        resume_session_id: str | None = None,
    ) -> SessionHandle: ...

    def run_prompt(
        self,
        *,
        worktree: Path,
        session_name: str,
        prompt: str,
        model: str,
    ) -> str: ...

    def assess_health(
        self,
        session_meta: dict | None,
        *,
        worktree: Path | None,
        now_epoch: int | None = None,
    ) -> SessionHealth: ...

    def close_session(
        self,
        *,
        worktree: Path,
        session_name: str,
    ) -> None: ...


_RUNTIME_KINDS: dict[str, type] = {}


def register(kind: str):
    """Decorator: registers a class as the implementation for a runtime kind."""

    def _register(cls):
        _RUNTIME_KINDS[kind] = cls
        return cls

    return _register


def build_runtimes(runtimes_cfg: dict, *, run=None, run_json=None) -> dict[str, Runtime]:
    """Instantiate one Runtime per profile in ``runtimes_cfg``.

    ``runtimes_cfg`` is the dict parsed from the YAML ``runtimes:`` section:
    ``{profile-name: {kind: <kind>, ...profile-specific keys...}}``.

    ``run`` / ``run_json`` are workspace-scoped subprocess primitives — the
    runtime implementations accept them via constructor args so tests can
    inject fakes without mocking subprocess globally.

    The concrete runtime classes are imported lazily here so that merely
    importing ``workflows.code_review.runtimes`` does not pull in acpx_codex
    or claude_cli until they're actually needed.
    """
    # Trigger registration side-effects by importing the runtime modules.
    from workflows.code_review.runtimes import acpx_codex  # noqa: F401
    from workflows.code_review.runtimes import claude_cli  # noqa: F401

    out: dict[str, Runtime] = {}
    for profile_name, profile_cfg in runtimes_cfg.items():
        kind = profile_cfg.get("kind")
        if kind not in _RUNTIME_KINDS:
            raise ValueError(
                f"runtime profile {profile_name!r} declares unknown kind={kind!r}; "
                f"registered kinds: {sorted(_RUNTIME_KINDS)}"
            )
        cls = _RUNTIME_KINDS[kind]
        out[profile_name] = cls(profile_cfg, run=run, run_json=run_json)
    return out
```

- [ ] **Step 4: Run tests (the build_runtimes empty case should pass; Runtime protocol test passes; runtime-module imports will not yet resolve)**

We expect the `build_runtimes({})` test to pass (no iteration, no import). The `test_runtime_protocol_declares_four_methods` test should pass now. Run:

```bash
python3 -m pytest tests/test_workflows_code_review_runtimes_init.py -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/code_review/runtimes/__init__.py tests/test_workflows_code_review_runtimes_init.py
git commit -m "$(cat <<'EOF'
feat(workflows/code-review): introduce Runtime protocol + runtimes package skeleton

Runtime is a Protocol with four methods (ensure_session, run_prompt,
assess_health, close_session). SessionHandle + SessionHealth are frozen
dataclasses. A decorator-based registry (_RUNTIME_KINDS + @register)
keeps the protocol implementations decoupled from the builder.

build_runtimes() iterates a YAML 'runtimes:' section and instantiates
one Runtime per named profile. Concrete implementations (acpx-codex,
claude-cli) land in the next tasks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3.2: Implement `AcpxCodexRuntime`

Wraps today's `ensure_acpx_session` / `run_acpx_prompt` / `close_acpx_session` / session-health assessment from `sessions.py`.

**Files:**
- Create: `workflows/code_review/runtimes/acpx_codex.py`
- Create: `tests/test_workflows_code_review_runtimes_acpx_codex.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_workflows_code_review_runtimes_acpx_codex.py`:

```python
from pathlib import Path

import pytest


def _make_runtime(**cfg_overrides):
    from workflows.code_review.runtimes.acpx_codex import AcpxCodexRuntime

    cfg = {
        "kind": "acpx-codex",
        "session-idle-freshness-seconds": 900,
        "session-idle-grace-seconds": 1800,
        "session-nudge-cooldown-seconds": 600,
        **cfg_overrides,
    }
    calls = []

    def fake_run(cmd, cwd=None, **kwargs):
        calls.append(("run", cmd, str(cwd) if cwd else None))
        class R:
            stdout = ""
            stderr = ""
            returncode = 0
        return R()

    def fake_run_json(cmd, cwd=None, **kwargs):
        calls.append(("run_json", cmd, str(cwd) if cwd else None))
        return {"name": "lane-224", "closed": False}

    runtime = AcpxCodexRuntime(cfg, run=fake_run, run_json=fake_run_json)
    return runtime, calls


def test_ensure_session_invokes_acpx_with_model_and_session_name(tmp_path):
    runtime, calls = _make_runtime()
    handle = runtime.ensure_session(
        worktree=tmp_path,
        session_name="lane-224",
        model="gpt-5.3-codex-spark/high",
    )
    run_json_calls = [c for c in calls if c[0] == "run_json"]
    assert run_json_calls, "ensure_session must invoke acpx via run_json"
    cmd = run_json_calls[0][1]
    assert "acpx" in cmd[0] or cmd[0].endswith("/acpx")
    assert "codex" in cmd
    assert "lane-224" in cmd
    assert handle.name == "lane-224"


def test_run_prompt_forwards_prompt_to_acpx_codex(tmp_path):
    runtime, calls = _make_runtime()
    runtime.run_prompt(
        worktree=tmp_path,
        session_name="lane-224",
        prompt="do the thing",
        model="gpt-5.3-codex-spark/high",
    )
    run_calls = [c for c in calls if c[0] == "run"]
    assert run_calls, "run_prompt must invoke acpx via run"
    cmd = run_calls[0][1]
    assert "codex" in cmd
    assert "prompt" in cmd
    assert "lane-224" in cmd


def test_close_session_invokes_acpx_close(tmp_path):
    runtime, calls = _make_runtime()
    runtime.close_session(worktree=tmp_path, session_name="lane-224")
    run_calls = [c for c in calls if c[0] == "run"]
    assert run_calls, "close_session must call acpx"
    cmd = run_calls[0][1]
    assert "close" in cmd or any("close" in str(p) for p in cmd)


def test_assess_health_reports_fresh_when_last_used_is_recent(tmp_path):
    runtime, _ = _make_runtime()
    meta = {"last_used_at": "2026-04-24T12:00:00Z", "name": "lane-224", "closed": False}
    health = runtime.assess_health(
        meta,
        worktree=tmp_path,
        now_epoch=1714,  # arbitrary; test logic in assess_health
    )
    # Health object shape; the specific 'healthy' value depends on epoch math.
    assert hasattr(health, "healthy")
    assert hasattr(health, "reason")
    assert hasattr(health, "last_used_at")


def test_assess_health_marks_closed_session_unhealthy(tmp_path):
    runtime, _ = _make_runtime()
    meta = {"last_used_at": "2026-04-24T12:00:00Z", "name": "lane-224", "closed": True}
    health = runtime.assess_health(meta, worktree=tmp_path)
    assert health.healthy is False
    assert "closed" in (health.reason or "").lower()


def test_assess_health_returns_unhealthy_when_meta_is_none(tmp_path):
    runtime, _ = _make_runtime()
    health = runtime.assess_health(None, worktree=tmp_path)
    assert health.healthy is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_workflows_code_review_runtimes_acpx_codex.py -v
```

Expected: `ModuleNotFoundError: No module named 'workflows.code_review.runtimes.acpx_codex'`.

- [ ] **Step 3: Implement the runtime**

Inspect current `workflows/code_review/sessions.py` for the exact shapes of `ensure_acpx_session`, `run_acpx_prompt`, `close_acpx_session`, `assess_codex_session_health`. Port those bodies into methods:

```python
# workflows/code_review/runtimes/acpx_codex.py
"""Persistent-session runtime for Codex via `acpx codex`."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from workflows.code_review.runtimes import (
    Runtime,
    SessionHandle,
    SessionHealth,
    register,
)


@register("acpx-codex")
class AcpxCodexRuntime:
    """Wraps the `acpx codex` CLI to manage long-lived Codex sessions.

    Config shape (YAML):
        kind: acpx-codex
        session-idle-freshness-seconds: 900
        session-idle-grace-seconds: 1800
        session-nudge-cooldown-seconds: 600
    """

    def __init__(self, cfg: dict, *, run, run_json):
        self._cfg = cfg
        self._run = run
        self._run_json = run_json
        self._freshness = int(cfg.get("session-idle-freshness-seconds", 900))
        self._grace = int(cfg.get("session-idle-grace-seconds", 1800))
        self._nudge_cooldown = int(cfg.get("session-nudge-cooldown-seconds", 600))

    def ensure_session(
        self,
        *,
        worktree: Path,
        session_name: str,
        model: str,
        resume_session_id: str | None = None,
    ) -> SessionHandle:
        # Port the body of workflows.code_review.sessions.ensure_acpx_session
        # here, replacing calls to the injected run_json parameter.
        cmd = ["acpx", "codex", "sessions", "ensure", "--name", session_name, "--model", model]
        if resume_session_id:
            cmd.extend(["--resume-session", resume_session_id])
        payload = self._run_json(cmd, cwd=worktree)
        return SessionHandle(
            record_id=payload.get("acpxRecordId") or payload.get("acpx_record_id"),
            session_id=payload.get("acpSessionId") or payload.get("acpxSessionId"),
            name=payload.get("name") or session_name,
        )

    def run_prompt(
        self,
        *,
        worktree: Path,
        session_name: str,
        prompt: str,
        model: str,
    ) -> str:
        # Port the body of workflows.code_review.sessions.run_acpx_prompt
        cmd = ["acpx", "codex", "prompt", "-s", session_name, "--model", model, prompt]
        completed = self._run(cmd, cwd=worktree)
        return getattr(completed, "stdout", "") or ""

    def assess_health(
        self,
        session_meta: dict | None,
        *,
        worktree: Path | None,
        now_epoch: int | None = None,
    ) -> SessionHealth:
        # Port the body of workflows.code_review.sessions.assess_codex_session_health
        # using self._freshness / self._grace for thresholds. When meta is None or
        # session is closed, return unhealthy.
        if session_meta is None:
            return SessionHealth(healthy=False, reason="missing-session-meta", last_used_at=None)
        if session_meta.get("closed"):
            return SessionHealth(
                healthy=False,
                reason="session-closed",
                last_used_at=session_meta.get("last_used_at"),
            )
        # The existing helper returns a dict; wrap it.
        from workflows.code_review.sessions import assess_codex_session_health
        legacy_health = assess_codex_session_health(
            session_meta,
            worktree,
            now_epoch=now_epoch,
            freshness_seconds=self._freshness,
            poke_grace_seconds=self._grace,
        )
        return SessionHealth(
            healthy=bool(legacy_health.get("healthy")),
            reason=legacy_health.get("reason"),
            last_used_at=legacy_health.get("lastUsedAt"),
        )

    def close_session(self, *, worktree: Path, session_name: str) -> None:
        # Port workflows.code_review.sessions.close_acpx_session
        cmd = ["acpx", "codex", "sessions", "close", "--name", session_name]
        self._run(cmd, cwd=worktree)
```

- [ ] **Step 4: Run the tests**

```bash
python3 -m pytest tests/test_workflows_code_review_runtimes_acpx_codex.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/code_review/runtimes/acpx_codex.py tests/test_workflows_code_review_runtimes_acpx_codex.py
git commit -m "$(cat <<'EOF'
feat(workflows/code-review): AcpxCodexRuntime implementing Runtime protocol

Registers kind='acpx-codex'. Wraps the acpx codex CLI with the four
protocol methods (ensure_session, run_prompt, assess_health,
close_session). Thresholds (session-idle-freshness-seconds,
session-idle-grace-seconds, session-nudge-cooldown-seconds) come from
the runtime profile config, not globally. Reuses the existing
assess_codex_session_health helper from sessions.py for the health
computation; future slices can collapse that helper into this class.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3.3: Implement `ClaudeCliRuntime`

One-shot runtime that wraps the `claude` CLI invocation currently inlined in `reviews.run_inter_review_agent_review`.

**Files:**
- Create: `workflows/code_review/runtimes/claude_cli.py`
- Create: `tests/test_workflows_code_review_runtimes_claude_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workflows_code_review_runtimes_claude_cli.py
from pathlib import Path


def _make_runtime(**cfg_overrides):
    from workflows.code_review.runtimes.claude_cli import ClaudeCliRuntime

    cfg = {
        "kind": "claude-cli",
        "max-turns-per-invocation": 24,
        "timeout-seconds": 1200,
        **cfg_overrides,
    }
    calls = []

    def fake_run(cmd, cwd=None, **kwargs):
        calls.append(("run", cmd, str(cwd) if cwd else None, kwargs))
        class R:
            stdout = "claude said hi"
            stderr = ""
            returncode = 0
        return R()

    return ClaudeCliRuntime(cfg, run=fake_run, run_json=None), calls


def test_ensure_session_is_a_noop_and_returns_synthetic_handle(tmp_path):
    runtime, calls = _make_runtime()
    handle = runtime.ensure_session(
        worktree=tmp_path,
        session_name="inter-review-agent:abc",
        model="claude-sonnet-4-6",
    )
    assert calls == []
    assert handle.name == "inter-review-agent:abc"
    assert handle.session_id is None
    assert handle.record_id is None


def test_close_session_is_a_noop(tmp_path):
    runtime, calls = _make_runtime()
    runtime.close_session(worktree=tmp_path, session_name="anything")
    assert calls == []


def test_assess_health_is_always_healthy_for_oneshot_runtime(tmp_path):
    runtime, _ = _make_runtime()
    health = runtime.assess_health({}, worktree=tmp_path)
    assert health.healthy is True


def test_run_prompt_invokes_claude_cli_with_model_and_max_turns(tmp_path):
    runtime, calls = _make_runtime()
    out = runtime.run_prompt(
        worktree=tmp_path,
        session_name="inter-review-agent:abc",
        prompt="review this",
        model="claude-sonnet-4-6",
    )
    assert out == "claude said hi"
    run_calls = [c for c in calls if c[0] == "run"]
    assert run_calls
    cmd = run_calls[0][1]
    assert cmd[0] == "claude"
    assert "--model" in cmd
    assert "claude-sonnet-4-6" in cmd
    assert "--max-turns" in cmd
    assert "24" in cmd
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_workflows_code_review_runtimes_claude_cli.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement the runtime**

Inspect `workflows/code_review/reviews.py` for the `claude` CLI invocation inside `run_inter_review_agent_review`. Port the command shape into:

```python
# workflows/code_review/runtimes/claude_cli.py
"""One-shot Claude CLI runtime.

No persistent session; ``ensure_session`` and ``close_session`` are no-ops,
``assess_health`` always returns healthy. Each ``run_prompt`` spawns the
``claude`` CLI, feeds the prompt, and returns stdout.
"""
from __future__ import annotations

from pathlib import Path

from workflows.code_review.runtimes import (
    Runtime,
    SessionHandle,
    SessionHealth,
    register,
)


@register("claude-cli")
class ClaudeCliRuntime:
    """Wraps the ``claude`` CLI for one-shot pre-publish / review invocations.

    Config shape (YAML):
        kind: claude-cli
        max-turns-per-invocation: 24
        timeout-seconds: 1200
    """

    def __init__(self, cfg: dict, *, run, run_json=None):
        self._cfg = cfg
        self._run = run
        self._max_turns = int(cfg.get("max-turns-per-invocation", 24))
        self._timeout = int(cfg.get("timeout-seconds", 1200))

    def ensure_session(
        self,
        *,
        worktree: Path,
        session_name: str,
        model: str,
        resume_session_id: str | None = None,
    ) -> SessionHandle:
        return SessionHandle(record_id=None, session_id=None, name=session_name)

    def run_prompt(
        self,
        *,
        worktree: Path,
        session_name: str,
        prompt: str,
        model: str,
    ) -> str:
        cmd = [
            "claude",
            "--model", model,
            "--max-turns", str(self._max_turns),
            "--print",
            prompt,
        ]
        completed = self._run(cmd, cwd=worktree, timeout=self._timeout)
        return getattr(completed, "stdout", "") or ""

    def assess_health(
        self,
        session_meta: dict | None,
        *,
        worktree: Path | None,
        now_epoch: int | None = None,
    ) -> SessionHealth:
        # One-shot runtime: no persistent session to be unhealthy.
        return SessionHealth(healthy=True, reason=None, last_used_at=None)

    def close_session(self, *, worktree: Path, session_name: str) -> None:
        return None
```

**Note on the actual CLI invocation:** cross-check the exact `claude` args used today in `reviews.py::run_inter_review_agent_review`. If they differ (e.g., `--output-format json` or `--dangerously-skip-permissions`), mirror them here. The existing test suite's review-flow tests will fail in Task 3.4 if the invocation shape drifts.

- [ ] **Step 4: Run the tests**

```bash
python3 -m pytest tests/test_workflows_code_review_runtimes_claude_cli.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/code_review/runtimes/claude_cli.py tests/test_workflows_code_review_runtimes_claude_cli.py
git commit -m "$(cat <<'EOF'
feat(workflows/code-review): ClaudeCliRuntime — one-shot Claude-via-CLI runtime

Registers kind='claude-cli'. ensure_session + close_session are no-ops;
assess_health always returns healthy. run_prompt spawns the claude CLI
with --model / --max-turns / --print and the prompt, returning stdout.
Max turns + timeout come from the runtime profile config.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3.4: Expose `ws.runtime(name)` on the workspace accessor

The workspace factory (in `workflows/code_review/workspace.py`) currently passes `_run` / `_run_json` etc. as free primitives. Add a `runtime(name)` method that returns pre-built runtime instances.

**Files:**
- Modify: `workflows/code_review/workspace.py`
- Modify: `tests/test_workflows_code_review_workspace.py` (add runtime test)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_workflows_code_review_workspace.py`:

```python
def test_workspace_exposes_runtime_accessor_with_named_profiles():
    """make_workspace instantiates runtimes from the config's 'runtimes:' section."""
    from workflows.code_review.workspace import load_workspace_from_config

    # For now we load from the live workspace root; Phase 4 exercises YAML.
    workspace_root = Path("/home/radxa/.hermes/workflows/yoyopod")
    if not (workspace_root / "config" / "yoyopod-workflow.json").exists():
        import pytest
        pytest.skip("live workspace config not present")

    ws = load_workspace_from_config(workspace_root=workspace_root)
    # The accessor must expose a `runtime(name)` callable returning a Runtime.
    assert hasattr(ws, "runtime"), "workspace must expose `runtime(name)` accessor"
    acpx = ws.runtime("acpx-codex")
    claude = ws.runtime("claude-cli")
    # Duck-type: they respond to the protocol methods.
    for r in (acpx, claude):
        assert callable(getattr(r, "ensure_session", None))
        assert callable(getattr(r, "run_prompt", None))
        assert callable(getattr(r, "assess_health", None))
        assert callable(getattr(r, "close_session", None))
```

- [ ] **Step 2: Run test, verify fail**

```bash
python3 -m pytest tests/test_workflows_code_review_workspace.py::test_workspace_exposes_runtime_accessor_with_named_profiles -v
```

Expected: `AttributeError: 'SimpleNamespace' object has no attribute 'runtime'`.

- [ ] **Step 3: Add `runtime()` accessor to the workspace factory**

In `workflows/code_review/workspace.py`, locate the `make_workspace` function (or wherever the SimpleNamespace is populated). Add:

```python
# Near the top of the file:
from workflows.code_review.runtimes import build_runtimes

# Inside make_workspace (or load_workspace_from_config), after the namespace
# is populated with _run / _run_json, add:

# Phase 3: hardcode the runtime profiles using the old JSON's session-policy
# settings as a bridge; Phase 4 swaps this for YAML-driven instantiation.
_session_policy = config.get("sessionPolicy", {}) or {}
_review_policy = config.get("reviewPolicy", {}) or {}

_runtimes_cfg = {
    "acpx-codex": {
        "kind": "acpx-codex",
        "session-idle-freshness-seconds": int(_session_policy.get("codexSessionFreshnessSeconds", 900)),
        "session-idle-grace-seconds": int(_session_policy.get("codexSessionPokeGraceSeconds", 1800)),
        "session-nudge-cooldown-seconds": int(_session_policy.get("codexSessionNudgeCooldownSeconds", 600)),
    },
    "claude-cli": {
        "kind": "claude-cli",
        "max-turns-per-invocation": int(
            _review_policy.get("interReviewAgentMaxTurns")
            or _review_policy.get("internalReviewerAgentMaxTurns")
            or _review_policy.get("claudeReviewMaxTurns", 24)
        ),
        "timeout-seconds": int(
            _review_policy.get("interReviewAgentTimeoutSeconds")
            or _review_policy.get("internalReviewerAgentTimeoutSeconds")
            or _review_policy.get("claudeReviewTimeoutSeconds", 1200)
        ),
    },
}

_runtimes = build_runtimes(_runtimes_cfg, run=ns._run, run_json=ns._run_json)

def _runtime_accessor(name: str):
    if name not in _runtimes:
        raise KeyError(f"unknown runtime profile {name!r}; known: {sorted(_runtimes)}")
    return _runtimes[name]

ns.runtime = _runtime_accessor
```

(Exact placement: after `ns = SimpleNamespace(...)` and after `ns._run`, `ns._run_json` are set. The `build_runtimes` call needs `ns._run` / `ns._run_json` already defined.)

- [ ] **Step 4: Run the test**

```bash
python3 -m pytest tests/test_workflows_code_review_workspace.py::test_workspace_exposes_runtime_accessor_with_named_profiles -v
```

Expected: PASS (if the live workspace exists) or SKIP (if not). Run the broader suite too:

```bash
python3 -m pytest tests/test_workflows_code_review_workspace.py -q 2>&1 | tail -5
```

Expected: no regressions from the existing workspace tests.

- [ ] **Step 5: Commit**

```bash
git add workflows/code_review/workspace.py tests/test_workflows_code_review_workspace.py
git commit -m "$(cat <<'EOF'
feat(workflows/code-review): workspace.runtime(name) accessor with acpx + claude-cli

make_workspace now instantiates AcpxCodexRuntime and ClaudeCliRuntime via
build_runtimes() and exposes them via `ws.runtime('acpx-codex')` /
`ws.runtime('claude-cli')`. Runtime profile configs are bridged from the
old JSON's sessionPolicy/reviewPolicy fields; Phase 4 replaces this
bridge with YAML-driven instantiation.

Callers in sessions.py / reviews.py continue to use the free _run /
_run_json primitives for now; Task 3.5 rewires them to use the runtime
accessor.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 3.5: Rewire `sessions.py` + `reviews.py` to use the runtime accessor

**Files:**
- Modify: `workflows/code_review/sessions.py`
- Modify: `workflows/code_review/reviews.py`

- [ ] **Step 1: Write the failing test (integration-level)**

The existing tests in `tests/test_workflows_code_review_sessions.py` and `tests/test_workflows_code_review_reviews.py` already exercise `ensure_acpx_session` / `run_acpx_prompt` / `run_inter_review_agent_review` via mocked primitives. Add a single new test that asserts the workspace runtime accessor is the code path used:

```python
# Append to tests/test_workflows_code_review_sessions.py
def test_ensure_session_routes_through_workspace_runtime_accessor(monkeypatch):
    """sessions.ensure_acpx_session(workspace=..., ...) must resolve the runtime via ws.runtime()."""
    from workflows.code_review.runtimes import SessionHandle
    from workflows.code_review import sessions

    captured = {}

    class FakeRuntime:
        def ensure_session(self, *, worktree, session_name, model, resume_session_id=None):
            captured["called"] = (worktree, session_name, model)
            return SessionHandle(record_id="rec-1", session_id="sess-1", name=session_name)

    class FakeWs:
        def runtime(self, name):
            captured["runtime_name"] = name
            return FakeRuntime()

    handle = sessions.ensure_session_via_runtime(
        workspace=FakeWs(),
        runtime_name="acpx-codex",
        worktree=Path("/tmp/wt"),
        session_name="lane-224",
        model="gpt-5.3-codex-spark/high",
    )
    assert captured["runtime_name"] == "acpx-codex"
    assert captured["called"] == (Path("/tmp/wt"), "lane-224", "gpt-5.3-codex-spark/high")
    assert handle.record_id == "rec-1"
```

- [ ] **Step 2: Run to verify fail**

```bash
python3 -m pytest tests/test_workflows_code_review_sessions.py::test_ensure_session_routes_through_workspace_runtime_accessor -v
```

Expected: `AttributeError: module 'workflows.code_review.sessions' has no attribute 'ensure_session_via_runtime'`.

- [ ] **Step 3: Add the new passthrough wrappers**

Append to `workflows/code_review/sessions.py` (keep the old `ensure_acpx_session` etc. functions intact for back-compat with existing call sites):

```python
def ensure_session_via_runtime(
    *,
    workspace,
    runtime_name: str,
    worktree,
    session_name: str,
    model: str,
    resume_session_id: str | None = None,
):
    """Runtime-aware version of ensure_acpx_session.

    Resolves the runtime via ``workspace.runtime(runtime_name)`` and calls
    its ``ensure_session`` method. New callers should use this form; the
    free ``ensure_acpx_session`` remains for callers that haven't been
    rewired yet.
    """
    runtime = workspace.runtime(runtime_name)
    return runtime.ensure_session(
        worktree=worktree,
        session_name=session_name,
        model=model,
        resume_session_id=resume_session_id,
    )


def run_prompt_via_runtime(
    *,
    workspace,
    runtime_name: str,
    worktree,
    session_name: str,
    prompt: str,
    model: str,
) -> str:
    return workspace.runtime(runtime_name).run_prompt(
        worktree=worktree,
        session_name=session_name,
        prompt=prompt,
        model=model,
    )


def close_session_via_runtime(*, workspace, runtime_name: str, worktree, session_name: str) -> None:
    return workspace.runtime(runtime_name).close_session(
        worktree=worktree,
        session_name=session_name,
    )
```

- [ ] **Step 4: Run the test**

```bash
python3 -m pytest tests/test_workflows_code_review_sessions.py::test_ensure_session_routes_through_workspace_runtime_accessor -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/code_review/sessions.py tests/test_workflows_code_review_sessions.py
git commit -m "$(cat <<'EOF'
feat(workflows/code-review): runtime-aware session helpers (via ws.runtime())

Adds ensure_session_via_runtime / run_prompt_via_runtime /
close_session_via_runtime to sessions.py. They resolve the runtime via
workspace.runtime(name) and delegate. The existing free functions
(ensure_acpx_session, run_acpx_prompt, close_acpx_session) stay in place
until Phase 5's full rewire.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Phase 3 verification

- [ ] **Run the full suite**

```bash
python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -6
```

Expected: previous total + 6 acpx-codex tests + 4 claude-cli tests + 2 runtime-init tests + 1 session-passthrough test + 1 workspace-accessor test ≈ +14 tests. No regressions.

---

## Phase 4 — Switch config from JSON to YAML

Introduce the full `schema.yaml`, write `scripts/migrate_config.py` to convert `yoyopod-workflow.json` → `workflow.yaml`, and teach the workspace factory to consume the new YAML dict.

### Task 4.1: Expand `workflows/code_review/schema.yaml` to the full shape

**Files:**
- Modify: `workflows/code_review/schema.yaml`
- Create: `tests/test_workflows_code_review_schema.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_workflows_code_review_schema.py
from pathlib import Path

import yaml
import jsonschema
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "workflows" / "code_review" / "schema.yaml"


def _load_schema():
    return yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))


def _minimal_valid_config():
    """The smallest YAML that should pass schema validation."""
    return {
        "workflow": "code-review",
        "schema-version": 1,
        "instance": {"name": "yoyopod", "engine-owner": "hermes"},
        "repository": {
            "local-path": "/tmp/repo",
            "github-slug": "owner/repo",
            "active-lane-label": "active-lane",
        },
        "runtimes": {
            "acpx-codex": {
                "kind": "acpx-codex",
                "session-idle-freshness-seconds": 900,
                "session-idle-grace-seconds": 1800,
                "session-nudge-cooldown-seconds": 600,
            },
            "claude-cli": {
                "kind": "claude-cli",
                "max-turns-per-invocation": 24,
                "timeout-seconds": 1200,
            },
        },
        "agents": {
            "coder": {
                "default": {
                    "name": "Internal_Coder_Agent",
                    "model": "gpt-5.3-codex-spark/high",
                    "runtime": "acpx-codex",
                },
            },
            "internal-reviewer": {
                "name": "Internal_Reviewer_Agent",
                "model": "claude-sonnet-4-6",
                "runtime": "claude-cli",
                "freeze-coder-while-running": True,
            },
            "external-reviewer": {
                "enabled": True,
                "name": "External_Reviewer_Agent",
                "provider": "codex-cloud",
                "cache-seconds": 1800,
            },
        },
        "gates": {
            "internal-review": {
                "pass-with-findings-tolerance": 1,
                "require-pass-clean-before-publish": True,
                "request-cooldown-seconds": 1200,
            },
            "external-review": {"required-for-merge": True},
            "merge": {"require-ci-acceptable": True},
        },
        "triggers": {
            "lane-selector": {"type": "github-label", "label": "active-lane"},
        },
        "storage": {
            "ledger": "memory/workflow-status.json",
            "health": "memory/workflow-health.json",
            "audit-log": "memory/workflow-audit.jsonl",
        },
    }


def test_schema_accepts_minimal_valid_config():
    jsonschema.validate(_minimal_valid_config(), _load_schema())


def test_schema_rejects_missing_workflow_key():
    cfg = _minimal_valid_config()
    del cfg["workflow"]
    with pytest.raises(jsonschema.ValidationError) as exc:
        jsonschema.validate(cfg, _load_schema())
    assert "workflow" in str(exc.value)


def test_schema_rejects_missing_runtimes_block():
    cfg = _minimal_valid_config()
    del cfg["runtimes"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(cfg, _load_schema())


def test_schema_rejects_agent_pointing_at_unknown_runtime():
    # jsonschema alone doesn't enforce cross-references (agent.runtime must be
    # a key in runtimes). This check lives in workspace.py, not in schema.yaml.
    # Here we just verify the schema accepts arbitrary string runtime values;
    # the cross-reference test lives in test_workflows_code_review_workspace.py.
    cfg = _minimal_valid_config()
    cfg["agents"]["coder"]["default"]["runtime"] = "nonexistent"
    # Schema validation still passes:
    jsonschema.validate(cfg, _load_schema())


def test_schema_enforces_workflow_const_value_is_code_review():
    cfg = _minimal_valid_config()
    cfg["workflow"] = "not-code-review"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(cfg, _load_schema())
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
python3 -m pytest tests/test_workflows_code_review_schema.py -v
```

Expected: the first test fails because the placeholder schema doesn't declare required top-level sections like `runtimes`, `agents`, etc.

- [ ] **Step 3: Rewrite `workflows/code_review/schema.yaml` with the full shape**

Replace the placeholder file with the full schema. The schema is long; an abbreviated form:

```yaml
$schema: http://json-schema.org/draft-07/schema#
title: code-review workflow config
type: object
required:
  - workflow
  - schema-version
  - instance
  - repository
  - runtimes
  - agents
  - gates
  - triggers
  - storage
properties:
  workflow:
    const: code-review
  schema-version:
    type: integer
    enum: [1]

  instance:
    type: object
    required: [name, engine-owner]
    properties:
      name: {type: string}
      engine-owner: {type: string, enum: [hermes, openclaw]}

  repository:
    type: object
    required: [local-path, github-slug, active-lane-label]
    properties:
      local-path: {type: string}
      github-slug: {type: string}
      active-lane-label: {type: string}

  runtimes:
    type: object
    minProperties: 1
    additionalProperties:
      oneOf:
        - $ref: "#/definitions/acpx-codex-runtime"
        - $ref: "#/definitions/claude-cli-runtime"

  agents:
    type: object
    required: [coder, internal-reviewer, external-reviewer]
    properties:
      coder:
        type: object
        minProperties: 1
        additionalProperties:
          $ref: "#/definitions/coder-tier"
      internal-reviewer:
        type: object
        required: [name, model, runtime]
        properties:
          name: {type: string}
          model: {type: string}
          runtime: {type: string}
          freeze-coder-while-running: {type: boolean}
      external-reviewer:
        type: object
        required: [enabled, name]
        properties:
          enabled: {type: boolean}
          name: {type: string}
          provider: {type: string}
          cache-seconds: {type: integer}
      advisory-reviewer:
        type: object
        required: [enabled, name]
        properties:
          enabled: {type: boolean}
          name: {type: string}

  gates:
    type: object
    required: [internal-review, external-review, merge]
    properties:
      internal-review:
        type: object
        properties:
          pass-with-findings-tolerance: {type: integer}
          require-pass-clean-before-publish: {type: boolean}
          request-cooldown-seconds: {type: integer}
      external-review:
        type: object
        properties:
          required-for-merge: {type: boolean}
      merge:
        type: object
        properties:
          require-ci-acceptable: {type: boolean}

  triggers:
    type: object
    required: [lane-selector]
    properties:
      lane-selector:
        type: object
        required: [type, label]
        properties:
          type: {type: string}
          label: {type: string}
      start-conditions:
        type: array
        items: {type: object}

  escalation:
    type: object
    additionalProperties: {type: integer}

  schedules:
    type: object
    properties:
      watchdog-tick:
        type: object
        properties:
          interval-minutes: {type: integer}
      milestone-notifier:
        type: object
        properties:
          interval-hours: {type: integer}
          delivery:
            type: object
            properties:
              channel: {type: string}
              chat-id: {type: string}

  prompts:
    type: object
    additionalProperties: {type: string}

  storage:
    type: object
    required: [ledger, health, audit-log]
    properties:
      ledger: {type: string}
      health: {type: string}
      audit-log: {type: string}
      cron-jobs-path: {type: string}
      hermes-cron-jobs-path: {type: string}
      sessions-state: {type: string}

  codex-bot:
    type: object
    properties:
      logins:
        type: array
        items: {type: string}
      clean-reactions:
        type: array
        items: {type: string}
      pending-reactions:
        type: array
        items: {type: string}

definitions:
  acpx-codex-runtime:
    type: object
    required: [kind, session-idle-freshness-seconds, session-idle-grace-seconds, session-nudge-cooldown-seconds]
    properties:
      kind: {const: acpx-codex}
      session-idle-freshness-seconds: {type: integer, minimum: 1}
      session-idle-grace-seconds: {type: integer, minimum: 1}
      session-nudge-cooldown-seconds: {type: integer, minimum: 1}

  claude-cli-runtime:
    type: object
    required: [kind, max-turns-per-invocation, timeout-seconds]
    properties:
      kind: {const: claude-cli}
      max-turns-per-invocation: {type: integer, minimum: 1}
      timeout-seconds: {type: integer, minimum: 1}

  coder-tier:
    type: object
    required: [name, model, runtime]
    properties:
      name: {type: string}
      model: {type: string}
      runtime: {type: string}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
python3 -m pytest tests/test_workflows_code_review_schema.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add workflows/code_review/schema.yaml tests/test_workflows_code_review_schema.py
git commit -m "$(cat <<'EOF'
feat(workflows/code-review): full JSON Schema for workflow.yaml

schema.yaml now validates every top-level section declared in the design
spec: instance, repository, runtimes (with per-kind oneOf), agents
(coder tiers + internal/external/advisory reviewers), gates, triggers,
escalation, schedules, prompts, storage, codex-bot. Cross-references
(e.g. agent.runtime must match a key in runtimes) are enforced in
workspace.py, not in the schema.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 4.2: Write `scripts/migrate_config.py` (JSON → YAML one-shot)

**Files:**
- Create: `scripts/migrate_config.py`
- Create: `tests/test_migrate_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_migrate_config.py
import json
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATE_SCRIPT = REPO_ROOT / "scripts" / "migrate_config.py"


def _sample_old_json():
    return {
        "repoPath": "/home/radxa/.hermes/workspaces/YoyoPod_Core",
        "cronJobsPath": "/home/radxa/.hermes/workflows/yoyopod/archive/openclaw-cron-jobs.json",
        "ledgerPath": "/home/radxa/.hermes/workflows/yoyopod/memory/yoyopod-workflow-status.json",
        "healthPath": "/home/radxa/.hermes/workflows/yoyopod/memory/yoyopod-workflow-health.json",
        "auditLogPath": "/home/radxa/.hermes/workflows/yoyopod/memory/yoyopod-workflow-audit.jsonl",
        "activeLaneLabel": "active-lane",
        "engineOwner": "hermes",
        "coreJobNames": [],
        "hermesJobNames": ["yoyopod-workflow-milestone-telegram"],
        "issueWatcherNameRegex": "issue-\\d+-watch",
        "staleness": {
            "coreJobMissMultiplier": 2.5,
            "activeLaneWithoutPrMinutes": 45,
            "reviewHeadMissingMinutes": 20,
        },
        "sessionPolicy": {
            "codexModel": "gpt-5.3-codex-spark/high",
            "codexModelLargeEffort": "gpt-5.3-codex",
            "codexModelEscalated": "gpt-5.4",
            "codexEscalateRestartCount": 2,
            "codexEscalateLocalReviewCount": 3,
            "codexEscalatePostpublishFindingCount": 3,
            "laneFailureRetryBudget": 3,
            "laneNoProgressTickBudget": 3,
            "laneOperatorAttentionRetryThreshold": 5,
            "laneOperatorAttentionNoProgressThreshold": 5,
            "codexSessionFreshnessSeconds": 900,
            "codexSessionPokeGraceSeconds": 1800,
            "codexSessionNudgeCooldownSeconds": 600,
        },
        "reviewPolicy": {
            "interReviewAgentPassWithFindingsReviews": 1,
            "interReviewAgentModel": "claude-sonnet-4-6",
            "interReviewAgentMaxTurns": 24,
            "interReviewAgentTimeoutSeconds": 1200,
            "freezeCoderWhileInterReviewAgentRunning": True,
        },
        "agentLabels": {
            "internalCoderAgent": "Internal_Coder_Agent",
            "escalationCoderAgent": "Escalation_Coder_Agent",
            "internalReviewerAgent": "Internal_Reviewer_Agent",
            "externalReviewerAgent": "External_Reviewer_Agent",
            "advisoryReviewerAgent": "Advisory_Reviewer_Agent",
        },
    }


def test_migrate_emits_valid_workflow_yaml(tmp_path):
    json_path = tmp_path / "yoyopod-workflow.json"
    json_path.write_text(json.dumps(_sample_old_json()), encoding="utf-8")
    yaml_path = tmp_path / "workflow.yaml"

    result = subprocess.run(
        [sys.executable, str(MIGRATE_SCRIPT), str(json_path), str(yaml_path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr

    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))

    # Validate against the live schema
    import jsonschema
    schema_path = REPO_ROOT / "workflows" / "code_review" / "schema.yaml"
    schema = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(cfg, schema)

    # Spot-check key translations
    assert cfg["workflow"] == "code-review"
    assert cfg["schema-version"] == 1
    assert cfg["instance"]["engine-owner"] == "hermes"
    assert cfg["repository"]["local-path"] == "/home/radxa/.hermes/workspaces/YoyoPod_Core"
    assert cfg["runtimes"]["acpx-codex"]["session-idle-freshness-seconds"] == 900
    assert cfg["runtimes"]["claude-cli"]["max-turns-per-invocation"] == 24
    assert cfg["agents"]["coder"]["default"]["model"] == "gpt-5.3-codex-spark/high"
    assert cfg["agents"]["internal-reviewer"]["model"] == "claude-sonnet-4-6"
    assert cfg["agents"]["external-reviewer"]["provider"] == "codex-cloud"
```

- [ ] **Step 2: Run to verify fail**

```bash
python3 -m pytest tests/test_migrate_config.py -v
```

Expected: `FileNotFoundError` or similar — script does not exist.

- [ ] **Step 3: Implement the migration script**

```python
#!/usr/bin/env python3
"""One-shot migrator: legacy yoyopod-workflow.json → workflow.yaml.

Usage: python3 scripts/migrate_config.py <old-json-path> <new-yaml-path>

Reads the legacy JSON, projects each setting into its new YAML location
under the shape defined by workflows/code_review/schema.yaml, and writes
the YAML file. The legacy JSON is NOT deleted by this script — do that
manually after verifying the migration.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def convert(old: dict) -> dict:
    session = old.get("sessionPolicy", {}) or {}
    review = old.get("reviewPolicy", {}) or {}
    labels = old.get("agentLabels", {}) or {}

    engine_owner = old.get("engineOwner", "openclaw")
    repo_path = old.get("repoPath", "")
    # Infer workspace name from paths (used as instance.name).
    instance_name = Path(old.get("ledgerPath", "")).parent.parent.name or "default"

    # Derive github-slug from repoPath if possible; otherwise require operator
    # fixup post-migration. YoyoPod's live repoPath is
    # /home/radxa/.hermes/workspaces/YoyoPod_Core — the slug isn't encoded in
    # the filesystem path. We emit a placeholder the operator must fill in.
    github_slug = "FIXME/FIXME"
    if "YoyoPod_Core" in repo_path:
        github_slug = "moustafattia/YoyoPod_Core"

    return {
        "workflow": "code-review",
        "schema-version": 1,

        "instance": {
            "name": instance_name,
            "engine-owner": engine_owner,
        },

        "repository": {
            "local-path": repo_path,
            "github-slug": github_slug,
            "active-lane-label": old.get("activeLaneLabel", "active-lane"),
        },

        "runtimes": {
            "acpx-codex": {
                "kind": "acpx-codex",
                "session-idle-freshness-seconds": int(session.get("codexSessionFreshnessSeconds", 900)),
                "session-idle-grace-seconds": int(session.get("codexSessionPokeGraceSeconds", 1800)),
                "session-nudge-cooldown-seconds": int(session.get("codexSessionNudgeCooldownSeconds", 600)),
            },
            "claude-cli": {
                "kind": "claude-cli",
                "max-turns-per-invocation": int(
                    review.get("interReviewAgentMaxTurns")
                    or review.get("internalReviewerAgentMaxTurns")
                    or review.get("claudeReviewMaxTurns", 24)
                ),
                "timeout-seconds": int(
                    review.get("interReviewAgentTimeoutSeconds")
                    or review.get("internalReviewerAgentTimeoutSeconds")
                    or review.get("claudeReviewTimeoutSeconds", 1200)
                ),
            },
        },

        "agents": {
            "coder": {
                "default": {
                    "name": labels.get("internalCoderAgent", "Internal_Coder_Agent"),
                    "model": session.get("codexModel", "gpt-5.3-codex-spark/high"),
                    "runtime": "acpx-codex",
                },
                "high-effort": {
                    "name": labels.get("internalCoderAgent", "Internal_Coder_Agent"),
                    "model": session.get("codexModelLargeEffort") or session.get("codexModelHighEffort") or "gpt-5.3-codex",
                    "runtime": "acpx-codex",
                },
                "escalated": {
                    "name": labels.get("escalationCoderAgent", "Escalation_Coder_Agent"),
                    "model": session.get("codexModelEscalated", "gpt-5.4"),
                    "runtime": "acpx-codex",
                },
            },
            "internal-reviewer": {
                "name": labels.get("internalReviewerAgent", "Internal_Reviewer_Agent"),
                "model": review.get("interReviewAgentModel") or review.get("internalReviewerAgentModel") or review.get("claudeModel", "claude-sonnet-4-6"),
                "runtime": "claude-cli",
                "freeze-coder-while-running": bool(
                    review.get("freezeCoderWhileInterReviewAgentRunning",
                               review.get("freezeCoderWhileInternalReviewAgentRunning",
                                          review.get("freezeCoderWhileClaudeReviewRunning", True)))
                ),
            },
            "external-reviewer": {
                "enabled": True,
                "name": labels.get("externalReviewerAgent", "External_Reviewer_Agent"),
                "provider": "codex-cloud",
                "cache-seconds": int(old.get("reviewCache", {}).get("codexCloudSeconds", 1800)),
            },
            "advisory-reviewer": {
                "enabled": False,
                "name": labels.get("advisoryReviewerAgent", "Advisory_Reviewer_Agent"),
            },
        },

        "gates": {
            "internal-review": {
                "pass-with-findings-tolerance": int(
                    review.get("interReviewAgentPassWithFindingsReviews")
                    or review.get("internalReviewerAgentPassWithFindingsReviews")
                    or review.get("claudePassWithFindingsReviews", 1)
                ),
                "require-pass-clean-before-publish": True,
                "request-cooldown-seconds": int(old.get("reviewCache", {}).get("claudeReviewRequestCooldownSeconds", 1200)),
            },
            "external-review": {
                "required-for-merge": True,
            },
            "merge": {
                "require-ci-acceptable": True,
            },
        },

        "triggers": {
            "lane-selector": {
                "type": "github-label",
                "label": old.get("activeLaneLabel", "active-lane"),
            },
        },

        "escalation": {
            "restart-count-threshold": int(session.get("codexEscalateRestartCount", 2)),
            "local-review-count-threshold": int(session.get("codexEscalateLocalReviewCount", 2)),
            "postpublish-finding-threshold": int(session.get("codexEscalatePostpublishFindingCount", 3)),
            "lane-failure-retry-budget": int(session.get("laneFailureRetryBudget", 3)),
            "no-progress-tick-budget": int(session.get("laneNoProgressTickBudget", 3)),
            "operator-attention-retry-threshold": int(session.get("laneOperatorAttentionRetryThreshold", 5)),
            "operator-attention-no-progress-threshold": int(session.get("laneOperatorAttentionNoProgressThreshold", 5)),
            "lane-counter-increment-min-seconds": int(session.get("laneCounterIncrementMinSeconds", 240)),
        },

        "schedules": {
            "watchdog-tick": {"interval-minutes": 5},
            "milestone-notifier": {
                "interval-hours": 1,
                "delivery": {
                    "channel": "telegram",
                    "chat-id": "-1003651617977",
                },
            },
        },

        "prompts": {
            "internal-review": "internal-review-strict",
            "coder-dispatch": "coder-dispatch",
            "repair-handoff": "repair-handoff",
        },

        "storage": {
            "ledger": "memory/workflow-status.json",
            "health": "memory/workflow-health.json",
            "audit-log": "memory/workflow-audit.jsonl",
            "cron-jobs-path": old.get("cronJobsPath", ""),
            "hermes-cron-jobs-path": old.get("hermesCronJobsPath", str(Path.home() / ".hermes/cron/jobs.json")),
            "sessions-state": "state/sessions",
        },

        "codex-bot": {
            "logins": ["chatgpt-codex-connector", "chatgpt-codex-connector[bot]"],
            "clean-reactions": ["+1"],
            "pending-reactions": ["eyes"],
        },
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: migrate_config.py <old-json-path> <new-yaml-path>", file=sys.stderr)
        return 2
    old_path = Path(argv[0]).expanduser().resolve()
    new_path = Path(argv[1]).expanduser().resolve()
    if not old_path.exists():
        print(f"input JSON not found: {old_path}", file=sys.stderr)
        return 1
    if new_path.exists():
        print(f"refusing to overwrite existing file: {new_path}", file=sys.stderr)
        return 1
    old = json.loads(old_path.read_text(encoding="utf-8"))
    new = convert(old)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    new_path.write_text(yaml.safe_dump(new, sort_keys=False, default_flow_style=False), encoding="utf-8")
    print(f"wrote {new_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

Make it executable:

```bash
chmod +x scripts/migrate_config.py
```

- [ ] **Step 4: Run the test**

```bash
python3 -m pytest tests/test_migrate_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_config.py tests/test_migrate_config.py
git commit -m "$(cat <<'EOF'
feat(scripts): add migrate_config.py JSON-to-YAML one-shot migrator

Translates the legacy yoyopod-workflow.json shape to the new YAML
workflow.yaml shape. Every section of the new schema is populated from
the old JSON's fields. github-slug is inferred from YoyoPod_Core paths;
other repos get a FIXME placeholder the operator fills in.

Refuses to overwrite an existing target file; the operator deletes the
old JSON manually after verifying the migration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 4.3: Rewrite `workflows/code_review/workspace.py` to consume the YAML config

This is the largest task in the plan. The existing `make_workspace` reads ~30 JSON keys. Rewrite it to read from the new YAML shape while preserving the full namespace surface (every `ns.REPO_PATH`, `ns.INTER_REVIEW_AGENT_MODEL`, etc. still exists, just sourced differently).

**Files:**
- Modify: `workflows/code_review/workspace.py`
- Modify: `tests/test_workflows_code_review_workspace.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_workflows_code_review_workspace.py`:

```python
def test_workspace_from_yaml_exposes_same_surface_as_legacy_json(tmp_path):
    """Given the new YAML shape, workspace exposes the same attribute surface
    callers have historically used (REPO_PATH, INTER_REVIEW_AGENT_MODEL, etc.)."""
    from workflows.code_review.workspace import make_workspace

    yaml_cfg = {
        "workflow": "code-review",
        "schema-version": 1,
        "instance": {"name": "yoyopod", "engine-owner": "hermes"},
        "repository": {
            "local-path": str(tmp_path / "repo"),
            "github-slug": "owner/repo",
            "active-lane-label": "active-lane",
        },
        "runtimes": {
            "acpx-codex": {
                "kind": "acpx-codex",
                "session-idle-freshness-seconds": 900,
                "session-idle-grace-seconds": 1800,
                "session-nudge-cooldown-seconds": 600,
            },
            "claude-cli": {
                "kind": "claude-cli",
                "max-turns-per-invocation": 24,
                "timeout-seconds": 1200,
            },
        },
        "agents": {
            "coder": {
                "default": {"name": "Internal_Coder_Agent", "model": "gpt-5.3-codex-spark/high", "runtime": "acpx-codex"},
                "high-effort": {"name": "Internal_Coder_Agent", "model": "gpt-5.3-codex", "runtime": "acpx-codex"},
                "escalated": {"name": "Escalation_Coder_Agent", "model": "gpt-5.4", "runtime": "acpx-codex"},
            },
            "internal-reviewer": {
                "name": "Internal_Reviewer_Agent",
                "model": "claude-sonnet-4-6",
                "runtime": "claude-cli",
                "freeze-coder-while-running": True,
            },
            "external-reviewer": {
                "enabled": True, "name": "External_Reviewer_Agent",
                "provider": "codex-cloud", "cache-seconds": 1800,
            },
        },
        "gates": {
            "internal-review": {
                "pass-with-findings-tolerance": 1,
                "require-pass-clean-before-publish": True,
                "request-cooldown-seconds": 1200,
            },
            "external-review": {"required-for-merge": True},
            "merge": {"require-ci-acceptable": True},
        },
        "triggers": {"lane-selector": {"type": "github-label", "label": "active-lane"}},
        "storage": {
            "ledger": "memory/workflow-status.json",
            "health": "memory/workflow-health.json",
            "audit-log": "memory/workflow-audit.jsonl",
            "cron-jobs-path": str(tmp_path / "cron.json"),
            "hermes-cron-jobs-path": str(tmp_path / "hermes-cron.json"),
            "sessions-state": "state/sessions",
        },
        "codex-bot": {
            "logins": ["chatgpt-codex-connector"],
            "clean-reactions": ["+1"],
            "pending-reactions": ["eyes"],
        },
    }

    ws = make_workspace(workflow_root=tmp_path, config=yaml_cfg)

    # Legacy surface still present:
    assert str(ws.REPO_PATH) == str(tmp_path / "repo")
    assert ws.ACTIVE_LANE_LABEL == "active-lane"
    assert ws.ENGINE_OWNER == "hermes"
    assert ws.CODEX_MODEL_DEFAULT == "gpt-5.3-codex-spark/high"
    assert ws.CODEX_MODEL_HIGH_EFFORT == "gpt-5.3-codex"
    assert ws.CODEX_MODEL_ESCALATED == "gpt-5.4"
    assert ws.INTER_REVIEW_AGENT_MODEL == "claude-sonnet-4-6"
    assert ws.INTER_REVIEW_AGENT_MAX_TURNS == 24
    assert ws.INTER_REVIEW_AGENT_TIMEOUT_SECONDS == 1200
    assert ws.CODEX_SESSION_FRESHNESS_SECONDS == 900
    assert ws.CODEX_SESSION_POKE_GRACE_SECONDS == 1800
    assert ws.CODEX_SESSION_NUDGE_COOLDOWN_SECONDS == 600
    assert ws.INTERNAL_CODER_AGENT_NAME == "Internal_Coder_Agent"
    assert ws.ESCALATION_CODER_AGENT_NAME == "Escalation_Coder_Agent"
    assert ws.INTERNAL_REVIEWER_AGENT_NAME == "Internal_Reviewer_Agent"
    assert ws.EXTERNAL_REVIEWER_AGENT_NAME == "External_Reviewer_Agent"
    # Runtime accessor works
    assert callable(ws.runtime)
    assert hasattr(ws.runtime("acpx-codex"), "ensure_session")
    assert hasattr(ws.runtime("claude-cli"), "run_prompt")


def test_workspace_raises_on_agent_referencing_unknown_runtime(tmp_path):
    from workflows.code_review.workspace import make_workspace

    cfg = {
        "workflow": "code-review",
        "schema-version": 1,
        "instance": {"name": "test", "engine-owner": "hermes"},
        "repository": {"local-path": str(tmp_path), "github-slug": "o/r", "active-lane-label": "active-lane"},
        "runtimes": {"acpx-codex": {"kind": "acpx-codex", "session-idle-freshness-seconds": 900, "session-idle-grace-seconds": 1800, "session-nudge-cooldown-seconds": 600}},
        "agents": {
            "coder": {"default": {"name": "C", "model": "m", "runtime": "nonexistent-runtime"}},
            "internal-reviewer": {"name": "R", "model": "m", "runtime": "acpx-codex"},
            "external-reviewer": {"enabled": False, "name": "E"},
        },
        "gates": {"internal-review": {}, "external-review": {}, "merge": {}},
        "triggers": {"lane-selector": {"type": "github-label", "label": "l"}},
        "storage": {"ledger": "l", "health": "h", "audit-log": "a"},
    }
    import pytest
    with pytest.raises(ValueError) as exc:
        make_workspace(workflow_root=tmp_path, config=cfg)
    assert "nonexistent-runtime" in str(exc.value)
```

- [ ] **Step 2: Run, verify fail**

```bash
python3 -m pytest tests/test_workflows_code_review_workspace.py::test_workspace_from_yaml_exposes_same_surface_as_legacy_json -v
```

Expected: FAIL — `make_workspace` currently reads old JSON keys (`repoPath`, etc.), not the new YAML shape.

- [ ] **Step 3: Rewrite `make_workspace`**

This is a substantial rewrite. Strategy: produce a small `_yaml_to_legacy_view(yaml_cfg)` helper at the top of `workspace.py` that projects the YAML into the old-JSON key shape, then pass that through the existing `make_workspace` body. This minimizes risk — the existing ~1600-LOC factory stays intact; only its input shape changes.

At the top of `workflows/code_review/workspace.py`, add:

```python
def _yaml_to_legacy_view(yaml_cfg: dict) -> dict:
    """Project the new YAML shape onto the old JSON key shape.

    This is a temporary bridge that keeps the ~1600-LOC workspace factory
    body untouched during Phase 4. Phase 6 cleanup can fold the bridge
    into the factory once the shape is stable.
    """
    instance = yaml_cfg.get("instance", {}) or {}
    repo = yaml_cfg.get("repository", {}) or {}
    runtimes = yaml_cfg.get("runtimes", {}) or {}
    agents = yaml_cfg.get("agents", {}) or {}
    gates = yaml_cfg.get("gates", {}) or {}
    storage = yaml_cfg.get("storage", {}) or {}
    escalation = yaml_cfg.get("escalation", {}) or {}

    acpx = runtimes.get("acpx-codex", {}) or {}
    claude_cli = runtimes.get("claude-cli", {}) or {}

    coder_default = (agents.get("coder") or {}).get("default", {}) or {}
    coder_high = (agents.get("coder") or {}).get("high-effort", {}) or coder_default
    coder_escalated = (agents.get("coder") or {}).get("escalated", {}) or coder_default
    int_reviewer = agents.get("internal-reviewer", {}) or {}
    ext_reviewer = agents.get("external-reviewer", {}) or {}
    adv_reviewer = agents.get("advisory-reviewer", {}) or {}
    internal_review_gate = gates.get("internal-review", {}) or {}

    return {
        "repoPath": repo.get("local-path", ""),
        "cronJobsPath": storage.get("cron-jobs-path", ""),
        "hermesCronJobsPath": storage.get("hermes-cron-jobs-path"),
        "ledgerPath": str(Path(repo.get("local-path", "")).parent.parent / storage.get("ledger", "memory/workflow-status.json"))
            if not Path(storage.get("ledger", "")).is_absolute()
            else storage.get("ledger"),
        "healthPath": storage.get("health"),
        "auditLogPath": storage.get("audit-log"),
        "activeLaneLabel": repo.get("active-lane-label", "active-lane"),
        "engineOwner": instance.get("engine-owner", "openclaw"),
        "coreJobNames": [],
        # Hardcoded to the one hermes-owned job name emitted by the schedules
        # section; revisit when adding more hermes-scheduled jobs.
        "hermesJobNames": ["yoyopod-workflow-milestone-telegram"],
        "issueWatcherNameRegex": r"issue-\d+-watch",
        "staleness": {
            "coreJobMissMultiplier": 2.5,
            "activeLaneWithoutPrMinutes": 45,
            "reviewHeadMissingMinutes": 20,
        },
        "reviewCache": {
            "codexCloudSeconds": ext_reviewer.get("cache-seconds", 1800),
            "claudeReviewRequestCooldownSeconds": internal_review_gate.get("request-cooldown-seconds", 1200),
        },
        "sessionPolicy": {
            "codexModel": coder_default.get("model", "gpt-5.3-codex-spark/high"),
            "codexModelLargeEffort": coder_high.get("model"),
            "codexModelEscalated": coder_escalated.get("model"),
            "codexEscalateRestartCount": escalation.get("restart-count-threshold", 2),
            "codexEscalateLocalReviewCount": escalation.get("local-review-count-threshold", 2),
            "codexEscalatePostpublishFindingCount": escalation.get("postpublish-finding-threshold", 3),
            "laneFailureRetryBudget": escalation.get("lane-failure-retry-budget", 3),
            "laneNoProgressTickBudget": escalation.get("no-progress-tick-budget", 3),
            "laneOperatorAttentionRetryThreshold": escalation.get("operator-attention-retry-threshold", 5),
            "laneOperatorAttentionNoProgressThreshold": escalation.get("operator-attention-no-progress-threshold", 5),
            "laneCounterIncrementMinSeconds": escalation.get("lane-counter-increment-min-seconds", 240),
            "codexSessionFreshnessSeconds": acpx.get("session-idle-freshness-seconds", 900),
            "codexSessionPokeGraceSeconds": acpx.get("session-idle-grace-seconds", 1800),
            "codexSessionNudgeCooldownSeconds": acpx.get("session-nudge-cooldown-seconds", 600),
        },
        "reviewPolicy": {
            "interReviewAgentPassWithFindingsReviews": internal_review_gate.get("pass-with-findings-tolerance", 1),
            "interReviewAgentModel": int_reviewer.get("model", "claude-sonnet-4-6"),
            "interReviewAgentMaxTurns": claude_cli.get("max-turns-per-invocation", 24),
            "interReviewAgentTimeoutSeconds": claude_cli.get("timeout-seconds", 1200),
            "freezeCoderWhileInterReviewAgentRunning": int_reviewer.get("freeze-coder-while-running", True),
        },
        "agentLabels": {
            "internalCoderAgent": coder_default.get("name", "Internal_Coder_Agent"),
            "escalationCoderAgent": coder_escalated.get("name", "Escalation_Coder_Agent"),
            "internalReviewerAgent": int_reviewer.get("name", "Internal_Reviewer_Agent"),
            "externalReviewerAgent": ext_reviewer.get("name", "External_Reviewer_Agent"),
            "advisoryReviewerAgent": adv_reviewer.get("name", "Advisory_Reviewer_Agent"),
        },
    }
```

Then update `make_workspace` to detect whether it's been passed an old-shape JSON or a new-shape YAML. Keep the historical parameter name ``workspace_root`` (the plugin contract in ``__init__.py`` already translates ``workflow_root`` → ``workspace_root`` at the boundary, see Task 4.4):

```python
def make_workspace(*, workspace_root: Path, config: dict):
    # Detect new-shape YAML (has `workflow:` top-level key) and bridge if so.
    if "workflow" in config and "runtimes" in config and "agents" in config:
        # New YAML shape — bridge to legacy view for the existing body.
        legacy_view = _yaml_to_legacy_view(config)
        yaml_cfg = config  # keep the original for direct runtimes/agents access
    else:
        # Old JSON shape (Phase 2-3 compatibility) — pass through unchanged.
        legacy_view = config
        yaml_cfg = None

    # ... existing body uses `legacy_view` where it previously used `config` ...
    # Existing lines like `config["repoPath"]` become `legacy_view["repoPath"]`.

    # After the namespace is built, validate agent → runtime cross-references
    # (only relevant when yaml_cfg is set):
    if yaml_cfg is not None:
        agents = yaml_cfg.get("agents", {}) or {}
        runtimes = yaml_cfg.get("runtimes", {}) or {}
        known_runtimes = set(runtimes.keys())
        # Check coder tiers
        for tier_name, tier in (agents.get("coder") or {}).items():
            rt = tier.get("runtime")
            if rt and rt not in known_runtimes:
                raise ValueError(
                    f"agents.coder.{tier_name}.runtime={rt!r} not defined in runtimes: "
                    f"{sorted(known_runtimes)}"
                )
        # Check internal-reviewer
        for reviewer_role in ("internal-reviewer",):
            agent = agents.get(reviewer_role, {})
            rt = agent.get("runtime")
            if rt and rt not in known_runtimes:
                raise ValueError(
                    f"agents.{reviewer_role}.runtime={rt!r} not defined in runtimes: "
                    f"{sorted(known_runtimes)}"
                )
```

**Important:** the in-body rewrite of `config["X"]` → `legacy_view["X"]` must be exhaustive. After the rewrite, `grep -n 'config\[' workflows/code_review/workspace.py` should only return lines where the new-shape `config` is used (e.g., in the cross-reference validation at the bottom).

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_workflows_code_review_workspace.py -v
```

Expected: the 2 new tests PASS, and all existing workspace tests still pass (because the bridge preserves the legacy key shape).

Also run the broader code-review suite:

```bash
python3 -m pytest tests/test_workflows_code_review_ -q 2>&1 | tail -5
```

Expected: no regressions.

- [ ] **Step 5: Commit**

```bash
git add workflows/code_review/workspace.py tests/test_workflows_code_review_workspace.py
git commit -m "$(cat <<'EOF'
feat(workflows/code-review): workspace.make_workspace consumes the new YAML shape

Adds _yaml_to_legacy_view(yaml_cfg) that projects the new-YAML structure
(instance / repository / runtimes / agents / gates / storage / ...) into
the old-JSON key shape the existing 1600-LOC factory body consumes.
make_workspace auto-detects whether it got old-shape JSON or new-shape
YAML and bridges accordingly.

Cross-reference validation catches agents pointing at runtimes that
aren't declared, with a clear error listing the known runtime names.

Both shapes coexist for the duration of Phase 4; Phase 6 cleanup can
fold the bridge into the factory once the live workspace is fully
migrated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 4.4: Wire the schema-validated YAML into `make_workspace` inside the dispatcher flow

The dispatcher's `run_cli` currently calls `module.make_workspace(workflow_root=..., config=cfg)` with `cfg` = the parsed YAML. In Phase 2's Task 2.2 we defined `make_workspace` as a thin wrapper that ignores `config` and calls `load_workspace_from_config(workspace_root=...)`. Now that `make_workspace` accepts real YAML, rewire:

**Files:**
- Modify: `workflows/code_review/__init__.py`

- [ ] **Step 1: Change `make_workspace` in `__init__.py` to pass `config` through**

Edit `workflows/code_review/__init__.py`:

```python
# Before:
def make_workspace(*, workflow_root: Path, config: dict):
    return _load_workspace_from_config(workspace_root=workflow_root)

# After:
from workflows.code_review.workspace import make_workspace as _make_workspace_inner


def make_workspace(*, workflow_root: Path, config: dict):
    # Internal workspace.make_workspace still uses the historical param name
    # 'workspace_root'; the plugin contract exposes 'workflow_root'. Translate
    # across the boundary.
    return _make_workspace_inner(workspace_root=workflow_root, config=config)
```

- [ ] **Step 2: Run the full code-review suite + dispatcher suite**

```bash
python3 -m pytest tests/test_workflows_code_review_ tests/test_workflows_dispatcher.py -q 2>&1 | tail -5
```

Expected: no regressions.

- [ ] **Step 3: Commit**

```bash
git add workflows/code_review/__init__.py
git commit -m "feat(workflows/code-review): wire dispatcher make_workspace through the YAML-aware factory

The contract's make_workspace() now delegates to the workspace.make_workspace()
that consumes the new YAML shape. Phase 4 completes the JSON -> YAML switch.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 4.5: Run the migration on the live workspace

**Files:**
- Create: `/home/radxa/.hermes/workflows/yoyopod/config/workflow.yaml` (output)
- Delete: `/home/radxa/.hermes/workflows/yoyopod/config/yoyopod-workflow.json` (after verification)

- [ ] **Step 1: Back up the live JSON**

```bash
cp /home/radxa/.hermes/workflows/yoyopod/config/yoyopod-workflow.json \
   /home/radxa/.hermes/workflows/yoyopod/config/yoyopod-workflow.json.pre-yaml-migration
```

- [ ] **Step 2: Run the migration**

```bash
cd /home/radxa/WS/hermes-relay
python3 scripts/migrate_config.py \
  /home/radxa/.hermes/workflows/yoyopod/config/yoyopod-workflow.json \
  /home/radxa/.hermes/workflows/yoyopod/config/workflow.yaml
```

Expected output: `wrote /home/radxa/.hermes/workflows/yoyopod/config/workflow.yaml`.

- [ ] **Step 3: Inspect the result**

```bash
head -60 /home/radxa/.hermes/workflows/yoyopod/config/workflow.yaml
```

Verify the top-level `workflow: code-review`, `schema-version: 1`, and all major sections (`instance`, `repository`, `runtimes`, `agents`, `gates`, `triggers`, `escalation`, `schedules`, `prompts`, `storage`, `codex-bot`) are present.

- [ ] **Step 4: Run the new CLI against the live workspace**

```bash
cd /home/radxa/WS/hermes-relay
python3 -m workflows --workflow-root /home/radxa/.hermes/workflows/yoyopod status 2>&1 | head -10
```

Expected: same output as the old `python3 -m adapters.yoyopod_core status` (health, active-lane, open-pr, ledger state). If you see `jsonschema.ValidationError`, inspect the emitted `workflow.yaml` — the migrator may have missed a field.

- [ ] **Step 5: Delete the old JSON**

```bash
rm /home/radxa/.hermes/workflows/yoyopod/config/yoyopod-workflow.json
ls /home/radxa/.hermes/workflows/yoyopod/config/
```

Expected: only `workflow.yaml` and `yoyopod-workflow.json.pre-yaml-migration` (backup) remain.

- [ ] **Step 6: Commit (no repo changes from this task — it's a live-workspace operation)**

No commit. Optionally note the migration in an audit-log file:

```bash
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) — migrated yoyopod-workflow.json to workflow.yaml" >> \
  /home/radxa/.hermes/workflows/yoyopod/memory/yoyopod-workflow-audit.jsonl
```

### Phase 4 verification

- [ ] **Run the full suite**

```bash
cd /home/radxa/WS/hermes-relay
python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -6
```

Expected: previous total + 5 schema tests + 1 migrate test + 2 new workspace tests ≈ +8 tests. No regressions.

- [ ] **Live smoke test**

```bash
python3 -m workflows --workflow-root /home/radxa/.hermes/workflows/yoyopod tick --json | python3 -c "import sys, json; d=json.loads(sys.stdin.read()); print(d['action']['type'], d['action'].get('reason'))"
```

Expected: same action/reason as pre-migration (`noop no-active-lane` or whatever the current state is).

---

## Phase 5 — Delete `adapters/` and rewire external callers

At this point `workflows/code_review/` is fully functional and the live workspace runs against YAML. Now delete `adapters/`, rewire callers, and update the installer.

### Task 5.1: Rewire `runtime.py` imports

**Files:**
- Modify: `runtime.py`

- [ ] **Step 1: Locate all `adapters.yoyopod_core` references**

```bash
grep -n "adapters\.yoyopod_core\|adapters/yoyopod_core" runtime.py
```

Expected: several matches for `plugin_entrypoint_path`, `yoyopod_cli_argv` (both come from `adapters.yoyopod_core.paths`).

- [ ] **Step 2: Rewrite imports**

```bash
sed -i \
  -e 's|adapters\.yoyopod_core\.paths|workflows.code_review.paths|g' \
  -e 's|from adapters\.yoyopod_core|from workflows.code_review|g' \
  -e 's|adapters/yoyopod_core|workflows/code_review|g' \
  runtime.py
```

- [ ] **Step 3: Update `plugin_entrypoint_path` target**

`workflows/code_review/paths.py::plugin_entrypoint_path` still returns `.../adapters/yoyopod_core/__main__.py`. Update it to return the generic dispatcher:

Edit `workflows/code_review/paths.py`:

```python
def plugin_entrypoint_path(workflow_root: Path) -> Path:
    """Path to the installed plugin's generic CLI entrypoint.

    Lives at ``<workflow_root>/.hermes/plugins/hermes-relay/workflows/__main__.py``.
    Use this as the canonical external-caller surface.
    """
    root = workflow_root.resolve()
    return (
        root / ".hermes" / "plugins" / "hermes-relay" / "workflows" / "__main__.py"
    )
```

Rename the existing `yoyopod_cli_argv` to `workflow_cli_argv` (same body, just a rename) and keep the old name as a module-level alias for one release:

```python
def workflow_cli_argv(workflow_root: Path, *command_args: str) -> list[str]:
    plugin_path = plugin_entrypoint_path(workflow_root)
    return ["python3", str(plugin_path), "--workflow-root", str(workflow_root), *command_args]


# Back-compat alias; remove in 0.3.0
yoyopod_cli_argv = workflow_cli_argv
```

- [ ] **Step 4: Run full tests**

```bash
python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5
```

Expected: no regressions.

- [ ] **Step 5: Commit**

```bash
git add runtime.py workflows/code_review/paths.py
git commit -m "$(cat <<'EOF'
refactor: runtime.py imports move from adapters.yoyopod_core to workflows.code_review

Also:
- workflows/code_review/paths.plugin_entrypoint_path now returns the
  generic dispatcher at workflows/__main__.py (not the per-workflow
  direct form). This is the stable external-caller surface.
- yoyopod_cli_argv is renamed workflow_cli_argv (keeps old name as a
  deprecated alias).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 5.2: Rewire `tools.py` + `alerts.py` imports

**Files:**
- Modify: `tools.py`
- Modify: `alerts.py`

- [ ] **Step 1: Bulk rewrite imports**

```bash
sed -i \
  -e 's|adapters\.yoyopod_core\.paths|workflows.code_review.paths|g' \
  -e 's|from adapters\.yoyopod_core|from workflows.code_review|g' \
  -e 's|adapters/yoyopod_core|workflows/code_review|g' \
  tools.py alerts.py
```

- [ ] **Step 2: Run tests**

```bash
python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5
```

Expected: no regressions.

- [ ] **Step 3: Commit**

```bash
git add tools.py alerts.py
git commit -m "refactor: tools.py + alerts.py import workflows.code_review.paths

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 5.3: Update the installer's PAYLOAD_ITEMS and add workflows dep check

**Files:**
- Modify: `scripts/install.py`

- [ ] **Step 1: Update `PAYLOAD_ITEMS`**

Edit `scripts/install.py`:

```python
PAYLOAD_ITEMS = [
    "__init__.py",
    "alerts.py",
    "plugin.yaml",
    "runtime.py",
    "schemas.py",
    "tools.py",
    "workflows",       # NEW — replaces "adapters"
    "projects",
    "skills",
]
```

(Remove `"adapters"` from the list if it's there.)

- [ ] **Step 2: Add runtime dep verification**

Near the top of `install_plugin()`, add:

```python
def _check_runtime_deps() -> None:
    """Fail early if PyYAML or jsonschema are missing on the host python."""
    missing = []
    try:
        import yaml  # noqa: F401
    except ImportError:
        missing.append("pyyaml (apt: python3-yaml)")
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        missing.append("jsonschema (apt: python3-jsonschema)")
    if missing:
        raise RuntimeError(
            "hermes-relay plugin requires the following python modules on the host: "
            + ", ".join(missing)
        )
```

Call `_check_runtime_deps()` at the top of `install_plugin`.

- [ ] **Step 3: Update installer tests**

The existing test `test_install_into_default_hermes_home_copies_plugin_tree` asserts `adapters/yoyopod_core/status.py` is present. Update:

Edit `tests/test_install.py`:

```python
# In test_install_into_default_hermes_home_copies_plugin_tree:
assert (plugin_dir / "workflows" / "code_review" / "status.py").exists()
# Remove:
# assert (plugin_dir / "adapters" / "yoyopod_core" / "status.py").exists()

# In test_install_into_explicit_destination_uses_given_path:
assert (target / "workflows" / "code_review" / "workflow.py").exists()
# Remove:
# assert (target / "adapters" / "yoyopod_core" / "workflow.py").exists()
```

- [ ] **Step 4: Run install tests**

```bash
python3 -m pytest tests/test_install.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/install.py tests/test_install.py
git commit -m "$(cat <<'EOF'
feat(install): payload ships workflows/ instead of adapters/

PAYLOAD_ITEMS replaces 'adapters' with 'workflows'. _check_runtime_deps()
verifies pyyaml + jsonschema are importable on the host python and fails
the install loudly if either is missing.

Tests updated to assert the new installed layout.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 5.4: Delete `adapters/` and the adapters-side tests

**Files:**
- Delete: `adapters/` (entire tree)
- Delete: `tests/test_yoyopod_core_*.py` (15 files)

- [ ] **Step 1: Verify no remaining references**

```bash
grep -rn "from adapters\.\|import adapters\.\|adapters/yoyopod_core" \
  --include="*.py" \
  --exclude-dir=adapters \
  --exclude-dir=.git \
  --exclude-dir=__pycache__ \
  .
```

Expected: empty output (no non-adapters file still references the old path).

- [ ] **Step 2: Delete the adapters tree**

```bash
cd /home/radxa/WS/hermes-relay
git rm -r adapters/
git rm tests/test_yoyopod_core_*.py
```

- [ ] **Step 3: Run full suite**

```bash
python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -5
```

Expected: the workflows-side tests all still pass; adapters-side tests no longer exist.

- [ ] **Step 4: Run install.sh end-to-end**

```bash
cd /home/radxa/WS/hermes-relay
./scripts/install.sh 2>&1 | tail -3
ls /home/radxa/.hermes/plugins/hermes-relay/workflows/code_review/ | head -5
```

Expected: install succeeds; `workflows/code_review/` is present in the installed payload; no `adapters/` dir.

- [ ] **Step 5: Live smoke test**

```bash
python3 -m workflows --workflow-root /home/radxa/.hermes/workflows/yoyopod status 2>&1 | head -5
python3 -m workflows --workflow-root /home/radxa/.hermes/workflows/yoyopod tick --json | python3 -c "import sys, json; d=json.loads(sys.stdin.read()); print(d['action']['type'])"
```

Expected: healthy status + noop tick (or whatever the current lane state is). Identical behavior to pre-deletion.

- [ ] **Step 6: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat: delete adapters/ — workflows/code_review/ is the sole code path

Removes the entire adapters/ tree (14 modules) and the adapters-side
tests (15 files). Live smoke tests pass against the new workflows CLI.

The workspace-side yoyopod-workflow.json config file was migrated to
workflow.yaml in Phase 4; this commit removes the now-unused source of
the old shape.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Task 5.5: Rewire skill docs + cron job prompts

**Files:**
- Modify: `skills/yoyopod-workflow-watchdog-tick/SKILL.md`
- Modify: `skills/yoyopod-closeout-notifier/SKILL.md`
- Modify: `skills/yoyopod-lane-automation/SKILL.md`
- Modify: `skills/yoyopod-relay-alerts-monitoring/SKILL.md` (if it references the old path)
- Modify: `~/.hermes/workflows/yoyopod/archive/openclaw-cron-jobs.json` (live, not repo)

- [ ] **Step 1: Locate stale CLI path references in skills**

```bash
grep -rn "adapters/yoyopod_core/__main__\|adapters\.yoyopod_core" skills/
```

- [ ] **Step 2: Replace with the generic workflows path**

```bash
sed -i \
  -e 's|adapters/yoyopod_core/__main__.py|workflows/__main__.py|g' \
  -e 's|adapters\.yoyopod_core|workflows|g' \
  skills/*/SKILL.md
```

Then verify the commands still make sense contextually — the generic form requires `--workflow-root <path>`:

```bash
grep -n "python3.*workflows/__main__.py" skills/*/SKILL.md | head
```

Each instance should read: `python3 /home/radxa/.hermes/plugins/hermes-relay/workflows/__main__.py --workflow-root /home/radxa/.hermes/workflows/yoyopod <cmd>`. If any reference omits `--workflow-root`, add it. The old form (`adapters/yoyopod_core/__main__.py`) implied the workflow root via its own resolver; the new form requires it explicitly.

- [ ] **Step 3: Update the cron job prompts in the live workspace**

Edit `/home/radxa/.hermes/workflows/yoyopod/archive/openclaw-cron-jobs.json`:

```bash
sed -i \
  -e 's|adapters/yoyopod_core/__main__.py|workflows/__main__.py --workflow-root /home/radxa/.hermes/workflows/yoyopod|g' \
  /home/radxa/.hermes/workflows/yoyopod/archive/openclaw-cron-jobs.json
```

Validate JSON:

```bash
python3 -c "import json; json.load(open('/home/radxa/.hermes/workflows/yoyopod/archive/openclaw-cron-jobs.json'))" && echo "valid"
```

- [ ] **Step 4: Run the plugin skills test**

```bash
python3 -m pytest tests/test_plugin_skills.py -v
```

Expected: 5 PASS. If `test_no_skills_reference_retired_wrapper_script` fails, check for any missed references.

- [ ] **Step 5: Commit**

```bash
git add skills/
git commit -m "$(cat <<'EOF'
docs(skills): skill docs invoke the generic workflows entrypoint

Skills now reference
  python3 .../workflows/__main__.py --workflow-root <root> <cmd>
instead of the retired
  python3 .../adapters/yoyopod_core/__main__.py <cmd>

The generic form reads the YAML to pick the workflow module, so it works
across workspaces that bind to different workflows later.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

### Phase 5 verification

- [ ] **Full suite + install + live smoke**

```bash
cd /home/radxa/WS/hermes-relay
python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -4
./scripts/install.sh 2>&1 | tail -2
python3 -m workflows --workflow-root /home/radxa/.hermes/workflows/yoyopod status 2>&1 | head -4
```

All three should succeed: tests pass, install succeeds, live status works.

---

## Phase 6 — Polish

Version bump, docs refresh, ADR.

### Task 6.1: Bump `plugin.yaml` version

**Files:**
- Modify: `plugin.yaml`

- [ ] **Step 1: Bump version**

```bash
sed -i 's|version: 0\.1\.0|version: 0.2.0|' plugin.yaml
cat plugin.yaml
```

Verify the file still parses:

```bash
python3 -c "import yaml; print(yaml.safe_load(open('plugin.yaml'))['version'])"
```

Expected: `0.2.0`.

- [ ] **Step 2: Commit**

```bash
git add plugin.yaml
git commit -m "chore: bump plugin version to 0.2.0

Major surface change: workflow-plugin contract + YAML config format.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6.2: Update `README.md` + `docs/architecture.md` + operator cheat sheet

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/operator-cheat-sheet.md`

- [ ] **Step 1: `README.md`**

Replace the "Repo layout" section's `adapters/` references with `workflows/`:

```bash
sed -i \
  -e 's|`adapters/yoyopod_core`|`workflows/code_review`|g' \
  -e 's|adapters/yoyopod_core|workflows/code_review|g' \
  README.md
```

Then manually open `README.md` and adjust any prose that still frames the plugin around a single adapter. Replace with language about the workflow-plugin contract and pluggable workflows.

- [ ] **Step 2: `docs/architecture.md`**

Update any diagrams/prose referring to the `adapters/` layout. Add a short paragraph on the workflow-plugin contract with a link to the spec.

- [ ] **Step 3: `docs/operator-cheat-sheet.md`**

Replace operator CLI commands that still say `adapters/yoyopod_core/__main__.py`:

```bash
sed -i 's|adapters/yoyopod_core/__main__.py|workflows/__main__.py --workflow-root ~/.hermes/workflows/yoyopod|g' docs/operator-cheat-sheet.md
```

- [ ] **Step 4: Commit**

```bash
git add README.md docs/architecture.md docs/operator-cheat-sheet.md
git commit -m "docs: refresh README, architecture, operator cheat sheet for workflows layout

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6.3: Add `CLAUDE.md` section if present

**Files:**
- Modify: `CLAUDE.md` (if present)

- [ ] **Step 1: Check presence + update**

```bash
test -f CLAUDE.md && grep -n "adapters/yoyopod_core\|adapters\.yoyopod_core" CLAUDE.md
```

If present with references, update them:

```bash
sed -i \
  -e 's|adapters/yoyopod_core|workflows/code_review|g' \
  -e 's|adapters\.yoyopod_core|workflows.code_review|g' \
  CLAUDE.md
```

- [ ] **Step 2: Commit**

```bash
test -f CLAUDE.md && git add CLAUDE.md && git commit -m "docs(CLAUDE.md): reflect workflows/ layout

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>" || echo "no CLAUDE.md to update"
```

### Task 6.4: Add ADR-0002 capturing the decision

**Files:**
- Create: `docs/adr/ADR-0002-workflows-contract.md`

- [ ] **Step 1: Write the ADR**

```markdown
# ADR-0002: Workflows contract + YAML config surface

**Status:** Accepted (2026-04-24)
**Supersedes:** ADR-0001 (adapters/<project>/ layout)

## Context

The hermes-relay plugin initially hosted one adapter per project
(`adapters/yoyopod_core/`). This conflated two concepts:

- **Workflow type** (Code-Review, Testing, Security-Review, ...) — the engine
- **Workspace instance** (YoyoPod, future projects) — the runtime binding

Operators also could not tune workflow behavior (coder model, reviewer model,
gate policy, ...) without editing Python, and the partial JSON config that
did exist accumulated aliases from implementation history.

## Decision

Re-frame the plugin around a **workflow-plugin contract**:

- Workflows live at `workflows/<name>/` as Python packages.
- Each package exposes a five-attribute contract: `NAME`,
  `SUPPORTED_SCHEMA_VERSIONS`, `CONFIG_SCHEMA_PATH`, `make_workspace`,
  `cli_main`.
- A dispatcher at `workflows/__init__.py` reads
  `<workspace>/config/workflow.yaml`, validates against the workflow's
  JSON Schema, and hands off to `cli_main`.
- Runtimes (how we talk to models) are pluggable behind a `Runtime`
  `Protocol`; `acpx-codex` and `claude-cli` are the initial
  implementations. Adding a new runtime (Kimi, Gemini, HTTP-API) is a
  new module + schema entry; no dispatcher change.
- The workspace accessor exposes named runtime instances via
  `ws.runtime(name)`.
- The YAML config cleanly separates **role** (coder, reviewer) from
  **identity** (name, model) from **runtime** (plumbing); no more
  Claude-prefixed and inter-review-agent-prefixed aliases for the same
  concept.

## Consequences

Positive:

- Adding a new workflow (Testing, Security-Review, ...) is a new
  directory implementing the five-attribute contract; no plugin-level
  changes required.
- Swapping the coder to a different model/runtime is a config-only
  change in most cases.
- One canonical CLI surface per workspace: `python3 -m workflows
  --workflow-root <root> <cmd>`.
- External callers (systemd, cron, runtime.py subprocess spawns) never
  couple to a specific workflow module.

Negative:

- Config file shape changed; operators with custom configs must migrate
  via `scripts/migrate_config.py`.
- `plugin_entrypoint_path` now returns the generic dispatcher, not the
  per-workflow module; callers that need to pin a workflow use the
  `-m workflows.<name>` form.

## References

- Design spec:
  `docs/superpowers/specs/2026-04-24-workflows-contract-and-code-review-design.md`
- Implementation plan:
  `docs/superpowers/plans/2026-04-24-workflows-contract-and-code-review.md`
```

- [ ] **Step 2: Commit**

```bash
git add docs/adr/ADR-0002-workflows-contract.md
git commit -m "docs(adr): ADR-0002 captures workflows-contract decision

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Phase 6 verification

- [ ] **Final full suite + install + live smoke**

```bash
cd /home/radxa/WS/hermes-relay
python3 -m pytest tests/ --ignore=tests/test_runtime_tools_alerts.py -q 2>&1 | tail -4
./scripts/install.sh 2>&1 | tail -2
python3 -m workflows --workflow-root /home/radxa/.hermes/workflows/yoyopod status --json 2>&1 | python3 -c "import sys, json; d=json.loads(sys.stdin.read()); print(f'health={d[\"health\"]} engineOwner={d[\"engineOwner\"]}')"
python3 -m workflows --workflow-root /home/radxa/.hermes/workflows/yoyopod tick --json | python3 -c "import sys, json; d=json.loads(sys.stdin.read()); print(f'action={d[\"action\"][\"type\"]} reason={d[\"action\"].get(\"reason\")}')"
```

Expected: all green. Target ≥ 225 tests passing (baseline 203 + dispatcher 10 + init 3 + runtimes ~12 + schema 5 + migrate 1 + workspace accessor 2 ≈ 236 before deletions; net after Phase 5 deletion of 203 adapters-side tests ≈ +30 net).

- [ ] **Acceptance-criteria audit**

Walk through each criterion in the spec's "Acceptance criteria" section and verify:

| # | Criterion | Verification |
|---|---|---|
| 1 | `./scripts/install.sh` installs `workflows/`; old `adapters/` is gone | `ls ~/.hermes/plugins/hermes-relay/workflows; ls ~/.hermes/plugins/hermes-relay/adapters 2>&1` |
| 2 | `python3 -m workflows --workflow-root <root> status --json` matches today's output | Diff against a pre-migration capture |
| 3 | `python3 -m workflows.code_review --workflow-root <root> tick --json` works | Run it, assert JSON parses |
| 4 | `workflow.yaml` exists; `yoyopod-workflow.json` doesn't | `ls ~/.hermes/workflows/yoyopod/config/` |
| 5 | Live workflow operates end-to-end with no behavior change | Watch `tick` for several cycles; compare against pre-migration audit log |
| 6 | `pytest` reports ≥ 225 passing tests | `pytest -q \| tail -1` |
| 7 | Adding a new runtime requires only `workflows/code_review/runtimes/<kind>.py` + YAML entry | Manually scaffold an `http_api.py` stub; verify it loads via `build_runtimes` |

All seven pass → the plan is complete.

---

## Post-implementation hygiene

- [ ] **Push commits**

```bash
cd /home/radxa/WS/hermes-relay
git log origin/main..HEAD --oneline
git push origin main
```

- [ ] **Tag the 0.2.0 release**

```bash
git tag -a v0.2.0 -m "Workflows contract + code-review workflow

See docs/superpowers/specs/2026-04-24-workflows-contract-and-code-review-design.md"
git push origin v0.2.0
```

- [ ] **Remove the pre-migration config backup after a cool-down period**

```bash
# After a week of successful operation with no regressions:
# rm /home/radxa/.hermes/workflows/yoyopod/config/yoyopod-workflow.json.pre-yaml-migration
```
