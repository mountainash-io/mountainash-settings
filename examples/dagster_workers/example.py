"""Run real Dagster subprocess steps against a warmed parent cache."""

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from dagster import DagsterInstance, execute_job, reconstructable

# Keep this recipe self-contained and importable even under Python -I.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import definitions


def main():
    definitions.PARENT_SETTINGS = definitions.PlainSettings()
    start = definitions.READS
    assert definitions.recipe(str(definitions.CONFIG)).get_settings().DATABASE == "reports_db"
    assert definitions.READS - start == 1
    config = {"resources": {"settings": {"config": {"path": str(definitions.CONFIG)}}}}
    assert definitions.eager_job.execute_in_process().success
    assert definitions.cache_only_job.execute_in_process(run_config=config).success
    print("In-process: parent object and warmed cache both work")

    with TemporaryDirectory(prefix="report-dagster-") as directory:
        with DagsterInstance.local_temp(tempdir=directory) as instance:
            for name, factory in (
                ("eager", definitions.define_eager),
                ("cache_only", definitions.define_cache_only),
                ("factory", definitions.define_factory),
                ("recipe", definitions.define_recipe),
            ):
                run_config = config if name in ("cache_only", "recipe") else {}
                with execute_job(reconstructable(factory), instance=instance,
                                 run_config=run_config, raise_on_error=False) as result:
                    assert result.success is (name in ("factory", "recipe"))
                    logs = instance.all_logs(result.run_id)
                    probes = [json.loads(entry.message.removeprefix("CACHE_PROBE "))
                              for entry in logs if entry.message.startswith("CACHE_PROBE ")]
                    # Entering the execution-result context also builds parent resources.
                    workers = [entry for entry in probes if entry["pid"] != os.getpid()]
                    errors = [event.event_specific_data.error for event in result.all_events
                              if event.is_step_failure]
                    if name == "eager":
                        assert any(error.cause and "AttributeError" in error.cause.message
                                   for error in errors)
                    elif name == "cache_only":
                        assert workers and all(not entry["cached"] for entry in workers)
                        assert any("Cached settings context is not initialised" in error.message
                                   for error in errors)
                    else:
                        assert {event.step_key for event in result.all_events
                                if event.is_step_success} == {"first", "second"}
                    if name == "recipe":
                        assert len({entry["pid"] for entry in workers}) == 2
                        assert all(not entry["cached"] and entry["first_reads"] == 1
                                   and entry["second_reads"] == 0 for entry in workers)
                    print(f"Multiprocess {name}: {'succeeds' if result.success else 'expected failure'}")
    print("Recipe: each step worker rehydrates once; second retrieval reads no file")


if __name__ == "__main__":
    main()
