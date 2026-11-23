"""Keep settings subclasses on the library's dynamic constructor contract."""
import functools
from types import FunctionType
from typing import Any, Callable

from pydantic._internal._model_construction import ModelMetaclass

_SOURCE_HOOK = "settings_customise_sources"


def _prepare_incoming_sources(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    """Hydrate the incoming dotenv source of an active direct construction, if it is one.

    Pydantic dispatches the hook as ``hook(cls, init_settings=..., dotenv_settings=...)``;
    manual callers pass the five arguments positionally. ``args`` excludes any receiver.
    """
    # Imported lazily: base_settings imports this module for its metaclass.
    from .base_settings import _prepare_direct_dotenv

    settings_cls = kwargs["settings_cls"] if "settings_cls" in kwargs else (args[0] if args else None)
    dotenv_settings = kwargs["dotenv_settings"] if "dotenv_settings" in kwargs else (
        args[3] if len(args) > 3 else None
    )
    _prepare_direct_dotenv(settings_cls, dotenv_settings)


def _hydrating(call: Callable[..., Any]) -> Callable[..., Any]:
    """``call`` preceded by preparing the incoming dotenv source."""

    @functools.wraps(call)
    def hook(*args: Any, **kwargs: Any) -> Any:
        _prepare_incoming_sources(args, kwargs)
        return call(*args, **kwargs)

    return hook


def _wrap_source_hook(original: Any) -> Any:
    """Return an equivalent descriptor that prepares the incoming dotenv source first.

    Each form keeps the binding it already had: a function or staticmethod is called
    exactly as before, and a classmethod (or other class-bound descriptor) is bound to
    the actual receiver at call time, so a subclass's zero-argument ``super()`` still
    reaches it. A classmethod stays a classmethod, so inheriting subclasses keep resolving
    to one shared function (cache admission compares that identity).
    """
    if isinstance(original, staticmethod):
        return staticmethod(_hydrating(original.__func__))
    if isinstance(original, FunctionType):
        return _hydrating(original)
    if not hasattr(original, "__get__"):
        return staticmethod(_hydrating(original))

    def class_hook(cls: Any, *args: Any, **kwargs: Any) -> Any:
        _prepare_incoming_sources(args, kwargs)
        return original.__get__(None, cls)(*args, **kwargs)

    return classmethod(functools.wraps(getattr(original, "__func__", original))(class_hook))


class _SettingsMetaclass(ModelMetaclass):
    """Inherit runtime construction without redeclaring dataclass_transform.

    Mypy 1.10.1 synthesizes field-only constructors for classes whose metaclass
    is directly decorated as a dataclass transform. An undecorated private
    subclass preserves our inherited constructor and its source controls.
    Runtime model construction remains Pydantic-owned, apart from wrapping the
    source hook declared by the base class or in a subclass body (never one that
    is merely inherited) so a direct construction's incoming dotenv source is
    prepared through the protected adapter before the hook can see it.
    """

    def __init__(
        cls, cls_name: str, bases: tuple[type, ...], namespace: dict[str, Any], *args: Any, **kwargs: Any,
    ) -> None:
        # After construction, not in __new__: Pydantic's own __new__ must stay at the
        # caller's stack depth to capture the defining namespace for forward references.
        super().__init__(cls_name, bases, namespace, *args, **kwargs)
        if _SOURCE_HOOK in namespace:
            setattr(cls, _SOURCE_HOOK, _wrap_source_hook(namespace[_SOURCE_HOOK]))
