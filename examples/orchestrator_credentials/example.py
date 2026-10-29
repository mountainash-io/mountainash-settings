"""Compare accidental logging of orchestrators holding settings or a recipe."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings

from mountainash_settings import MountainAshBaseSettings, SettingsParameters
from mountainash_settings.settings_cache.settings_functions import get_settings_manager


class EagerSettings(BaseSettings):
    DATABASE: str
    PASSWORD: str


class MaskedSettings(BaseSettings):
    DATABASE: str
    PASSWORD: SecretStr


class AppSettings(MountainAshBaseSettings):
    DATABASE: str
    PASSWORD: str


@dataclass
class EagerOrchestrator:
    settings: EagerSettings | MaskedSettings

    def run_task(self) -> str:
        return self.settings.DATABASE


@dataclass
class RecipeOrchestrator:
    settings_parameters: SettingsParameters

    def run_task(self) -> str:
        # Resolve locally, rather than retaining resolved credentials on self.
        settings = self.settings_parameters.get_settings()
        assert settings.PASSWORD
        return settings.DATABASE


def main() -> None:
    # Synthetic only. Never send the rendered objects below to an actual log.
    password = "synthetic-report-password"
    eager = EagerOrchestrator(EagerSettings(DATABASE="reports_db", PASSWORD=password))
    masked = EagerOrchestrator(MaskedSettings(DATABASE="reports_db", PASSWORD=password))
    params = SettingsParameters(
        settings_class=AppSettings, env_prefix="REPORT_",
        kwargs={"DATABASE": "reports_db", "PASSWORD": password},
    )
    recipe = RecipeOrchestrator(params)
    for label, orchestrator, exposed in (
        ("Eager string", eager, True),
        ("Recipe", recipe, False),
        ("Eager SecretStr", masked, False),
    ):
        # Dataclass repr includes attributes. Ordinary object repr need not.
        assert (password in repr(orchestrator)) is exposed
        assert (password in str(vars(orchestrator))) is exposed
        assert orchestrator.run_task() == "reports_db"
        assert (password in repr(orchestrator)) is exposed
        print(f"{label}: credential in orchestrator repr/attributes = {exposed}")

    file_recipe = RecipeOrchestrator(SettingsParameters(
        settings_class=AppSettings, env_prefix="REPORT_",
        config_files=[Path(__file__).with_name("settings.json")],
    ))
    assert password not in repr(file_recipe)
    assert password not in str(vars(file_recipe))
    assert file_recipe.settings_parameters.kwargs is None
    assert not get_settings_manager().is_initialised(file_recipe.settings_parameters)
    assert file_recipe.run_task() == "reports_db"
    assert password not in repr(file_recipe)
    assert password not in str(vars(file_recipe))
    print("File recipe: resolved credentials stay off orchestrator attributes")

    # Safe representation is not safe arbitrary inspection or serialization.
    assert params.kwargs is not None and params.kwargs["PASSWORD"] == password
    assert password in repr(params.get_settings())
    assert isinstance(masked.settings.PASSWORD, SecretStr)
    assert masked.settings.PASSWORD.get_secret_value() == password
    print("Explicit kwargs/resolved-value access still exposes credentials")


if __name__ == "__main__":
    main()
