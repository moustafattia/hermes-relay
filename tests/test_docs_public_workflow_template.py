from pathlib import Path

import jsonschema
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = REPO_ROOT / "docs" / "examples" / "code-review.workflow.yaml"
PAYLOAD_TEMPLATE_PATH = (
    REPO_ROOT / "daedalus" / "workflows" / "code_review" / "workflow.template.yaml"
)
SCHEMA_PATH = REPO_ROOT / "daedalus" / "workflows" / "code_review" / "schema.yaml"


def test_public_workflow_template_validates_against_schema():
    template = yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))
    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(template, schema)


def test_public_workflow_template_uses_generic_placeholders():
    text = TEMPLATE_PATH.read_text(encoding="utf-8").lower()
    assert "yoyopod" not in text
    assert "your-org-your-repo-code-review" in text


def test_payload_workflow_template_matches_docs_copy():
    assert PAYLOAD_TEMPLATE_PATH.read_text(encoding="utf-8") == TEMPLATE_PATH.read_text(encoding="utf-8").replace(
        "# Public docs copy.\n# Canonical installable source:\n#   daedalus/workflows/code_review/workflow.template.yaml\n\n",
        "",
        1,
    )
