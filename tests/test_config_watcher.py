"""S-2 tests: ConfigWatcher (mtime-poll hot-reload) — Symphony §6.2."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


_VALID_YAML = textwrap.dedent("""\
    workflow: code-review
    schema-version: 1
    instance:
      name: test-instance
      engine-owner: hermes
    repository:
      local-path: /tmp/test
      github-slug: org/repo
      active-lane-label: active-lane
    runtimes:
      r1:
        kind: claude-cli
        max-turns-per-invocation: 4
        timeout-seconds: 60
    agents:
      coder:
        t1:
          name: coder
          model: claude
          runtime: r1
      internal-reviewer:
        name: internal
        model: claude
        runtime: r1
      external-reviewer:
        enabled: false
        name: external
    gates:
      internal-review: {}
      external-review: {}
      merge: {}
    triggers:
      lane-selector:
        type: github-issue-label
        label: active-lane
    storage:
      ledger: ledger.json
      health: health.json
      audit-log: audit.log
""")


def test_parse_and_validate_returns_snapshot(tmp_path):
    from workflows.code_review.config_watcher import parse_and_validate

    p = tmp_path / "workflow.yaml"
    p.write_text(_VALID_YAML)
    snap = parse_and_validate(p)
    assert snap.config["workflow"] == "code-review"
    assert snap.source_mtime == p.stat().st_mtime
    assert snap.loaded_at > 0


def test_parse_and_validate_raises_on_yaml_syntax_error(tmp_path):
    from workflows.code_review.config_watcher import parse_and_validate, ParseError

    p = tmp_path / "workflow.yaml"
    p.write_text("workflow: [unclosed\n")
    with pytest.raises(ParseError):
        parse_and_validate(p)


def test_parse_and_validate_raises_on_schema_violation(tmp_path):
    from workflows.code_review.config_watcher import parse_and_validate, ValidationError

    p = tmp_path / "workflow.yaml"
    p.write_text("workflow: code-review\n")  # missing required fields
    with pytest.raises(ValidationError):
        parse_and_validate(p)


def _seed_snapshot(tmp_path: Path):
    """Helper: write valid yaml + return (path, snapshot)."""
    from workflows.code_review.config_watcher import parse_and_validate

    p = tmp_path / "workflow.yaml"
    p.write_text(_VALID_YAML)
    return p, parse_and_validate(p)


def test_watcher_poll_swaps_on_mtime_change(tmp_path):
    import os
    from workflows.code_review.config_snapshot import AtomicRef
    from workflows.code_review.config_watcher import ConfigWatcher

    p, initial = _seed_snapshot(tmp_path)
    ref = AtomicRef(initial)
    events: list[tuple[str, dict]] = []
    w = ConfigWatcher(p, ref, lambda t, d: events.append((t, d)))

    # Edit file with a future mtime
    new_yaml = _VALID_YAML.replace("test-instance", "edited-instance")
    p.write_text(new_yaml)
    os.utime(p, (initial.source_mtime + 5, initial.source_mtime + 5))

    w.poll()
    assert ref.get().config["instance"]["name"] == "edited-instance"
    assert any(t == "daedalus.config_reloaded" for t, _ in events)


def test_watcher_poll_no_change_is_noop(tmp_path):
    from workflows.code_review.config_snapshot import AtomicRef
    from workflows.code_review.config_watcher import ConfigWatcher

    p, initial = _seed_snapshot(tmp_path)
    ref = AtomicRef(initial)
    events: list[tuple[str, dict]] = []
    w = ConfigWatcher(p, ref, lambda t, d: events.append((t, d)))

    w.poll()
    w.poll()
    assert ref.get() is initial
    assert events == []


def test_watcher_poll_invalid_yaml_keeps_lkg_and_emits_failure(tmp_path):
    import os
    from workflows.code_review.config_snapshot import AtomicRef
    from workflows.code_review.config_watcher import ConfigWatcher

    p, initial = _seed_snapshot(tmp_path)
    ref = AtomicRef(initial)
    events: list[tuple[str, dict]] = []
    w = ConfigWatcher(p, ref, lambda t, d: events.append((t, d)))

    p.write_text("workflow: [unclosed\n")
    os.utime(p, (initial.source_mtime + 5, initial.source_mtime + 5))

    w.poll()
    assert ref.get() is initial
    assert any(t == "daedalus.config_reload_failed" for t, _ in events)


def test_watcher_poll_schema_invalid_keeps_lkg_and_emits_failure(tmp_path):
    import os
    from workflows.code_review.config_snapshot import AtomicRef
    from workflows.code_review.config_watcher import ConfigWatcher

    p, initial = _seed_snapshot(tmp_path)
    ref = AtomicRef(initial)
    events: list[tuple[str, dict]] = []
    w = ConfigWatcher(p, ref, lambda t, d: events.append((t, d)))

    p.write_text("workflow: code-review\n")  # schema-invalid (missing required fields)
    os.utime(p, (initial.source_mtime + 5, initial.source_mtime + 5))

    w.poll()
    assert ref.get() is initial
    failures = [d for t, d in events if t == "daedalus.config_reload_failed"]
    assert len(failures) == 1
    assert "schema validation" in failures[0]["error"]


def test_watcher_poll_does_not_re_emit_for_same_broken_mtime(tmp_path):
    import os
    from workflows.code_review.config_snapshot import AtomicRef
    from workflows.code_review.config_watcher import ConfigWatcher

    p, initial = _seed_snapshot(tmp_path)
    ref = AtomicRef(initial)
    events: list[tuple[str, dict]] = []
    w = ConfigWatcher(p, ref, lambda t, d: events.append((t, d)))

    p.write_text("workflow: [unclosed\n")
    os.utime(p, (initial.source_mtime + 5, initial.source_mtime + 5))

    w.poll()
    w.poll()
    w.poll()

    failures = [t for t, _ in events if t == "daedalus.config_reload_failed"]
    assert len(failures) == 1  # only the first tick re-attempted parsing


def test_watcher_poll_detects_size_change_at_same_mtime(tmp_path):
    """Bytes changed but mtime preserved (e.g. rsync -t). Must reload."""
    import os
    from workflows.code_review.config_snapshot import AtomicRef
    from workflows.code_review.config_watcher import ConfigWatcher

    p, initial = _seed_snapshot(tmp_path)
    ref = AtomicRef(initial)
    events: list[tuple[str, dict]] = []
    w = ConfigWatcher(p, ref, lambda t, d: events.append((t, d)))

    # Force first poll to record current key
    w.poll()
    events.clear()

    # Rewrite with longer content but force-restore the original mtime
    new_yaml = p.read_text() + "\n# trailing comment to bump size\n"
    original_mtime = p.stat().st_mtime
    p.write_text(new_yaml)
    os.utime(p, (original_mtime, original_mtime))

    # mtime is unchanged but size grew. Watcher must still re-parse.
    w.poll()

    reloads = [t for t, _ in events if t == "daedalus.config_reloaded"]
    assert len(reloads) == 1, f"Expected size-change to trigger reload, got events={events}"
    assert ref.get() is not initial  # snapshot replaced
