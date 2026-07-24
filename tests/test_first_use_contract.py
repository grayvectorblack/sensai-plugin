from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = REPOSITORY_ROOT / "payload-src/shared/skills/sensai/SKILL.md"
PACKAGED_SKILL = REPOSITORY_ROOT / "plugins/sensai/skills/sensai/SKILL.md"
FIRST_CONTACT_SPEC = REPOSITORY_ROOT / "docs/specs/FIRST-CONTACT-001.md"


def _text(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_public_payload_is_built_from_the_single_skill_source() -> None:
    assert PACKAGED_SKILL.read_bytes() == SOURCE_SKILL.read_bytes()


def test_skill_preserves_human_control_at_real_boundaries() -> None:
    skill = _text(SOURCE_SKILL)

    assert "Before an authorization screen or an external action" in skill
    assert "what will happen and why" in skill
    assert (
        "account choice, consent, a secret, payment, or confirmation of an external side effect"
        in skill
    )
    assert "Give technical details when the person asks." in skill
    assert "authorization code, token, or password" in skill


def test_skill_requires_confirmed_human_context() -> None:
    skill = _text(SOURCE_SKILL)

    assert "ask the person directly" in skill
    assert (
        "Do not treat workspace contents, account labels, installed tools, "
        "or your own guesses as facts"
        in skill
    )
    assert "Relay only facts the person confirms." in skill


def test_skill_keeps_one_real_conversation_without_inventing_ids() -> None:
    skill = _text(SOURCE_SKILL)

    assert "omit `conversation_id`" in skill
    assert "retain that exact value for later calls in the same conversation" in skill
    assert "Do not reuse it for an unrelated conversation or invent a placeholder." in skill


def test_skill_recovers_codex_auth_without_copying_secrets() -> None:
    skill = _text(SOURCE_SKILL)

    assert "If a Codex `tell_sensai` call returns `Auth required`" in skill
    assert "Sensai needs a Google sign-in for this session and why." in skill
    assert "Run `codex mcp login sensai` through Codex" in skill
    assert "retry the original request once after success" in skill
    assert (
        "Do not claim that a browser opened or access was granted until the host confirms it."
        in skill
    )


def test_skill_relays_variable_sensai_options_without_deciding_for_the_person() -> None:
    skill = _text(SOURCE_SKILL)

    assert "present every distinct option and the recommendation" in skill
    assert "Do not choose on the person's behalf." in skill
    assert "three options" not in skill.lower()
    assert "exactly three" not in skill.lower()


def test_first_contact_spec_documents_behavior_not_private_mechanics_or_fixed_counts() -> None:
    spec = _text(FIRST_CONTACT_SPEC)

    assert "briefly explains what will happen and why" in spec
    assert "technical details when asked" in spec
    assert "number of options is its judgment, not a protocol rule" in spec
    assert "three onboarding scenarios" not in spec.lower()
    assert "terminal-wait mechanism private" not in spec.lower()
