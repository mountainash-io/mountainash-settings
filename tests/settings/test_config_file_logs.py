"""Real fsspec DEBUG records must not carry configuration-location credentials."""
from __future__ import annotations

from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import subprocess
import sys
import textwrap
import traceback
from threading import Thread
from urllib.parse import urlsplit

import pytest
from upath import UPath

from mountainash_settings import MountainAshBaseSettings, get_settings

EMITTERS = ("fsspec", "fsspec.http", "fsspec.caching", "fsspec.asyn", "fsspec.reference")
USER, PASSWORD, QUERY, FRAGMENT = "LOG_USER", "LOG_PASSWORD", "LOG_QUERY", "LOG_FRAGMENT"
SENTINELS = (USER, PASSWORD, QUERY, FRAGMENT)
LARGE_ITEMS = 6000


class LogSettings(MountainAshBaseSettings):
    VALUE: int = 0


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def record_surfaces(record: logging.LogRecord) -> str:
    parts = [str(record.msg), repr(record.args), record.getMessage(), str(record.exc_text),
             str(record.stack_info), repr(record.__dict__.get("message"))]
    if record.exc_info:
        parts.append("".join(traceback.format_exception(*record.exc_info)))
        parts.append(repr(record.exc_info[1]))
    return "\n".join(parts)


@pytest.fixture
def captured_records() -> Iterator[list[logging.LogRecord]]:
    handler = _Capture()
    saved = []
    for name in EMITTERS:
        logger = logging.getLogger(name)
        saved.append((logger, logger.level))
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)
    try:
        yield handler.records
    finally:
        for logger, level in saved:
            logger.removeHandler(handler)
            logger.setLevel(level)


@pytest.fixture
def range_server() -> Iterator[tuple[str, list[str]]]:
    """Loopback server answering HEAD, GET and byte ranges."""
    requests: list[str] = []
    large = ("".join(f"KEY_{i}: {i}\n" for i in range(LARGE_ITEMS)) + "VALUE: 77\n").encode()

    class Handler(BaseHTTPRequestHandler):
        def respond(self, include_body: bool) -> None:
            requests.append(self.path)
            name = Path(urlsplit(self.path).path).name
            if "missing" in name:
                self.send_error(404)
                return
            if "headfail" in name and not include_body:
                self.send_error(500)
                return
            if "denied" in name:
                self.send_error(403)
                return
            body = large if name.startswith("large") else b"VALUE: 12\n"
            if name == "refs.json":
                body = json.dumps({"version": 1, "refs": {"config.json": '{"VALUE": 42}'}}).encode()
            start, end, status = 0, len(body) - 1, 200
            spec = self.headers.get("Range")
            if spec and spec.startswith("bytes="):
                first, _, last = spec[6:].partition("-")
                start = int(first)
                end = min(int(last), len(body) - 1) if last else len(body) - 1
                status = 206
            chunk = body[start:end + 1]
            self.send_response(status)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(len(chunk)))
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(body)}")
            self.end_headers()
            if include_body:
                self.wfile.write(chunk)

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


def credential_url(origin: str, name: str) -> str:
    authority = origin.replace("http://", f"http://{USER}:{PASSWORD}@")
    return f"{authority}/{name}?token={QUERY}#{FRAGMENT}"


def assert_clean_and_emitted(records: list[logging.LogRecord]) -> None:
    assert any(record.name in EMITTERS and record.levelno == logging.DEBUG for record in records)
    for record in records:
        if record.name not in EMITTERS:
            continue
        text = record_surfaces(record)
        for sentinel in SENTINELS:
            assert sentinel not in text, (record.name, record.funcName, sentinel)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("cache_type", ["bytes", "background"])
def test_successful_http_load_logs_are_clean(
    range_server, isolated_settings_manager, captured_records, cached, cache_type,
):
    origin, requests = range_server
    path = UPath(credential_url(origin, "large.yaml"), cache_type=cache_type, block_size=4096)
    if cached:
        value = get_settings(settings_class=LogSettings, config_files=path).VALUE
    else:
        value = LogSettings(config_files=path).VALUE
    assert value == 77
    assert any(f"token={QUERY}" in request for request in requests)
    assert_clean_and_emitted(captured_records)


@pytest.mark.parametrize("cached", [False, True])
def test_reference_document_url_logs_are_clean(
    range_server, isolated_settings_manager, captured_records, cached,
):
    """A reference-document URL in storage options must not leak through INFO records."""
    origin, requests = range_server
    path = UPath("reference://config.json", fo=credential_url(origin, "refs.json"))
    settings = (get_settings(settings_class=LogSettings, config_files=path) if cached
                else LogSettings(config_files=path))
    assert settings.VALUE == 42
    assert any(f"token={QUERY}" in request for request in requests)
    reference_records = [r for r in captured_records if r.name == "fsspec.reference"]
    assert any(r.levelno == logging.INFO for r in reference_records)
    for record in reference_records:
        for sentinel in SENTINELS:
            assert sentinel not in record_surfaces(record)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("name", ["missing.yaml", "denied.yaml"])
def test_failing_http_load_logs_are_clean(
    range_server, isolated_settings_manager, captured_records, cached, name,
):
    origin, requests = range_server
    url = credential_url(origin, name)
    expected = FileNotFoundError if name.startswith("missing") else OSError
    with pytest.raises(expected):
        if cached:
            get_settings(settings_class=LogSettings, config_files=url)
        else:
            LogSettings(config_files=url)
    assert any(f"token={QUERY}" in request for request in requests)
    assert_clean_and_emitted(captured_records)


def test_filter_reduces_unrelated_fsspec_record_in_fresh_process():
    program = textwrap.dedent(f"""
        import logging
        from mountainash_settings import MountainAshBaseSettings  # noqa: F401 -- loads the config machinery

        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        logging.getLogger().addHandler(Capture(logging.DEBUG))
        for name in {EMITTERS!r}:
            logging.getLogger(name).setLevel(logging.DEBUG)
            try:
                raise ValueError("{PASSWORD}")
            except ValueError:
                logging.getLogger(name).debug("open https://{USER}:{PASSWORD}@h/x?{QUERY}", "{FRAGMENT}", exc_info=True, stack_info=True)
        assert sorted(record.name for record in records) == sorted({EMITTERS!r}), [r.name for r in records]
        for record in records:
            text = " ".join([str(record.msg), repr(record.args), record.getMessage(),
                             str(record.exc_info), str(record.exc_text), str(record.stack_info)])
            assert not any(s in text for s in {SENTINELS!r}), text
            assert record.levelno == logging.DEBUG
        print("OK")
    """)
    result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"


@pytest.mark.parametrize("cached", [False, True])
def test_failed_http_metadata_head_exception_record_is_clean(
    range_server, isolated_settings_manager, captured_records, cached,
):
    """HEAD fails, GET succeeds: fsspec's `_info` logs `logger.debug("", exc_info=exc)`."""
    origin, requests = range_server
    url = credential_url(origin, "headfail.yaml")
    value = (get_settings(settings_class=LogSettings, config_files=url) if cached
             else LogSettings(config_files=url)).VALUE
    assert value == 12
    assert any(f"token={QUERY}" in request for request in requests)
    info_records = [r for r in captured_records if r.name == "fsspec.http" and r.funcName == "_info"]
    assert info_records, "fsspec did not log the failed HEAD metadata fallback"
    assert_clean_and_emitted(captured_records)
