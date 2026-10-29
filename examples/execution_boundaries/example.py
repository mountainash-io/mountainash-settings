"""A stable file, a warmed parent cache, and different execution boundaries."""

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextvars import ContextVar
import multiprocessing as mp
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Barrier, get_ident

from pydantic import Field
from pydantic_settings import BaseSettings, JsonConfigSettingsSource, SettingsConfigDict

from mountainash_settings import MountainAshBaseSettings, SettingsParameters
from mountainash_settings.settings_cache.settings_functions import get_settings_manager

CONFIG = Path(__file__).with_name("settings.json").resolve()
SOURCE = ContextVar("source", default=CONFIG)
READS = 0
PARENT_SETTINGS = None


def count_reads(event: str, args: tuple) -> None:
    """Observe actual source opens, including ones made inside the library."""
    global READS
    if event == "open" and isinstance(args[0], (str, bytes)):
        if os.path.abspath(os.fsdecode(args[0])) == str(CONFIG) and args[1] in ("r", "rb"):
            READS += 1


sys.addaudithook(count_reads)


class PlainSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REPORT_")
    DATABASE: str
    TAGS: list[str] = Field(default_factory=list)

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                   dotenv_settings, file_secret_settings):
        return init_settings, env_settings, JsonConfigSettingsSource(settings_cls, json_file=SOURCE.get())


class AppSettings(MountainAshBaseSettings):
    DATABASE: str
    TAGS: list[str] = Field(default_factory=list)


def plain(path=CONFIG):
    token = SOURCE.set(path)
    try:
        return PlainSettings()
    finally:
        SOURCE.reset(token)


def recipe(path=CONFIG):
    return SettingsParameters(settings_class=AppSettings, config_files=[str(path)], env_prefix="REPORT_")


def worker(mode, payload, environment=None, cwd=None):
    """Return observations; expected failures are asserted by the caller."""
    start = READS
    if environment:
        os.environ["REPORT_DATABASE"] = environment
    if cwd:
        os.chdir(cwd)
    result = {"pid": os.getpid(), "thread": get_ident()}
    if mode in ("cache_only", "recipe"):
        result["cached"] = get_settings_manager().is_initialised(payload)
    try:
        if mode == "passed":
            settings = payload
        elif mode == "parent_global":
            settings = PARENT_SETTINGS
        elif mode == "factory":
            settings = plain(payload)
        elif mode == "cache_only":
            settings = get_settings_manager().get_settings_object(payload)
        else:
            settings = payload.get_settings()
        result["database"] = settings.DATABASE
        result["first_reads"] = READS - start
        if mode == "recipe":
            again = READS
            local = payload.get_settings(DATABASE="task_database")
            assert local.DATABASE == "task_database"
            assert settings.DATABASE == result["database"]
            result["second_reads"] = READS - again
        return result
    except (ValueError, AttributeError, FileNotFoundError) as exc:
        return {**result, "error": type(exc).__name__}


def process(method, mode, payload, **kwargs):
    with ProcessPoolExecutor(1, mp_context=mp.get_context(method)) as pool:
        return pool.submit(worker, mode, payload, **kwargs).result(timeout=15)


def thread_isolation(params):
    for mode in ("shared", "deepcopy", "factory", "recipe"):
        before = READS
        shared = plain() if mode in ("shared", "deepcopy") else None
        barrier = Barrier(2)

        def task(index):
            if mode == "shared":
                settings = shared
            elif mode == "deepcopy":
                settings = shared.model_copy(deep=True)
            elif mode == "factory":
                settings = plain()
            else:
                settings = params.get_settings()
            if index == 0:
                settings.TAGS.append("task-0")
            barrier.wait(timeout=5)
            return list(settings.TAGS)

        with ThreadPoolExecutor(2) as pool:
            values = list(pool.map(task, (0, 1)))
        assert values == [["task-0"], ["task-0"] if mode == "shared" else []]
        expected_reads = {"shared": 1, "deepcopy": 1, "factory": 2, "recipe": 0}[mode]
        assert READS - before == expected_reads
        print(f"Threads {mode}: isolated={mode != 'shared'}, file reads={expected_reads}")


def main():
    global PARENT_SETTINGS
    params = recipe()
    before = READS
    assert params.get_settings().DATABASE == "reports_db"
    assert READS - before == 1
    PARENT_SETTINGS = plain()
    barrier = Barrier(2)

    def thread(mode):
        barrier.wait(timeout=5)
        return worker(mode, params)

    with ThreadPoolExecutor(2) as pool:
        observations = list(pool.map(thread, ("cache_only", "recipe")))
    assert len({item["thread"] for item in observations}) == 2
    assert all(item["cached"] and item["first_reads"] == 0 for item in observations)
    print("Warm parent cache: available to both threads; no file reads")
    thread_isolation(params)

    for method in ("spawn", "fork", "forkserver"):
        if method not in mp.get_all_start_methods():
            print(f"{method}: unavailable on this platform")
            continue
        inherited = method == "fork"
        cached = process(method, "cache_only", params)
        assert cached["cached"] is inherited
        if inherited:
            assert cached["database"] == "reports_db" and cached["first_reads"] == 0
        else:
            assert cached["error"] == "ValueError"
        resolved = process(method, "recipe", params)
        assert resolved["cached"] is inherited
        assert resolved["database"] == "reports_db"
        assert resolved["first_reads"] == (0 if inherited else 1)
        assert resolved["second_reads"] == 0
        passed = process(method, "passed", PARENT_SETTINGS)
        assert passed["database"] == "reports_db" and passed["first_reads"] == 0
        parent = process(method, "parent_global", None)
        if inherited:
            assert parent["database"] == "reports_db"
        else:
            assert parent["error"] == "AttributeError"
        factory = process(method, "factory", CONFIG)
        assert factory["database"] == "reports_db" and factory["first_reads"] == 1
        print(f"{method}: parent cache={inherited}, recipe reads={resolved['first_reads']}/0; explicit object transfer works")

    for mode, payload in (("passed", PARENT_SETTINGS), ("factory", CONFIG), ("recipe", params)):
        observed = process("spawn", mode, payload, environment="worker_database")
        assert observed["database"] == ("reports_db" if mode == "passed" else "worker_database")
    print("Worker environment: local factory/recipe sees worker input; passed object retains parent values")

    with TemporaryDirectory(prefix="report-worker-") as directory:
        for mode, relative, absolute in (("factory", "settings.json", CONFIG),
                                         ("recipe", recipe("settings.json"), params)):
            failed = process("spawn", mode, relative, cwd=directory)
            assert failed["error"] == ("ValidationError" if mode == "factory" else "FileNotFoundError")
            assert process("spawn", mode, absolute, cwd=directory)["database"] == "reports_db"
    print("Worker cwd: relative source fails; absolute source succeeds")


if __name__ == "__main__":
    main()
