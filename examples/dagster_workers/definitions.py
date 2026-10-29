"""Importable jobs: subprocess reconstruction imports this module afresh."""

import json
import os
from pathlib import Path
import sys

from dagster import job, op, resource
from pydantic_settings import BaseSettings, JsonConfigSettingsSource

from mountainash_settings import MountainAshBaseSettings, SettingsParameters
from mountainash_settings.settings_cache.settings_functions import get_settings_manager

CONFIG = Path(__file__).with_name("settings.json").resolve()
PARENT_SETTINGS = None
READS = 0


def count_reads(event, args):
    global READS
    if event == "open" and isinstance(args[0], (str, bytes)):
        if os.path.abspath(os.fsdecode(args[0])) == str(CONFIG) and args[1] in ("r", "rb"):
            READS += 1


sys.addaudithook(count_reads)


class PlainSettings(BaseSettings):
    DATABASE: str

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                   dotenv_settings, file_secret_settings):
        return init_settings, env_settings, JsonConfigSettingsSource(settings_cls, json_file=CONFIG)


class AppSettings(MountainAshBaseSettings):
    DATABASE: str


def recipe(path):
    return SettingsParameters(settings_class=AppSettings, config_files=[path], env_prefix="REPORT_")


@resource
def eager_resource(_):
    return PARENT_SETTINGS


@resource
def factory_resource(_):
    return PlainSettings()


@resource(config_schema={"path": str})
def cache_only_resource(context):
    params = recipe(context.resource_config["path"])
    context.log.info("CACHE_PROBE " + json.dumps({
        "pid": os.getpid(), "cached": get_settings_manager().is_initialised(params),
    }))
    # Deliberately reproduce the assumption that startup populated every worker.
    return get_settings_manager().get_settings_object(params)


@resource(config_schema={"path": str})
def recipe_resource(context):
    params = recipe(context.resource_config["path"])
    cached = get_settings_manager().is_initialised(params)
    start = READS
    settings = params.get_settings()
    first_reads = READS - start
    start = READS
    task_settings = params.get_settings(DATABASE="task_database")
    assert task_settings.DATABASE == "task_database"
    assert settings.DATABASE == "reports_db"
    context.log.info("CACHE_PROBE " + json.dumps({
        "pid": os.getpid(), "cached": cached, "first_reads": first_reads,
        "second_reads": READS - start,
    }))
    return settings


@op(required_resource_keys={"settings"})
def first(context):
    return context.resources.settings.DATABASE


@op(required_resource_keys={"settings"})
def second(context, previous: str):
    assert previous == context.resources.settings.DATABASE == "reports_db"
    return previous


@job(resource_defs={"settings": eager_resource})
def eager_job():
    second(first())


@job(resource_defs={"settings": cache_only_resource})
def cache_only_job():
    second(first())


@job(resource_defs={"settings": factory_resource})
def factory_job():
    second(first())


@job(resource_defs={"settings": recipe_resource})
def recipe_job():
    second(first())


def define_eager():
    return eager_job


def define_cache_only():
    return cache_only_job


def define_factory():
    return factory_job


def define_recipe():
    return recipe_job
