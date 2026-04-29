"""Repo-root code-review workflow wrapper for official Hermes plugin installs."""

import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[2]
_PLUGIN_ROOT_STR = str(_PLUGIN_ROOT)
if _PLUGIN_ROOT_STR not in sys.path:
    sys.path.insert(0, _PLUGIN_ROOT_STR)

_REAL_WORKFLOW_DIR = _PLUGIN_ROOT / "daedalus" / "workflows" / "code_review"
_real_dir_str = str(_REAL_WORKFLOW_DIR)
if _real_dir_str not in __path__:
    __path__.append(_real_dir_str)

from daedalus.workflows.code_review import *  # noqa: F401,F403
