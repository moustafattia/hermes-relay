import importlib.util
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1] / "daedalus"


def load_module(module_name: str, relative_path: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _tools():
    return load_module("daedalus_tools_scaffold_workflow_test", "tools.py")


def test_scaffold_workflow_writes_config_and_layout(tmp_path):
    tools = _tools()
    root = tmp_path / "attmous-daedalus-code-review"

    result = tools.scaffold_workflow_root(
        workflow_root=root,
        workflow_name="code-review",
        repo_path=None,
        github_slug="attmous/daedalus",
        active_lane_label="ready-for-daedalus",
        engine_owner="hermes",
        force=False,
    )

    config_path = root / "config" / "workflow.yaml"
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    assert result["config_path"] == str(config_path)
    assert cfg["instance"]["name"] == "attmous-daedalus-code-review"
    assert cfg["instance"]["engine-owner"] == "hermes"
    assert cfg["repository"]["github-slug"] == "attmous/daedalus"
    assert cfg["repository"]["active-lane-label"] == "ready-for-daedalus"
    assert cfg["triggers"]["lane-selector"]["label"] == "ready-for-daedalus"
    assert cfg["repository"]["local-path"] == str(root / "workspace" / "repo")
    assert (root / "memory").is_dir()
    assert (root / "state" / "sessions").is_dir()
    assert (root / "runtime" / "state" / "daedalus").is_dir()
    assert (root / "runtime" / "memory").is_dir()
    assert (root / "runtime" / "logs").is_dir()


def test_scaffold_workflow_refuses_to_overwrite_without_force(tmp_path):
    tools = _tools()
    root = tmp_path / "attmous-daedalus-code-review"
    config_path = root / "config" / "workflow.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("workflow: code-review\n", encoding="utf-8")

    try:
        tools.scaffold_workflow_root(
            workflow_root=root,
            workflow_name="code-review",
            repo_path=None,
            github_slug="attmous/daedalus",
            active_lane_label="active-lane",
            engine_owner="hermes",
            force=False,
        )
    except tools.DaedalusCommandError as exc:
        assert "refusing to overwrite existing config" in str(exc)
        return
    raise AssertionError("expected DaedalusCommandError when overwriting without --force")


def test_scaffold_workflow_force_replaces_existing_config(tmp_path):
    tools = _tools()
    root = tmp_path / "attmous-daedalus-code-review"
    config_path = root / "config" / "workflow.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("workflow: old\n", encoding="utf-8")

    tools.scaffold_workflow_root(
        workflow_root=root,
        workflow_name="code-review",
        repo_path=root / "workspace" / "checkout",
        github_slug="attmous/daedalus",
        active_lane_label="active-lane",
        engine_owner="openclaw",
        force=True,
    )

    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert cfg["workflow"] == "code-review"
    assert cfg["instance"]["name"] == "attmous-daedalus-code-review"
    assert cfg["instance"]["engine-owner"] == "openclaw"
    assert cfg["repository"]["local-path"] == str(root / "workspace" / "checkout")


def test_scaffold_workflow_requires_owner_repo_workflow_root_name(tmp_path):
    tools = _tools()
    root = tmp_path / "daedalus"

    with pytest.raises(tools.DaedalusCommandError) as exc:
        tools.scaffold_workflow_root(
            workflow_root=root,
            workflow_name="code-review",
            repo_path=None,
            github_slug="attmous/daedalus",
            active_lane_label="active-lane",
            engine_owner="hermes",
            force=False,
        )

    assert "<owner>-<repo>-<workflow-type>" in str(exc.value)
