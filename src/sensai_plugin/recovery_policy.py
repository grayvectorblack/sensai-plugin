"""Deterministic recovery actions for Sensai authentication failures."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class AuthError(StrEnum):
    REQUIRED = "auth_required"
    EXPIRED = "authentication_expired"


class RecoveryActionKind(StrEnum):
    NATIVE_CODEX_LOGIN = "native_codex_login"
    RETRY_SENSAI_REQUEST = "retry_sensai_request"


class HumanAction(StrEnum):
    COMPLETE_NATIVE_BROWSER_CONSENT = "complete_native_browser_consent"


@dataclass(frozen=True)
class RecoveryRequest:
    method: str
    arguments: Mapping[str, object]


@dataclass(frozen=True)
class RecoveryAction:
    kind: RecoveryActionKind
    command: str | None = None
    request: RecoveryRequest | None = None

    @classmethod
    def native_codex_login(cls, command: str) -> RecoveryAction:
        return cls(RecoveryActionKind.NATIVE_CODEX_LOGIN, command=command)

    @classmethod
    def retry_sensai_request(cls, request: RecoveryRequest) -> RecoveryAction:
        return cls(RecoveryActionKind.RETRY_SENSAI_REQUEST, request=request)


@dataclass(frozen=True)
class RecoveryPlan:
    actions: tuple[RecoveryAction, ...]
    human_actions: tuple[HumanAction, ...]


def recovery_plan(error: AuthError, request: RecoveryRequest) -> RecoveryPlan:
    """Recover recognized authentication failures without a manual OAuth URL step."""
    if error not in (AuthError.REQUIRED, AuthError.EXPIRED):
        raise ValueError(f"Unsupported authentication error: {error}")
    return RecoveryPlan(
        actions=(
            RecoveryAction.native_codex_login("codex mcp login sensai"),
            RecoveryAction.retry_sensai_request(request),
        ),
        human_actions=(HumanAction.COMPLETE_NATIVE_BROWSER_CONSENT,),
    )
