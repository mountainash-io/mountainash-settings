"""Lightweight auth model stubs for tests.

These replace mountainash-auth-client imports so mountainash-settings tests
can run without that dependency.  The stubs mirror just enough of the real
AuthSpec contract (frozen pydantic model with ``kind`` discriminator) to
satisfy Profile's discriminated-union field installation and the
base-settings nested-model secret resolution tests.
"""

from __future__ import annotations

import typing as t

from pydantic import BaseModel, ConfigDict, SecretStr


class StubAuthSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: str = ""


class StubNoAuth(StubAuthSpec):
    kind: t.Literal["none"] = "none"


class StubPasswordAuth(StubAuthSpec):
    kind: t.Literal["password"] = "password"
    username: str
    password: SecretStr
