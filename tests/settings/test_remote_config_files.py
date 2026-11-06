"""Real configuration-source boundaries: remote access, ownership and snapshots."""
from __future__ import annotations

from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit
from uuid import uuid4

from aiohttp import ClientTimeout
from pydantic import Field
import pytest
from upath import UPath

from mountainash_settings import MountainAshBaseSettings, SettingsParameters, get_settings
from mountainash_settings.settings_parameters.filehandler import FileTypeRegistry


class RemoteSettings(MountainAshBaseSettings):
    VALUE: int = 0
    NESTED: dict[str, int] = Field(default_factory=dict)


@pytest.mark.parametrize("suffix,initial,changed", [
    ("yaml", "VALUE: 5\nNESTED: {a: 1}\n", "VALUE: 9\n"),
    ("toml", "VALUE = 5\n[NESTED]\na = 1\n", "VALUE = 9\n"),
    ("json", '{"VALUE": 5, "NESTED": {"a": 1}}', '{"VALUE": 9}'),
])
def test_remote_snapshot_and_recipe(memory_config_root, isolated_settings_manager,
                                    suffix, initial, changed):
    path = memory_config_root / f"config.{suffix}"
    path.write_text(initial)
    assert RemoteSettings(config_files=path).VALUE == 5
    assert RemoteSettings(config_files=str(path)).VALUE == 5
    first = get_settings(settings_class=RemoteSettings, config_files=str(path), VALUE=42)
    assert first.VALUE == 42
    first.NESTED["a"] = 99
    captured = RemoteSettings.get_settings(config_files=path)
    assert (captured.VALUE, captured.NESTED) == (5, {"a": 1})
    path.write_text(changed)
    assert RemoteSettings(config_files=str(path)).VALUE == 9
    path.unlink()
    recipe = captured.extract_settings_parameters()
    assert recipe.get_settings().VALUE == 5
    assert get_settings(settings_parameters=recipe, reinitialise=True).VALUE == 5


def test_remote_source_order_survives_extraction(memory_config_root, isolated_settings_manager):
    json_path = memory_config_root / "first.json"
    yaml_path = memory_config_root / "second.yaml"
    json_path.write_text('{"VALUE": 3, "NESTED": {"json": 1}}')
    yaml_path.write_text("VALUE: 7\nNESTED: {yaml: 2}\n")
    recipe = SettingsParameters.create(settings_class=RemoteSettings, config_files=[json_path, yaml_path])
    settings = recipe.get_settings()
    assert (settings.VALUE, settings.NESTED) == (7, {"json": 1, "yaml": 2})
    settings.update_settings_from_dict({"VALUE": 11})
    extracted = settings.extract_settings_parameters()
    assert tuple(map(str, extracted.config_files)) == (str(json_path), str(yaml_path))
    json_path.unlink()
    yaml_path.unlink()
    assert extracted.get_settings().VALUE == 11
    assert recipe.get_settings().VALUE == 7


@pytest.mark.parametrize("suffix", [".yaml", ".yml", ".CUSTOM"])
def test_remote_registered_filename_loads(memory_config_root, monkeypatch, suffix):
    monkeypatch.setitem(FileTypeRegistry._registry, "custom", "yaml")
    path = memory_config_root / ("selected" + suffix)
    path.write_text("VALUE: 17\n")
    assert RemoteSettings(config_files=str(path)).VALUE == 17


@pytest.mark.parametrize("name", ["literal?part.yaml", "literal#part.yaml"])
def test_object_key_punctuation_is_not_a_query(memory_config_root, name):
    path = memory_config_root / name
    path.write_text("VALUE: 23\n")
    settings = RemoteSettings(config_files=path)
    assert settings.VALUE == 23
    assert str(settings.SETTINGS_SOURCE_YAML_FILES[0]) == str(path)


def test_remote_empty_missing_and_unknown_files(memory_config_root, isolated_settings_manager):
    empty = memory_config_root / "empty.yaml"
    empty.write_text("")
    assert RemoteSettings(config_files=empty).VALUE == 0
    assert get_settings(settings_class=RemoteSettings, config_files=empty).VALUE == 0
    unknown = memory_config_root / "unknown.unsupported"
    unknown.write_text("VALUE: 10")
    for path, error in ((memory_config_root / "missing.yaml", FileNotFoundError), (unknown, ValueError)):
        with pytest.raises(error):
            RemoteSettings(config_files=path)
        with pytest.raises(error):
            get_settings(settings_class=RemoteSettings, config_files=path)


def test_failed_remote_parse_does_not_publish_defaults(memory_config_root, isolated_settings_manager):
    path = memory_config_root / "retry.json"
    path.write_text('{"VALUE":')
    with pytest.raises(json.JSONDecodeError):
        get_settings(settings_class=RemoteSettings, config_files=path)
    path.write_text('{"VALUE": 31}')
    assert get_settings(settings_class=RemoteSettings, config_files=path).VALUE == 31


def test_selected_local_link_keeps_input_semantics(tmp_path):
    source = tmp_path / "source.yaml"
    source.write_text("VALUE: 29\n")
    link = tmp_path / "selected.yaml"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Configured input symlinks unavailable: {type(exc).__name__}")
    assert RemoteSettings(config_files=str(link)).VALUE == 29
    assert RemoteSettings(config_files=UPath(link)).VALUE == 29


@pytest.fixture
def http_config_server() -> Iterator[tuple[str, list[tuple[str, str | None]]]]:
    requests: list[tuple[str, str | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def respond(self, include_body: bool) -> None:
            requests.append((self.path, self.headers.get("X-Value")))
            location = urlsplit(self.path).path
            if "missing" in location:
                self.send_error(404)
                return
            if "denied" in location:
                self.send_error(403)
                return
            value = int(self.headers.get("X-Value", "12"))
            suffix = Path(location).suffix
            body = {
                ".yaml": f"VALUE: {value}\n",
                ".toml": f"VALUE = {value}\n",
                ".json": json.dumps({"VALUE": value}),
            }[suffix].encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if include_body:
                self.wfile.write(body)

        def do_HEAD(self) -> None:
            self.respond(False)

        def do_GET(self) -> None:
            self.respond(True)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


@pytest.mark.parametrize("suffix", ["yaml", "toml", "json"])
def test_http_options_snapshot_and_diagnostics(http_config_server, isolated_settings_manager, suffix):
    origin, requests = http_config_server
    url = f"{origin}/config.{suffix}?token=query-private-canary#fragment-private-canary"
    timeout = ClientTimeout(total=5)
    headers = {"X-Value": "51", "X-Case": uuid4().hex, "X-Secret": "option-private-canary"}
    path = UPath(url, headers=headers, client_kwargs={"timeout": timeout})
    assert RemoteSettings(config_files=path).VALUE == 51
    captured = get_settings(settings_class=RemoteSettings, config_files=path)
    assert captured.VALUE == 51
    assert any("token=query-private-canary" in request[0] for request in requests)

    before = len(requests)
    extracted = captured.extract_settings_parameters()
    assert extracted.config_files[0].storage_options["client_kwargs"]["timeout"] is timeout
    assert extracted.get_settings().VALUE == 51
    assert get_settings(settings_parameters=extracted, VALUE=99).VALUE == 99
    assert len(requests) == before
    for marker in ("query-private-canary", "fragment-private-canary", "option-private-canary"):
        assert marker not in repr(captured)
        assert marker not in repr(extracted)
        assert marker not in json.dumps(captured.model_dump(), default=str)
    assert str(extracted.config_files[0]) == str(path)

    other = UPath(url, headers=dict(headers), client_kwargs={"timeout": ClientTimeout(total=5)})
    before = len(requests)
    assert get_settings(settings_class=RemoteSettings, config_files=other).VALUE == 51
    assert len(requests) > before
    changed = UPath(url, headers={**headers, "X-Value": "52"}, client_kwargs={"timeout": timeout})
    assert get_settings(settings_class=RemoteSettings, config_files=changed).VALUE == 52

    # Mutate public containers only after checking fresh-context selection.
    path.storage_options["headers"]["X-Value"] = "61"
    assert extracted.config_files[0].storage_options["headers"]["X-Value"] == "51"
    extracted.config_files[0].storage_options["headers"]["X-Value"] = "71"
    before = len(requests)
    fresh = captured.extract_settings_parameters()
    assert fresh.config_files[0].storage_options["headers"]["X-Value"] == "51"
    assert fresh.get_settings().VALUE == 51
    assert len(requests) == before

    plain = f"{origin}/plain.{suffix}?selection=public"
    assert RemoteSettings(config_files=plain).VALUE == 12
    assert get_settings(settings_class=RemoteSettings, config_files=UPath(plain)).VALUE == 12


def test_http_missing_error_uses_safe_source_label(http_config_server):
    origin, _ = http_config_server
    url = origin.replace("http://", "http://user-private-canary:password-private-canary@")
    url += "/missing.yaml?token=query-private-canary"
    with pytest.raises(FileNotFoundError) as error:
        RemoteSettings(config_files=url)
    for marker in ("user-private-canary", "password-private-canary", "query-private-canary"):
        assert marker not in str(error.value)


def test_http_access_failure_does_not_yield_defaults(http_config_server, isolated_settings_manager):
    origin, _ = http_config_server
    with pytest.raises(OSError):
        get_settings(settings_class=RemoteSettings, config_files=f"{origin}/denied.yaml")
