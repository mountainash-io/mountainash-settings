"""Discriminated-union auth specs for settings profiles."""

from __future__ import annotations

from .azure import AzureADAuth, WindowsAuth
from .base import AuthSpec
from .certificate import CertificateAuth
from .iam import IAMAuth
from .kerberos import KerberosAuth
from .none import NoAuth
from .oauth2 import OAuth2Auth
from .password import PasswordAuth
from .service_account import ServiceAccountAuth
from .token import JWTAuth, TokenAuth

__all__ = [
    "AuthSpec",
    "AzureADAuth",
    "CertificateAuth",
    "IAMAuth",
    "JWTAuth",
    "KerberosAuth",
    "NoAuth",
    "OAuth2Auth",
    "PasswordAuth",
    "ServiceAccountAuth",
    "TokenAuth",
    "WindowsAuth",
]
