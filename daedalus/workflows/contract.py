"""Workflow contract loading for Daedalus.

Daedalus currently supports two workflow-contract entrypoints:

- ``config/workflow.yaml``: the native Daedalus instance config
- ``WORKFLOW.md``: a Symphony-style Markdown contract with YAML front matter

The Markdown form is a compatibility/front-door layer. It does not yet map the
entire Symphony front matter directly into Daedalus runtime settings; instead,
it expects a ``daedalus.workflow-config`` mapping containing the native
Daedalus config and optionally injects the Markdown body into
``prompts.<role>``.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_WORKFLOW_CONFIG_FILENAME = "config/workflow.yaml"
DEFAULT_WORKFLOW_MARKDOWN_FILENAME = "WORKFLOW.md"


class WorkflowContractError(RuntimeError):
    """Raised when the workflow contract file cannot be loaded or projected."""


@dataclass(frozen=True)
class WorkflowContract:
    """Loaded workflow contract plus prompt body metadata."""

    source_path: Path
    config: dict[str, Any]
    prompt_template: str
    front_matter: dict[str, Any]


def workflow_yaml_path(workflow_root: Path) -> Path:
    return workflow_root.resolve() / DEFAULT_WORKFLOW_CONFIG_FILENAME


def workflow_markdown_path(workflow_root: Path) -> Path:
    return workflow_root.resolve() / DEFAULT_WORKFLOW_MARKDOWN_FILENAME


def find_workflow_contract_path(workflow_root: Path) -> Path | None:
    """Return the preferred contract path for a workflow root, if any.

    ``config/workflow.yaml`` remains the first choice so existing instances do
    not change behavior if both files are present.
    """
    yaml_path = workflow_yaml_path(workflow_root)
    if yaml_path.exists():
        return yaml_path
    markdown_path = workflow_markdown_path(workflow_root)
    if markdown_path.exists():
        return markdown_path
    return None


def load_workflow_contract(workflow_root: Path) -> WorkflowContract:
    path = find_workflow_contract_path(workflow_root)
    if path is None:
        raise FileNotFoundError(
            f"workflow contract not found under {Path(workflow_root).resolve()} "
            f"(looked for {DEFAULT_WORKFLOW_CONFIG_FILENAME} and {DEFAULT_WORKFLOW_MARKDOWN_FILENAME})"
        )
    return load_workflow_contract_file(path)


def load_workflow_contract_file(path: Path) -> WorkflowContract:
    resolved = Path(path).expanduser().resolve()
    suffix = resolved.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return _load_yaml_contract(resolved)
    if suffix == ".md":
        return _load_markdown_contract(resolved)
    raise WorkflowContractError(
        f"unsupported workflow contract format for {resolved}; "
        "expected YAML (.yaml/.yml) or Markdown (.md)"
    )


def _load_yaml_contract(path: Path) -> WorkflowContract:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise WorkflowContractError(f"YAML parse error in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise WorkflowContractError(
            f"{path} must contain a YAML mapping at the top level"
        )
    return WorkflowContract(
        source_path=path,
        config=payload,
        prompt_template="",
        front_matter={},
    )


def _load_markdown_contract(path: Path) -> WorkflowContract:
    text = path.read_text(encoding="utf-8")
    front_matter, prompt_template = _parse_markdown_contract(path, text)
    config = _project_markdown_front_matter(
        path=path,
        front_matter=front_matter,
        prompt_template=prompt_template,
    )
    return WorkflowContract(
        source_path=path,
        config=config,
        prompt_template=prompt_template,
        front_matter=front_matter,
    )


def _parse_markdown_contract(path: Path, text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text.strip()

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text.strip()

    closing_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        raise WorkflowContractError(
            f"{path} starts with YAML front matter but is missing the closing --- delimiter"
        )

    front_matter_text = "\n".join(lines[1:closing_index])
    prompt_body = "\n".join(lines[closing_index + 1 :]).strip()
    try:
        parsed = yaml.safe_load(front_matter_text) if front_matter_text.strip() else {}
    except yaml.YAMLError as exc:
        raise WorkflowContractError(f"YAML front-matter parse error in {path}: {exc}") from exc
    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise WorkflowContractError(
            f"{path} front matter must decode to a YAML mapping at the top level"
        )
    return parsed, prompt_body


def _project_markdown_front_matter(
    *,
    path: Path,
    front_matter: dict[str, Any],
    prompt_template: str,
) -> dict[str, Any]:
    extension = front_matter.get("daedalus") or {}
    if not isinstance(extension, dict):
        raise WorkflowContractError(f"{path} must define daedalus: as a mapping")

    raw_config = extension.get("workflow-config")
    if raw_config is None:
        raise WorkflowContractError(
            f"{path} must define daedalus.workflow-config to map WORKFLOW.md "
            "into the current Daedalus workflow schema"
        )
    if not isinstance(raw_config, dict):
        raise WorkflowContractError(f"{path} daedalus.workflow-config must be a mapping")

    config = deepcopy(raw_config)
    prompt_role = extension.get("prompt-role", "coder")
    if not isinstance(prompt_role, str) or not prompt_role.strip():
        raise WorkflowContractError(f"{path} daedalus.prompt-role must be a non-empty string")

    if prompt_template:
        prompts = config.get("prompts")
        if prompts is None:
            prompts = {}
            config["prompts"] = prompts
        if not isinstance(prompts, dict):
            raise WorkflowContractError(f"{path} prompts must be a mapping when present")
        prompts[prompt_role.strip()] = prompt_template

    return config
