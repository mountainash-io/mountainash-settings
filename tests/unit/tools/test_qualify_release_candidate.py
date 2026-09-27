from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _qualifier_module():
    name = "qualify_release_candidate_under_test"
    path = Path(__file__).resolve().parents[3] / "tools" / "qualify_release_candidate.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_validate_python_identities_requires_312_and_313_once_each():
    qualifier = _qualifier_module()

    qualifier.validate_python_identities(
        [
            {"version_info": [3, 12], "executable": "/python312"},
            {"version_info": [3, 13], "executable": "/python313"},
        ]
    )

    with pytest.raises(ValueError, match="Python 3.12 and 3.13"):
        qualifier.validate_python_identities(
            [
                {"version_info": [3, 12], "executable": "/python312-a"},
                {"version_info": [3, 12], "executable": "/python312-b"},
            ]
        )


def test_validate_python_identities_rejects_additional_versions():
    qualifier = _qualifier_module()

    with pytest.raises(ValueError, match="Python 3.12 and 3.13"):
        qualifier.validate_python_identities(
            [
                {"version_info": [3, 12], "executable": "/python312"},
                {"version_info": [3, 13], "executable": "/python313"},
                {"version_info": [3, 14], "executable": "/python314"},
            ]
        )
