"""Keep settings subclasses on the library's dynamic constructor contract."""
from pydantic._internal._model_construction import ModelMetaclass


class _SettingsMetaclass(ModelMetaclass):
    """Inherit runtime construction without redeclaring dataclass_transform.

    Mypy 1.10.1 synthesizes field-only constructors for classes whose metaclass
    is directly decorated as a dataclass transform. An undecorated private
    subclass preserves our inherited constructor and its source controls.
    Runtime model construction remains Pydantic-owned.
    """
