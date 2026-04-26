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
