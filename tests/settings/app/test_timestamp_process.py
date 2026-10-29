"""Fresh-process proof of lazy timestamp ownership, contention and fork safety."""

import os
import subprocess
import sys
from textwrap import dedent

import pytest


PRELUDE = """
from datetime import datetime
from typing import ClassVar, Literal
from mountainash_settings import SettingsParameters
from mountainash_settings.settings.app import _timestamps
from mountainash_settings.settings.app.app_settings import AppSettings
from mountainash_settings.settings_cache.settings_manager import SettingsManager

class ProcessApp(AppSettings):
    RUN_TIMESTAMP_SCOPE: ClassVar[Literal["context", "process"]] = "process"

class OtherProcessApp(ProcessApp):
    pass
"""


def run_script(script):
    result = subprocess.run(
        [sys.executable, "-I", "-c", PRELUDE + dedent(script)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("year, expected_date", [(2031, "20311231"), (2041, "20411231")])
def test_process_timestamp_is_lazy_and_shared_across_classes_and_managers(year, expected_date):
    run_script(f"""
        # Context use must not eagerly populate the process clock slot.
        _timestamps._now = lambda: datetime(2000, 1, 1)
        AppSettings()
        _timestamps._now = lambda: datetime({year}, 12, 31, 23, 59, 59)
        first = ProcessApp()
        _timestamps._now = lambda: datetime(2050, 1, 1, 0, 0, 1)
        second = OtherProcessApp()
        cached = SettingsManager().get_or_create_settings(SettingsParameters.create(settings_class=ProcessApp))
        other_cached = SettingsManager().get_or_create_settings(SettingsParameters.create(settings_class=OtherProcessApp))
        assert (first.RUNDATE, second.RUNDATE, cached.RUNDATE, other_cached.RUNDATE) == ({expected_date!r},) * 4
        assert (first.RUNTIME, second.RUNTIME, cached.RUNTIME, other_cached.RUNTIME) == ("235959",) * 4
        explicit = OtherProcessApp(RUNDATE="19990101")
        assert (explicit.RUNDATE, explicit.RUNTIME) == ("19990101", "235959")
    """)


def test_competing_first_process_constructions_capture_one_instant():
    run_script("""
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event, Lock

        entered, release, contending = Event(), Event(), Event()
        real_lock = Lock()
        calls = []

        class ObservedLock:
            def __enter__(self):
                if real_lock.locked():
                    contending.set()
                real_lock.acquire()
            def __exit__(self, *args):
                real_lock.release()

        # Observe the real synchronization boundary, without replacing exclusion.
        _timestamps._process_lock = ObservedLock()
        def clock():
            calls.append(None)
            entered.set()
            assert release.wait(5)
            return datetime(2031, 12, 31, 23, 59, 59) if len(calls) == 1 else datetime(2032, 1, 1)
        _timestamps._now = clock
        with ThreadPoolExecutor(max_workers=2) as pool:
            try:
                first = pool.submit(ProcessApp)
                assert entered.wait(5)
                second = pool.submit(OtherProcessApp)
                assert contending.wait(5)
                release.set()
                results = [first.result(timeout=5), second.result(timeout=5)]
            finally:
                release.set()
        assert [(r.RUNDATE, r.RUNTIME) for r in results] == [("20311231", "235959")] * 2
    """)


FORK_CHECK = """
import json
import os
import select
import signal

def check_child(manager=None):
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        try:
            _timestamps._now = lambda: datetime(2032, 1, 1, 0, 0, 1)
            child = (ProcessApp() if manager is None else manager.get_or_create_settings(
                SettingsParameters.create(settings_class=ProcessApp), reinitialise=True,
            ))
            os.write(write_fd, json.dumps([child.RUNDATE, child.RUNTIME]).encode())
        except BaseException:
            os._exit(1)
        finally:
            os.close(write_fd)
        os._exit(0)
    os.close(write_fd)
    reaped = False
    try:
        assert select.select([read_fd], [], [], 5)[0], "child timestamp capture hung"
        payload = os.read(read_fd, 4096)
        _, status = os.waitpid(pid, 0)
        reaped = True
        assert os.waitstatus_to_exitcode(status) == 0
        assert json.loads(payload) == ["20320101", "000001"]
    finally:
        os.close(read_fd)
        if not reaped:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
"""


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork")
@pytest.mark.parametrize("inherited_manager", [False, True], ids=["direct", "inherited-manager"])
def test_fork_discards_populated_parent_process_timestamp(inherited_manager):
    run_script(FORK_CHECK + dedent(f"""
        _timestamps._now = lambda: datetime(2031, 12, 31, 23, 59, 59)
        parent_before = ProcessApp()
        manager = SettingsManager()
        params = SettingsParameters.create(settings_class=ProcessApp)
        manager.get_or_create_settings(params)
        check_child(manager if {inherited_manager!r} else None)
        _timestamps._now = lambda: datetime(2033, 1, 1)
        parent_after = ProcessApp()
        parent_cached = manager.get_or_create_settings(params, reinitialise=True)
        assert (parent_before.RUNDATE, parent_before.RUNTIME) == ("20311231", "235959")
        assert (parent_after.RUNDATE, parent_after.RUNTIME) == ("20311231", "235959")
        assert (parent_cached.RUNDATE, parent_cached.RUNTIME) == ("20311231", "235959")
    """))


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork")
def test_fork_replaces_lock_held_during_parent_process_capture():
    run_script(FORK_CHECK + dedent("""
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event

        entered, release = Event(), Event()
        def clock():
            entered.set()
            assert release.wait(10)
            return datetime(2031, 12, 31, 23, 59, 59)
        _timestamps._now = clock
        with ThreadPoolExecutor(max_workers=1) as pool:
            try:
                parent = pool.submit(ProcessApp)
                assert entered.wait(5)
                check_child()
            finally:
                release.set()
            result = parent.result(timeout=5)
        assert (result.RUNDATE, result.RUNTIME) == ("20311231", "235959")
    """))
