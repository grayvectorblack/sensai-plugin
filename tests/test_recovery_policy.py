from __future__ import annotations

import pytest

from sensai_plugin.recovery_policy import (
    AuthError,
    HumanAction,
    RecoveryAction,
    RecoveryRequest,
    recovery_plan,
)


@pytest.mark.parametrize("error", [AuthError.REQUIRED, AuthError.EXPIRED])
def test_auth_errors_recover_with_native_login_then_the_same_sensai_request(
    error: AuthError,
) -> None:
    request = RecoveryRequest(method="tell_sensai", arguments={"message": "Help me plan today."})

    plan = recovery_plan(error, request)

    assert plan.actions == (
        RecoveryAction.native_codex_login("codex mcp login sensai"),
        RecoveryAction.retry_sensai_request(request),
    )
    assert plan.human_actions == (HumanAction.COMPLETE_NATIVE_BROWSER_CONSENT,)
