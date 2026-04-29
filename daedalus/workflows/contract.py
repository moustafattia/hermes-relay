"""Workflow contract loading for Daedalus.

Daedalus supports two workflow-contract entrypoints:

- ``WORKFLOW.md``: the native public contract
- ``config/workflow.yaml``: a legacy load-only input

Both ultimately feed the same internal config object. ``WORKFLOW.md`` uses YAML
front matter for the structured config and its Markdown body as the shared
workflow policy text.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_WORKFLOW_CONFIG_FILENAME = "config/workflow.yaml"
DEFAULT_WORKFLOW_MARKDOWN_FILENAME = "WORKFLOW.md"
WORKFLOW_POLICY_KEY = "workflow-policy"


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

    ``WORKFLOW.md`` is the native public contract and wins when both forms are
    present. ``config/workflow.yaml`` remains loadable for legacy instances.
    """
    markdown_path = workflow_markdown_path(workflow_root)
    if markdown_path.exists():
        return markdown_path
    yaml_path = workflow_yaml_path(workflow_root)
    if yaml_path.exists():
        return yaml_path
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
        prompt_template=str(payload.get(WORKFLOW_POLICY_KEY) or "").strip()
        if isinstance(payload.get(WORKFLOW_POLICY_KEY), str)
        else "",
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
    config = deepcopy(front_matter)
    existing_policy = config.get(WORKFLOW_POLICY_KEY)
    if existing_policy is not None and not isinstance(existing_policy, str):
        raise WorkflowContractError(f"{path} {WORKFLOW_POLICY_KEY} must be a string when present")
    if existing_policy and prompt_template:
        raise WorkflowContractError(
            f"{path} defines both front-matter {WORKFLOW_POLICY_KEY!r} and a Markdown body; "
            "use the body as the workflow policy source"
        )
    if prompt_template:
        config[WORKFLOW_POLICY_KEY] = prompt_template
    return config


def render_workflow_markdown(*, config: dict[str, Any], prompt_template: str | None = None) -> str:
    """Render a native ``WORKFLOW.md`` file from config + policy text."""
    front_matter = deepcopy(config)
    body = prompt_template
    if body is None:
        policy = front_matter.pop(WORKFLOW_POLICY_KEY, "")
        if policy is None:
            body = ""
        elif isinstance(policy, str):
            body = policy
        else:
            raise WorkflowContractError(f"{WORKFLOW_POLICY_KEY} must be a string when rendering WORKFLOW.md")
    else:
        front_matter.pop(WORKFLOW_POLICY_KEY, None)

    if not isinstance(front_matter, dict):
        raise WorkflowContractError("workflow config must be a mapping when rendering WORKFLOW.md")

    front_matter_text = yaml.safe_dump(front_matter, sort_keys=False).strip()
    body_text = str(body or "").strip()
    if body_text:
        return f"---\n{front_matter_text}\n---\n\n{body_text}\n"
    return f"---\n{front_matter_text}\n---\n"
