from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = REPOSITORY_ROOT / "payload-src/shared/skills/sensai/SKILL.md"
PACKAGED_SKILL = REPOSITORY_ROOT / "plugins/sensai/skills/sensai/SKILL.md"


def _normalized_skill() -> str:
    return " ".join(SOURCE_SKILL.read_text(encoding="utf-8").split())


def test_curated_package_is_executed_instead_of_pasted_into_chat() -> None:
    skill = _normalized_skill()

    assert "curated implementation package" in skill
    assert "Do not paste the package or its file contents into chat" in skill
    assert "bundled deterministic helper" in skill
    assert "explain its validated intended result in ordinary language" in skill
    assert "normal file and command approval boundary" in skill


def test_manifest_is_complete_before_any_local_change() -> None:
    skill = _normalized_skill()

    assert "run its read-only inspection mode first" in skill
    assert "Do not validate or repair the manifest yourself" in skill
    assert "make no local change when inspection fails" in skill


def test_package_paths_and_contents_are_strictly_bounded() -> None:
    skill = _normalized_skill()

    assert "Never create, edit, validate, or remove package files yourself" in skill
    assert "scripts/package_runner.py" in skill
    assert "pass the exact structured package payload on standard input" in skill


def test_verification_and_run_use_declared_commands_under_approval() -> None:
    skill = _normalized_skill()

    assert "invoke the helper's execution mode" in skill
    assert "Do not run any package command separately" in skill
    assert "Do not translate the helper invocation into platform-specific shell syntax" in skill


def test_result_return_to_sensai_is_minimal_and_keeps_conversation() -> None:
    skill = _normalized_skill()

    assert "same retained `conversation_id`" in skill
    assert "concise factual execution result" in skill
    assert (
        "Never send local files, secrets, raw command output, or full conversation history" in skill
    )
    assert "sanitized error summary" in skill


def test_recovery_and_rollback_preserve_the_local_safety_boundary() -> None:
    skill = _normalized_skill()

    assert (
        "delegate validation, writing, execution, independent verification, "
        "and rollback to the helper" in skill
    )
    assert "Never perform recovery or rollback steps outside the helper" in skill


def test_no_package_transport_fallback_is_added() -> None:
    skill = _normalized_skill()

    assert "Do not use curl, raw HTTP, or guessed package URLs" in skill


def test_generated_skill_contains_exact_execution_contract() -> None:
    assert PACKAGED_SKILL.read_bytes() == SOURCE_SKILL.read_bytes()
