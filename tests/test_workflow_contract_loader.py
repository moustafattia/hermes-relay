from pathlib import Path

import pytest
import yaml

from workflows.contract import (
    WorkflowContractError,
    find_workflow_contract_path,
    load_workflow_contract,
    load_workflow_contract_file,
)


def _native_config() -> dict:
    return {
        "workflow": "code-review",
        "schema-version": 1,
        "instance": {"name": "attmous-daedalus-code-review", "engine-owner": "hermes"},
        "repository": {
            "local-path": "/tmp/repo",
            "github-slug": "attmous/daedalus",
            "active-lane-label": "active-lane",
        },
        "runtimes": {"r1": {"kind": "claude-cli", "max-turns-per-invocation": 8, "timeout-seconds": 60}},
        "agents": {
            "coder": {"default": {"name": "coder", "model": "gpt-5", "runtime": "r1"}},
            "internal-reviewer": {"name": "reviewer", "model": "claude", "runtime": "r1"},
            "external-reviewer": {"enabled": False, "name": "external"},
        },
        "gates": {"internal-review": {}, "external-review": {}, "merge": {}},
        "triggers": {"lane-selector": {"type": "github-label", "label": "active-lane"}},
        "storage": {
            "ledger": "memory/workflow-status.json",
            "health": "memory/workflow-health.json",
            "audit-log": "memory/workflow-audit.jsonl",
        },
    }


def _workflow_markdown(config: dict, *, prompt_role: str = "coder", body: str = "You are the workflow prompt.") -> str:
    front_matter = {
        "tracker": {"kind": "github-issues"},
        "daedalus": {
            "prompt-role": prompt_role,
            "workflow-config": config,
        },
    }
    return "---\n" + yaml.safe_dump(front_matter, sort_keys=False) + "---\n\n" + body + "\n"


def test_load_workflow_contract_reads_yaml_mapping(tmp_path):
    root = tmp_path / "wf"
    (root / "config").mkdir(parents=True)
    path = root / "config" / "workflow.yaml"
    path.write_text(yaml.safe_dump(_native_config()), encoding="utf-8")

    contract = load_workflow_contract(root)

    assert contract.source_path == path
    assert contract.config["workflow"] == "code-review"
    assert contract.prompt_template == ""


def test_load_workflow_contract_reads_markdown_and_injects_prompt(tmp_path):
    root = tmp_path / "wf"
    root.mkdir()
    path = root / "WORKFLOW.md"
    path.write_text(
        _workflow_markdown(
            _native_config(),
            prompt_role="internal-reviewer",
            body="Review the lane strictly.",
        ),
        encoding="utf-8",
    )

    contract = load_workflow_contract(root)

    assert contract.source_path == path
    assert contract.config["workflow"] == "code-review"
    assert contract.config["prompts"]["internal-reviewer"] == "Review the lane strictly."
    assert contract.prompt_template == "Review the lane strictly."


def test_load_workflow_contract_markdown_requires_daedalus_workflow_config(tmp_path):
    path = tmp_path / "WORKFLOW.md"
    path.write_text(
        "---\ntracker:\n  kind: linear\n---\n\nPrompt body.\n",
        encoding="utf-8",
    )

    with pytest.raises(WorkflowContractError, match="daedalus.workflow-config"):
        load_workflow_contract_file(path)


def test_find_workflow_contract_path_prefers_yaml_when_both_exist(tmp_path):
    root = tmp_path / "wf"
    (root / "config").mkdir(parents=True)
    yaml_path = root / "config" / "workflow.yaml"
    yaml_path.write_text(yaml.safe_dump(_native_config()), encoding="utf-8")
    (root / "WORKFLOW.md").write_text(_workflow_markdown(_native_config()), encoding="utf-8")

    assert find_workflow_contract_path(root) == yaml_path
