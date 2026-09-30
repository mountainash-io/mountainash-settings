from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import Field

from mountainash_settings import MountainAshBaseSettings, SettingsParameters


class _MergeSettings(MountainAshBaseSettings):
    targets: dict[str, Any] = Field(default_factory=dict)
    values: list[str] = Field(default_factory=list)
    payload: Any = None


def _write_pair(tmp_path: Path, suffix: str) -> tuple[Path, Path]:
    base = tmp_path / f"base.{suffix}"
    override = tmp_path / f"override.{suffix}"
    if suffix == "toml":
        base.write_text(
            'values = ["base"]\n'
            '[targets.docker]\ntransport = "compose"\n'
            '[targets.docker.backends.postgres]\nport = 5432\n'
            '[payload]\nleft = 1\nright = 2\n'
        )
        override.write_text(
            'values = ["override"]\n'
            'payload = "replaced"\n'
            '[targets.mpnas]\ntransport = "ssh-tunnel"\n'
            '[targets.docker.backends.postgres]\n'
            'port = 15432\n'
            'host = "localhost"\n'
        )
    elif suffix == "yaml":
        base.write_text(
            "values: [base]\n"
            "targets:\n"
            "  docker:\n"
            "    transport: compose\n"
            "    backends:\n"
            "      postgres:\n"
            "        port: 5432\n"
            "payload:\n"
            "  left: 1\n"
            "  right: 2\n"
        )
        override.write_text(
            "values: [override]\n"
            "targets:\n"
            "  mpnas:\n"
            "    transport: ssh-tunnel\n"
            "  docker:\n"
            "    backends:\n"
            "      postgres:\n"
            "        port: 15432\n"
            "        host: localhost\n"
            "payload: replaced\n"
        )
    else:
        base.write_text(json.dumps({
            "values": ["base"],
            "targets": {
                "docker": {
                    "transport": "compose",
                    "backends": {"postgres": {"port": 5432}},
                }
            },
            "payload": {"left": 1, "right": 2},
        }))
        override.write_text(json.dumps({
            "values": ["override"],
            "targets": {
                "mpnas": {"transport": "ssh-tunnel"},
                "docker": {
                    "backends": {
                        "postgres": {"port": 15432, "host": "localhost"},
                    },
                },
            },
            "payload": "replaced",
        }))
    return base, override


@pytest.mark.parametrize("suffix", ["toml", "yaml", "json"])
def test_structured_files_deep_merge_mappings_and_replace_leaves(tmp_path, suffix):
    base, override = _write_pair(tmp_path, suffix)

    settings = _MergeSettings(config_files=[base, override])

    assert settings.targets == {
        "docker": {
            "transport": "compose",
            "backends": {
                "postgres": {"port": 15432, "host": "localhost"},
            },
        },
        "mpnas": {"transport": "ssh-tunnel"},
    }
    assert settings.values == ["override"]
    assert settings.payload == "replaced"


@pytest.mark.parametrize("suffix", ["toml", "yaml", "json"])
def test_structured_file_order_controls_leaf_precedence(tmp_path, suffix):
    base, override = _write_pair(tmp_path, suffix)

    settings = _MergeSettings(config_files=[override, base])

    assert settings.targets["docker"]["backends"]["postgres"] == {
        "port": 5432,
        "host": "localhost",
    }
    assert settings.values == ["base"]
    assert settings.payload == {"left": 1, "right": 2}


@pytest.mark.parametrize("suffix", ["toml", "yaml", "json"])
def test_settings_parameters_preserves_base_then_local_order(tmp_path, suffix):
    base, override = _write_pair(tmp_path, suffix)
    params = SettingsParameters.create(
        settings_class=_MergeSettings,
        config_files=[base],
    )

    settings = _MergeSettings(
        settings_parameters=params,
        config_files=[override],
    )

    postgres = settings.targets["docker"]["backends"]["postgres"]
    assert postgres == {"port": 15432, "host": "localhost"}
    assert "mpnas" in settings.targets


@pytest.mark.parametrize("suffix", ["toml", "yaml", "json"])
def test_settings_parameters_respects_reversed_caller_order(tmp_path, suffix):
    base, override = _write_pair(tmp_path, suffix)
    params = SettingsParameters.create(
        settings_class=_MergeSettings,
        config_files=[override],
    )

    settings = _MergeSettings(
        settings_parameters=params,
        config_files=[base],
    )

    postgres = settings.targets["docker"]["backends"]["postgres"]
    assert postgres == {"port": 5432, "host": "localhost"}
