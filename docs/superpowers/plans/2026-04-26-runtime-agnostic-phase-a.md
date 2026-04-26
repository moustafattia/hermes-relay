# Runtime-Agnostic Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Make the code-review workflow's agent invocations operator-configurable via a generic `dispatch_agent()` + config-driven `command:` and `prompt:` overrides + a third (`hermes-agent`) runtime kind.

**Architecture:** Reuse the existing `Runtime` Protocol / `@register` registry / `build_runtimes()` factory. Add a new dispatcher module that owns prompt resolution, placeholder substitution, and command invocation. Runtimes gain a `run_command(...)` method; existing `run_prompt(...)` is preserved for back-compat fallback.

**Tech Stack:** Python 3.11, JSON Schema (jsonschema), pyyaml, pytest.

**Spec:** `docs/superpowers/specs/2026-04-26-runtime-agnostic-phase-a-design.md`

**Worktree:** `/home/radxa/WS/hermes-relay/.claude/worktrees/runtime-agnostic-phase-a` on branch `claude/runtime-agnostic-phase-a` from main `4bdb15b`. Baseline 450 tests passing. Use `/usr/bin/python3` (system Python 3.11 has pyyaml + jsonschema).

---

## File Structure

**New files:**
- `workflows/code_review/runtimes/hermes_agent.py` — third runtime adapter
- `workflows/code_review/dispatch.py` — `dispatch_agent()` + `DispatchConfigError` + prompt resolution + placeholder substitution
- `tests/test_runtime_agnostic_phase_a.py` — adapter + dispatcher tests
- `tests/test_runtime_agnostic_schema.py` — schema validation tests
- `workflows/code_review/prompts/coder.md` — renamed copy of `coder-dispatch.md`
- `workflows/code_review/prompts/internal-reviewer.md` — renamed copy of `internal-review-strict.md`

**Modified files:**
- `workflows/code_review/schema.yaml` — add `hermes-agent-runtime`, optional `command:` + `prompt:`
- `workflows/code_review/runtimes/__init__.py` — extend `Runtime` Protocol with `run_command(...)`; import `hermes_agent` in `build_runtimes`
- `workflows/code_review/runtimes/acpx_codex.py` — add `run_command(...)`
- `workflows/code_review/runtimes/claude_cli.py` — add `run_command(...)`
- `workflows/code_review/prompts.py` — update `_load_template` calls to new filenames
- `skills/operator/SKILL.md` — document new config surface

**Deleted files:**
- `workflows/code_review/prompts/coder-dispatch.md` (renamed)
- `workflows/code_review/prompts/internal-review-strict.md` (renamed)

---

## Task 1: Rename bundled prompts

**Files:**
- Rename: `workflows/code_review/prompts/coder-dispatch.md` → `workflows/code_review/prompts/coder.md`
- Rename: `workflows/code_review/prompts/internal-review-strict.md` → `workflows/code_review/prompts/internal-reviewer.md`
- Modify: `workflows/code_review/prompts.py:140` (`_load_template("coder-dispatch")` → `_load_template("coder")`)
- Modify: `workflows/code_review/prompts.py:230` (`_load_template("internal-review-strict")` → `_load_template("internal-reviewer")`)

- [ ] **Step 1: Rename the two prompt files**

```bash
cd /home/radxa/WS/hermes-relay/.claude/worktrees/runtime-agnostic-phase-a
git mv workflows/code_review/prompts/coder-dispatch.md workflows/code_review/prompts/coder.md
git mv workflows/code_review/prompts/internal-review-strict.md workflows/code_review/prompts/internal-reviewer.md
```

- [ ] **Step 2: Update _load_template calls**

In `workflows/code_review/prompts.py`, change:
```python
return _load_template("coder-dispatch").format(...)
```
to
```python
return _load_template("coder").format(...)
```

And change:
```python
return _load_template("internal-review-strict").format(...)
```
to
```python
return _load_template("internal-reviewer").format(...)
```

- [ ] **Step 3: Run prompt-related tests to verify no regression**

```bash
/usr/bin/python3 -m pytest tests/ -k prompt -v
```
Expected: all existing prompt tests pass.

- [ ] **Step 4: Run full test suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```
Expected: 450 passed (baseline preserved).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: rename bundled coder + internal-reviewer prompts to role-based filenames

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Extend Runtime Protocol with run_command

**Files:**
- Modify: `workflows/code_review/runtimes/__init__.py:41-79` (Runtime Protocol)
- Modify: `workflows/code_review/runtimes/acpx_codex.py` (add run_command)
- Modify: `workflows/code_review/runtimes/claude_cli.py` (add run_command)
- Test: `tests/test_runtime_agnostic_phase_a.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_runtime_agnostic_phase_a.py`:

```python
"""Phase A runtime-agnostic tests: hermes-agent adapter + dispatch_agent."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from workflows.code_review.runtimes import _RUNTIME_KINDS, SessionHandle


def test_acpx_runtime_has_run_command():
    from workflows.code_review.runtimes.acpx_codex import AcpxCodexRuntime
    assert hasattr(AcpxCodexRuntime, "run_command")


def test_claude_cli_runtime_has_run_command():
    from workflows.code_review.runtimes.claude_cli import ClaudeCliRuntime
    assert hasattr(ClaudeCliRuntime, "run_command")


def test_acpx_run_command_invokes_run(tmp_path):
    from workflows.code_review.runtimes.acpx_codex import AcpxCodexRuntime

    fake_run = MagicMock(return_value=MagicMock(stdout="hello"))
    rt = AcpxCodexRuntime(
        {
            "kind": "acpx-codex",
            "session-idle-freshness-seconds": 900,
            "session-idle-grace-seconds": 1800,
            "session-nudge-cooldown-seconds": 600,
        },
        run=fake_run,
        run_json=MagicMock(),
    )
    out = rt.run_command(worktree=tmp_path, command_argv=["acpx", "echo", "hi"])
    assert out == "hello"
    fake_run.assert_called_once()
    args, kwargs = fake_run.call_args
    assert args[0] == ["acpx", "echo", "hi"]
    assert kwargs.get("cwd") == tmp_path


def test_claude_cli_run_command_invokes_run(tmp_path):
    from workflows.code_review.runtimes.claude_cli import ClaudeCliRuntime

    fake_run = MagicMock(return_value=MagicMock(stdout="ok"))
    rt = ClaudeCliRuntime(
        {"kind": "claude-cli", "max-turns-per-invocation": 24, "timeout-seconds": 1200},
        run=fake_run,
    )
    out = rt.run_command(worktree=tmp_path, command_argv=["claude", "--print", "hi"])
    assert out == "ok"
    fake_run.assert_called_once()
    args, kwargs = fake_run.call_args
    assert args[0] == ["claude", "--print", "hi"]
    assert kwargs.get("cwd") == tmp_path
```

- [ ] **Step 2: Run test to verify it fails**

```bash
/usr/bin/python3 -m pytest tests/test_runtime_agnostic_phase_a.py -v
```
Expected: FAIL with `AttributeError: type object 'AcpxCodexRuntime' has no attribute 'run_command'`.

- [ ] **Step 3: Add run_command to Runtime Protocol**

In `workflows/code_review/runtimes/__init__.py`, add to the `Runtime` Protocol class (after `close_session`):

```python
    def run_command(
        self,
        *,
        worktree: Path,
        command_argv: list[str],
        env: dict[str, str] | None = None,
    ) -> str: ...
```

- [ ] **Step 4: Implement run_command in AcpxCodexRuntime**

In `workflows/code_review/runtimes/acpx_codex.py`, append a method to the class:

```python
    def run_command(
        self,
        *,
        worktree: Path,
        command_argv: list[str],
        env: dict | None = None,
    ) -> str:
        """Execute a fully-formed argv against this runtime's working dir.

        Used when an agent role supplies a `command:` override in workflow.yaml.
        Session plumbing (ensure/close) is the caller's responsibility.
        """
        completed = self._run(command_argv, cwd=worktree)
        return getattr(completed, "stdout", "") or ""
```

- [ ] **Step 5: Implement run_command in ClaudeCliRuntime**

In `workflows/code_review/runtimes/claude_cli.py`, append a method to the class:

```python
    def run_command(
        self,
        *,
        worktree: Path,
        command_argv: list[str],
        env: dict | None = None,
    ) -> str:
        """Execute a fully-formed argv via the configured timeout."""
        completed = self._run(command_argv, cwd=worktree, timeout=self._timeout)
        return getattr(completed, "stdout", "") or ""
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
/usr/bin/python3 -m pytest tests/test_runtime_agnostic_phase_a.py -v
```
Expected: 4 passed.

- [ ] **Step 7: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -5
```
Expected: 454 passed.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(runtimes): add run_command(...) to Runtime Protocol + adapters

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Add hermes-agent runtime adapter

**Files:**
- Create: `workflows/code_review/runtimes/hermes_agent.py`
- Modify: `workflows/code_review/runtimes/__init__.py` (import hermes_agent in build_runtimes)
- Test: `tests/test_runtime_agnostic_phase_a.py` (extend)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_runtime_agnostic_phase_a.py`:

```python
def test_hermes_agent_runtime_registered():
    # Trigger registration
    from workflows.code_review.runtimes import hermes_agent  # noqa: F401
    assert "hermes-agent" in _RUNTIME_KINDS


def test_hermes_agent_run_command(tmp_path):
    from workflows.code_review.runtimes.hermes_agent import HermesAgentRuntime

    fake_run = MagicMock(return_value=MagicMock(stdout="agent-out"))
    rt = HermesAgentRuntime({"kind": "hermes-agent"}, run=fake_run, run_json=None)
    out = rt.run_command(
        worktree=tmp_path,
        command_argv=["hermes-agent", "run", "--workspace", str(tmp_path)],
    )
    assert out == "agent-out"


def test_hermes_agent_ensure_session_is_noop(tmp_path):
    from workflows.code_review.runtimes.hermes_agent import HermesAgentRuntime

    rt = HermesAgentRuntime({"kind": "hermes-agent"}, run=MagicMock(), run_json=None)
    handle = rt.ensure_session(
        worktree=tmp_path, session_name="x", model="m"
    )
    assert handle.record_id is None
    assert handle.session_id is None
    assert handle.name == "x"


def test_hermes_agent_assess_health_always_healthy(tmp_path):
    from workflows.code_review.runtimes.hermes_agent import HermesAgentRuntime

    rt = HermesAgentRuntime({"kind": "hermes-agent"}, run=MagicMock(), run_json=None)
    h = rt.assess_health(None, worktree=tmp_path)
    assert h.healthy is True


def test_build_runtimes_accepts_hermes_agent():
    from workflows.code_review.runtimes import build_runtimes

    cfg = {"hermes-default": {"kind": "hermes-agent"}}
    rts = build_runtimes(cfg, run=MagicMock(), run_json=MagicMock())
    assert "hermes-default" in rts
```

- [ ] **Step 2: Run to verify failure**

```bash
/usr/bin/python3 -m pytest tests/test_runtime_agnostic_phase_a.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'workflows.code_review.runtimes.hermes_agent'`.

- [ ] **Step 3: Create hermes_agent.py**

Create `workflows/code_review/runtimes/hermes_agent.py`:

```python
"""Hermes-agent runtime adapter.

One-shot, no persistent session: ``ensure_session`` / ``close_session`` are
no-ops, ``assess_health`` always returns healthy. The actual command is
supplied by the operator via ``command:`` on the runtime profile or the
agent role; this adapter only provides session plumbing (none) and the
``run_command`` execution path.
"""
from __future__ import annotations

from pathlib import Path

from workflows.code_review.runtimes import (
    SessionHandle,
    SessionHealth,
    register,
)


@register("hermes-agent")
class HermesAgentRuntime:
    """Runs prompts by invoking a hermes-agent CLI defined in config.

    Config shape (YAML):
        kind: hermes-agent
        command: ["hermes-agent", "run", "--workspace", "{worktree}",
                  "--model", "{model}", "--prompt-file", "{prompt_path}"]
    """

    def __init__(self, cfg: dict, *, run, run_json=None):
        self._cfg = cfg
        self._run = run

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
        # No built-in prompt path — operators must supply `command:` to use
        # this runtime. Surface the misconfiguration clearly.
        raise RuntimeError(
            "hermes-agent runtime requires a `command:` override on the runtime "
            "profile or agent role; no built-in invocation is provided."
        )

    def assess_health(
        self,
        session_meta: dict | None,
        *,
        worktree: Path | None,
        now_epoch: int | None = None,
    ) -> SessionHealth:
        return SessionHealth(healthy=True, reason=None, last_used_at=None)

    def close_session(self, *, worktree: Path, session_name: str) -> None:
        return None

    def run_command(
        self,
        *,
        worktree: Path,
        command_argv: list[str],
        env: dict | None = None,
    ) -> str:
        completed = self._run(command_argv, cwd=worktree)
        return getattr(completed, "stdout", "") or ""
```

- [ ] **Step 4: Register in build_runtimes**

In `workflows/code_review/runtimes/__init__.py`, add to the lazy-import block in `build_runtimes` (around line 113):

```python
    from workflows.code_review.runtimes import acpx_codex  # noqa: F401
    from workflows.code_review.runtimes import claude_cli  # noqa: F401
    from workflows.code_review.runtimes import hermes_agent  # noqa: F401
```

- [ ] **Step 5: Run tests**

```bash
/usr/bin/python3 -m pytest tests/test_runtime_agnostic_phase_a.py -v
```
Expected: 9 passed.

- [ ] **Step 6: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -5
```
Expected: 459 passed.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(runtimes): add hermes-agent runtime adapter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Schema extensions

**Files:**
- Modify: `workflows/code_review/schema.yaml`
- Test: `tests/test_runtime_agnostic_schema.py` (new)

- [ ] **Step 1: Write failing tests**

Create `tests/test_runtime_agnostic_schema.py`:

```python
"""Phase A schema validation tests."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "workflows/code_review/schema.yaml"


def _schema():
    return yaml.safe_load(SCHEMA_PATH.read_text())


def _base_config():
    return {
        "workflow": "code-review",
        "schema-version": 1,
        "instance": {"name": "test", "engine-owner": "hermes"},
        "repository": {
            "local-path": "/tmp/x",
            "github-slug": "x/y",
            "active-lane-label": "active",
        },
        "runtimes": {
            "codex-acpx": {
                "kind": "acpx-codex",
                "session-idle-freshness-seconds": 900,
                "session-idle-grace-seconds": 1800,
                "session-nudge-cooldown-seconds": 600,
            },
        },
        "agents": {
            "coder": {
                "default": {"name": "c", "model": "m", "runtime": "codex-acpx"},
            },
            "internal-reviewer": {
                "name": "ir", "model": "m", "runtime": "codex-acpx",
            },
            "external-reviewer": {"enabled": False, "name": "er"},
        },
        "gates": {"internal-review": {}, "external-review": {}, "merge": {}},
        "triggers": {"lane-selector": {"type": "label", "label": "active"}},
        "storage": {"ledger": "x", "health": "x", "audit-log": "x"},
    }


def test_schema_accepts_hermes_agent_runtime():
    cfg = _base_config()
    cfg["runtimes"]["hm"] = {"kind": "hermes-agent"}
    Draft7Validator(_schema()).validate(cfg)


def test_schema_accepts_command_override_on_runtime():
    cfg = _base_config()
    cfg["runtimes"]["codex-acpx"]["command"] = ["acpx", "{model}"]
    Draft7Validator(_schema()).validate(cfg)


def test_schema_accepts_command_override_on_coder_tier():
    cfg = _base_config()
    cfg["agents"]["coder"]["default"]["command"] = ["acpx", "{model}", "{prompt_path}"]
    Draft7Validator(_schema()).validate(cfg)


def test_schema_accepts_prompt_override_on_internal_reviewer():
    cfg = _base_config()
    cfg["agents"]["internal-reviewer"]["prompt"] = "prompts/internal-reviewer.md"
    Draft7Validator(_schema()).validate(cfg)


def test_schema_rejects_empty_command_array():
    from jsonschema import ValidationError

    cfg = _base_config()
    cfg["runtimes"]["codex-acpx"]["command"] = []
    with pytest.raises(ValidationError):
        Draft7Validator(_schema()).validate(cfg)


def test_existing_yoyopod_workflow_yaml_still_validates():
    yoyopod = Path(os.path.expanduser("~/.hermes/workflows/yoyopod/config/workflow.yaml"))
    if not yoyopod.exists():
        pytest.skip("yoyopod workspace not present on this host")
    cfg = yaml.safe_load(yoyopod.read_text())
    Draft7Validator(_schema()).validate(cfg)
```

- [ ] **Step 2: Run to verify failure**

```bash
/usr/bin/python3 -m pytest tests/test_runtime_agnostic_schema.py -v
```
Expected: FAIL on `test_schema_accepts_hermes_agent_runtime` (no such definition).

- [ ] **Step 3: Add hermes-agent-runtime to schema oneOf**

In `workflows/code_review/schema.yaml`, the `runtimes:` block (lines 36-42), update `oneOf`:

```yaml
  runtimes:
    type: object
    minProperties: 1
    additionalProperties:
      oneOf:
        - $ref: "#/definitions/acpx-codex-runtime"
        - $ref: "#/definitions/claude-cli-runtime"
        - $ref: "#/definitions/hermes-agent-runtime"
```

- [ ] **Step 4: Add command field to all three runtime definitions**

In the `definitions:` section, add a `command:` property to `acpx-codex-runtime`:

```yaml
  acpx-codex-runtime:
    type: object
    required: [kind, session-idle-freshness-seconds, session-idle-grace-seconds, session-nudge-cooldown-seconds]
    properties:
      kind: {const: acpx-codex}
      session-idle-freshness-seconds: {type: integer, minimum: 1}
      session-idle-grace-seconds: {type: integer, minimum: 1}
      session-nudge-cooldown-seconds: {type: integer, minimum: 1}
      command:
        type: array
        items: {type: string}
        minItems: 1
```

Same `command:` property added to `claude-cli-runtime`. Then add the new definition:

```yaml
  hermes-agent-runtime:
    type: object
    required: [kind]
    properties:
      kind: {const: hermes-agent}
      command:
        type: array
        items: {type: string}
        minItems: 1
```

- [ ] **Step 5: Add command + prompt to coder-tier**

```yaml
  coder-tier:
    type: object
    required: [name, model, runtime]
    properties:
      name: {type: string}
      model: {type: string}
      runtime: {type: string}
      command:
        type: array
        items: {type: string}
        minItems: 1
      prompt: {type: string}
```

- [ ] **Step 6: Add command + prompt to internal-reviewer + advisory-reviewer**

In the `agents:` block, update `internal-reviewer`:

```yaml
      internal-reviewer:
        type: object
        required: [name, model, runtime]
        properties:
          name: {type: string}
          model: {type: string}
          runtime: {type: string}
          freeze-coder-while-running: {type: boolean}
          command:
            type: array
            items: {type: string}
            minItems: 1
          prompt: {type: string}
```

And `advisory-reviewer`:

```yaml
      advisory-reviewer:
        type: object
        required: [enabled, name]
        properties:
          enabled: {type: boolean}
          name: {type: string}
          command:
            type: array
            items: {type: string}
            minItems: 1
          prompt: {type: string}
```

- [ ] **Step 7: Run tests**

```bash
/usr/bin/python3 -m pytest tests/test_runtime_agnostic_schema.py -v
```
Expected: 6 passed (or 5 + 1 skipped if yoyopod not present).

- [ ] **Step 8: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -5
```
Expected: 465 passed.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(schema): add hermes-agent-runtime + optional command/prompt overrides

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: dispatch_agent module

**Files:**
- Create: `workflows/code_review/dispatch.py`
- Test: `tests/test_runtime_agnostic_phase_a.py` (extend)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_runtime_agnostic_phase_a.py`:

```python
def _make_workspace(tmp_path, agents_cfg, runtimes_cfg, fake_run, *, workspace_dir=None):
    """Build a minimal workspace stand-in for dispatcher tests."""
    from workflows.code_review.runtimes import build_runtimes

    runtimes = build_runtimes(runtimes_cfg, run=fake_run, run_json=MagicMock())
    cfg = {"agents": agents_cfg, "runtimes": runtimes_cfg}
    ws = MagicMock()
    ws.config = cfg
    ws.runtime = lambda name: runtimes[name]
    ws.path = workspace_dir or tmp_path
    return ws


def _runtimes_cfg():
    return {
        "codex-acpx": {
            "kind": "acpx-codex",
            "session-idle-freshness-seconds": 900,
            "session-idle-grace-seconds": 1800,
            "session-nudge-cooldown-seconds": 600,
            "command": ["acpx", "--model", "{model}", "--cwd", "{worktree}",
                        "codex", "prompt", "-s", "{session_name}", "{prompt_path}"],
        },
    }


def test_dispatch_agent_substitutes_placeholders(tmp_path):
    from workflows.code_review.dispatch import dispatch_agent

    fake_run = MagicMock(return_value=MagicMock(stdout="ok"))
    agents = {
        "coder": {
            "default": {"name": "c", "model": "gpt-5", "runtime": "codex-acpx"},
        },
    }
    ws = _make_workspace(tmp_path, agents, _runtimes_cfg(), fake_run)
    out = dispatch_agent(
        workspace=ws, role="coder", tier="default",
        rendered_prompt="hi", session_name="lane-42", worktree=tmp_path,
    )
    assert out == "ok"
    argv = fake_run.call_args[0][0]
    assert "gpt-5" in argv
    assert str(tmp_path) in argv
    assert "lane-42" in argv
    # one element should be the rendered-prompt file path
    prompt_files = [a for a in argv if a.endswith(".txt")]
    assert len(prompt_files) == 1
    assert Path(prompt_files[0]).read_text() == "hi"


def test_dispatch_agent_unknown_role_raises(tmp_path):
    from workflows.code_review.dispatch import dispatch_agent, DispatchConfigError

    ws = _make_workspace(tmp_path, {"coder": {}}, _runtimes_cfg(), MagicMock())
    with pytest.raises(DispatchConfigError):
        dispatch_agent(
            workspace=ws, role="nonexistent",
            rendered_prompt="x", session_name="s", worktree=tmp_path,
        )


def test_dispatch_agent_uses_runtime_default_when_no_override(tmp_path):
    """Agent without command: -> runtime profile's command."""
    from workflows.code_review.dispatch import dispatch_agent

    fake_run = MagicMock(return_value=MagicMock(stdout="ok"))
    agents = {"coder": {"default": {"name": "c", "model": "m", "runtime": "codex-acpx"}}}
    ws = _make_workspace(tmp_path, agents, _runtimes_cfg(), fake_run)
    dispatch_agent(
        workspace=ws, role="coder", tier="default",
        rendered_prompt="x", session_name="s", worktree=tmp_path,
    )
    argv = fake_run.call_args[0][0]
    assert argv[0] == "acpx"  # runtime default kicked in


def test_dispatch_agent_role_command_overrides_runtime(tmp_path):
    """Agent's command: fully replaces runtime command."""
    from workflows.code_review.dispatch import dispatch_agent

    fake_run = MagicMock(return_value=MagicMock(stdout="ok"))
    agents = {
        "coder": {
            "default": {
                "name": "c", "model": "m", "runtime": "codex-acpx",
                "command": ["my-tool", "--prompt", "{prompt_path}"],
            },
        },
    }
    ws = _make_workspace(tmp_path, agents, _runtimes_cfg(), fake_run)
    dispatch_agent(
        workspace=ws, role="coder", tier="default",
        rendered_prompt="x", session_name="s", worktree=tmp_path,
    )
    argv = fake_run.call_args[0][0]
    assert argv[0] == "my-tool"


def test_dispatch_agent_resolves_workspace_prompt_override(tmp_path):
    """When <workspace>/config/prompts/<role>.md exists, dispatcher picks it."""
    from workflows.code_review.dispatch import resolve_prompt_template_path

    cfg_dir = tmp_path / "config"
    (cfg_dir / "prompts").mkdir(parents=True)
    custom = cfg_dir / "prompts" / "coder.md"
    custom.write_text("workspace override")
    ws = MagicMock()
    ws.path = tmp_path
    ws.config = {"agents": {"coder": {"default": {"runtime": "codex-acpx"}}}}
    p = resolve_prompt_template_path(workspace=ws, role="coder", agent_cfg={})
    assert p == custom


def test_dispatch_agent_resolves_explicit_prompt_path(tmp_path):
    """Agent's `prompt:` key wins over workspace override."""
    from workflows.code_review.dispatch import resolve_prompt_template_path

    cfg_dir = tmp_path / "config"
    (cfg_dir / "prompts").mkdir(parents=True)
    (cfg_dir / "prompts" / "coder.md").write_text("workspace")
    explicit = tmp_path / "explicit-coder.md"
    explicit.write_text("explicit")
    ws = MagicMock()
    ws.path = tmp_path
    ws.config = {"agents": {}}
    p = resolve_prompt_template_path(
        workspace=ws, role="coder",
        agent_cfg={"prompt": str(explicit)},
    )
    assert p == explicit


def test_dispatch_agent_falls_back_to_bundled(tmp_path):
    """No explicit, no workspace override -> bundled default."""
    from workflows.code_review.dispatch import resolve_prompt_template_path

    ws = MagicMock()
    ws.path = tmp_path
    ws.config = {"agents": {}}
    p = resolve_prompt_template_path(workspace=ws, role="coder", agent_cfg={})
    assert p.name == "coder.md"
    assert "workflows/code_review/prompts" in str(p)
```

- [ ] **Step 2: Run to verify failure**

```bash
/usr/bin/python3 -m pytest tests/test_runtime_agnostic_phase_a.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'workflows.code_review.dispatch'`.

- [ ] **Step 3: Create dispatch.py**

Create `workflows/code_review/dispatch.py`:

```python
"""Generic agent dispatcher.

Resolves runtime + command + prompt-template path from workspace config,
materializes the rendered prompt to a file inside the worktree, fills
placeholders in the command argv, and invokes the runtime.

Phase A only — no model-tied call sites. Coding/review prompts are still
rendered by the legacy ``prompts.py`` helpers; the rendered string is
passed in as ``rendered_prompt`` and written to a temp file before the
runtime is invoked.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

_BUNDLED_PROMPTS = Path(__file__).parent / "prompts"


class DispatchConfigError(Exception):
    """Raised on misconfigured agent role / runtime / command override."""


def _agent_cfg(workspace, role: str, tier: str | None) -> dict:
    agents = (workspace.config or {}).get("agents") or {}
    if role not in agents:
        raise DispatchConfigError(f"unknown agent role: {role!r}")
    role_cfg = agents[role]

    # coder is tiered (map of tier -> cfg); other roles are flat dicts.
    if role == "coder":
        if not tier:
            raise DispatchConfigError(f"role {role!r} requires a tier")
        if tier not in role_cfg:
            raise DispatchConfigError(f"unknown tier {tier!r} for role {role!r}")
        return role_cfg[tier]
    return role_cfg


def resolve_prompt_template_path(
    *,
    workspace,
    role: str,
    agent_cfg: dict,
) -> Path:
    """Resolution order:

    1. agent_cfg['prompt']        — explicit override (absolute or relative
                                    to workspace.path/config)
    2. workspace.path/config/prompts/<role>.md
    3. bundled prompts/<role>.md
    """
    explicit = agent_cfg.get("prompt")
    if explicit:
        p = Path(explicit)
        if not p.is_absolute() and getattr(workspace, "path", None):
            p = Path(workspace.path) / "config" / explicit
        if not p.exists():
            raise DispatchConfigError(f"prompt path does not exist: {p}")
        return p

    if getattr(workspace, "path", None):
        ws_override = Path(workspace.path) / "config" / "prompts" / f"{role}.md"
        if ws_override.exists():
            return ws_override

    bundled = _BUNDLED_PROMPTS / f"{role}.md"
    if not bundled.exists():
        raise DispatchConfigError(
            f"no prompt template found for role {role!r} "
            f"(checked workspace override and {bundled})"
        )
    return bundled


def _materialize_prompt(*, worktree: Path, role: str, tier: str | None, rendered_prompt: str) -> Path:
    """Write the already-rendered prompt to a deterministic file under
    <worktree>/.daedalus/dispatch/, return the path."""
    out_dir = Path(worktree) / ".daedalus" / "dispatch"
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(rendered_prompt.encode("utf-8")).hexdigest()[:12]
    label = f"{role}-{tier}" if tier else role
    out = out_dir / f"{label}-{digest}.txt"
    out.write_text(rendered_prompt, encoding="utf-8")
    return out


def _resolve_command(*, agent_cfg: dict, runtime_cfg: dict) -> list[str] | None:
    """Agent command wins; falls back to runtime profile command; None if neither."""
    cmd = agent_cfg.get("command")
    if cmd:
        return list(cmd)
    cmd = runtime_cfg.get("command")
    if cmd:
        return list(cmd)
    return None


def _substitute(argv: list[str], values: dict[str, str]) -> list[str]:
    """Replace {key} placeholders in each argv element. Unknown placeholders
    pass through unchanged so adapters can interpret them."""
    out = []
    for a in argv:
        s = a
        for k, v in values.items():
            s = s.replace("{" + k + "}", v)
        out.append(s)
    return out


def dispatch_agent(
    *,
    workspace,
    role: str,
    rendered_prompt: str,
    session_name: str,
    worktree: Path,
    tier: str | None = None,
    extra_placeholders: dict[str, str] | None = None,
) -> str:
    """Resolve config, run the agent, return stdout.

    Behavior:
      - Resolves agent role (tiered for 'coder', flat otherwise).
      - Resolves runtime via ``workspace.runtime(<name>)``.
      - Resolves command (agent override -> runtime default -> None).
      - If a command is present: materializes ``rendered_prompt`` to a file,
        substitutes placeholders, invokes ``runtime.run_command(...)``.
      - If no command is present: invokes ``runtime.run_prompt(...)`` with the
        rendered prompt as a string (preserves pre-Phase-A behavior).
    """
    cfg = _agent_cfg(workspace, role, tier)
    runtime_name = cfg.get("runtime")
    if not runtime_name:
        raise DispatchConfigError(f"agent {role!r}/{tier!r} has no runtime")
    runtime = workspace.runtime(runtime_name)
    runtimes_cfg = (workspace.config or {}).get("runtimes") or {}
    runtime_cfg = runtimes_cfg.get(runtime_name) or {}
    model = cfg.get("model") or ""

    command = _resolve_command(agent_cfg=cfg, runtime_cfg=runtime_cfg)

    if command is None:
        # Legacy path: runtime owns the invocation.
        return runtime.run_prompt(
            worktree=worktree,
            session_name=session_name,
            prompt=rendered_prompt,
            model=model,
        )

    # Validate prompt template resolution even if not used in the command —
    # this surfaces config mistakes early.
    resolve_prompt_template_path(workspace=workspace, role=role, agent_cfg=cfg)

    prompt_path = _materialize_prompt(
        worktree=worktree, role=role, tier=tier, rendered_prompt=rendered_prompt,
    )
    placeholders = {
        "model": model,
        "prompt_path": str(prompt_path),
        "worktree": str(worktree),
        "session_name": session_name,
    }
    if extra_placeholders:
        placeholders.update(extra_placeholders)

    argv = _substitute(command, placeholders)
    return runtime.run_command(worktree=worktree, command_argv=argv)
```

- [ ] **Step 4: Run dispatcher tests**

```bash
/usr/bin/python3 -m pytest tests/test_runtime_agnostic_phase_a.py -v
```
Expected: all dispatcher tests pass (≈16 total in this file).

- [ ] **Step 5: Run full suite**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -5
```
Expected: ≥471 passed.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add dispatch_agent + prompt resolution + placeholder substitution

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Operator docs

**Files:**
- Modify: `skills/operator/SKILL.md` (or create section if missing)

- [ ] **Step 1: Add a section documenting the new config surface**

Locate `skills/operator/SKILL.md`. Append a new section near the existing `runtimes:` documentation:

````markdown
## Runtime + agent config (Phase A — runtime-agnostic)

Each agent role chooses a runtime, optionally a `command:` array, and optionally a `prompt:` template path.

**Runtime profile** declares a default invocation:

```yaml
runtimes:
  codex-acpx:
    kind: acpx-codex
    command: ["acpx", "--model", "{model}", "--cwd", "{worktree}",
              "codex", "prompt", "-s", "{session_name}", "{prompt_path}"]
    session-idle-freshness-seconds: 900
    session-idle-grace-seconds: 1800
    session-nudge-cooldown-seconds: 600
```

**Agent role** picks a runtime and optionally overrides `command:` (full replacement) and/or `prompt:` (template path):

```yaml
agents:
  coder:
    default:
      runtime: codex-acpx
      model: gpt-5
      # prompt: implied as <workspace>/config/prompts/coder.md,
      #         falls back to bundled prompts/coder.md
    high:
      runtime: codex-acpx
      model: gpt-5
      command: ["acpx", "--model", "{model}", "--cwd", "{worktree}",
                "codex", "prompt", "-s", "{session_name}",
                "--reasoning", "high", "{prompt_path}"]
```

**Placeholders** filled by the dispatcher:
- `{model}` — agent's `model:` value
- `{prompt_path}` — absolute path to the rendered prompt file
- `{worktree}` — lane worktree directory
- `{session_name}` — lane session identifier

**Prompt resolution order** (highest priority first):
1. `prompt:` on the agent role (absolute or relative to `<workspace>/config/`)
2. `<workspace>/config/prompts/<role>.md`
3. Bundled `workflows/code_review/prompts/<role>.md`

**Runtime kinds:**
- `acpx-codex` — persistent Codex sessions via `acpx`
- `claude-cli` — one-shot Claude CLI invocations
- `hermes-agent` — operator-supplied hermes-agent CLI; requires `command:` (no built-in invocation)

To swap a coder from Codex to Claude, change one line:

```yaml
agents:
  coder:
    default:
      runtime: claude-oneshot   # was: codex-acpx
      model: claude-sonnet-4
```

No code changes required.
````

- [ ] **Step 2: Run full suite (no test impact, but check)**

```bash
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -5
```
Expected: ≥471 passed.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs(operator): document runtime/command/prompt config surface

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] **Run full suite once more**

```bash
cd /home/radxa/WS/hermes-relay/.claude/worktrees/runtime-agnostic-phase-a
/usr/bin/python3 -m pytest tests/ 2>&1 | tail -10
```
Expected: ≥471 passed (450 baseline + ≥21 new). Pre-existing `test_runtime_tools_alerts.py` failure (if applicable) unchanged.

- [ ] **Sanity-check live yoyopod config still validates**

```bash
/usr/bin/python3 -c "
import yaml
from pathlib import Path
from jsonschema import Draft7Validator
schema = yaml.safe_load(Path('workflows/code_review/schema.yaml').read_text())
cfg = yaml.safe_load(Path('/home/radxa/.hermes/workflows/yoyopod/config/workflow.yaml').read_text())
Draft7Validator(schema).validate(cfg)
print('yoyopod config valid')
"
```
Expected: `yoyopod config valid`.

- [ ] **Use superpowers:finishing-a-development-branch** to wrap up.
