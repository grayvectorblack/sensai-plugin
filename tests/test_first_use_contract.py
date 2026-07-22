from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = REPOSITORY_ROOT / "payload-src/shared/skills/sensai/SKILL.md"
PACKAGED_SKILL = REPOSITORY_ROOT / "plugins/sensai/skills/sensai/SKILL.md"
README = REPOSITORY_ROOT / "README.md"


def _normalized_skill() -> str:
    return " ".join(SOURCE_SKILL.read_text(encoding="utf-8").split())


def _normalized_readme() -> str:
    return " ".join(README.read_text(encoding="utf-8").split())


def test_first_use_requests_immediately_start_sensai_onboarding() -> None:
    skill = _normalized_skill()

    assert (
        'Treat "Continue Sensai setup" and equivalent natural requests to start, continue, or '
        "finish "
        "Sensai setup as first use. Immediately call `tell_sensai`"
    ) in skill
    assert 'Send exactly this first-contact message: "Continue Sensai setup".' in skill
    assert "Do not add instructions or user context to that first message." in skill


def test_first_use_accepts_natural_start_wording_without_exposing_a_command() -> None:
    skill = _normalized_skill()

    assert "equivalent natural requests to start, continue, or finish Sensai setup" in skill
    assert "The user does not need to know or type that first-contact message." in skill


def test_profession_and_one_to_five_programs_are_valid_follow_up_answers() -> None:
    skill = _normalized_skill()

    assert "profession and up to five programs or websites" in skill
    assert "Accept any answer containing one to five programs or websites" in skill
    assert "which five programs or websites" not in skill


def test_first_use_does_not_require_a_scenario_or_expose_internals() -> None:
    skill = _normalized_skill()

    assert "Do not ask the user for a work scenario before this first call." in skill
    assert (
        "Never expose MCP, tool names, `conversation_id`, environment variables, invitation "
        "tokens, or commands to the user."
    ) in skill


def test_sensai_response_is_relayed_and_later_answers_keep_the_conversation() -> None:
    skill = _normalized_skill()

    assert "Relay Sensai's response to the user in plain language." in skill
    assert (
        "Treat the user's later natural answers as replies to Sensai, call `tell_sensai` again "
        "with those answers, and pass the retained `conversation_id`."
    ) in skill
    assert (
        "Do not ask again for information the user has already provided unless Sensai asks for "
        "clarification."
    ) in skill


def test_public_marketplace_contains_the_exact_first_use_contract() -> None:
    assert PACKAGED_SKILL.read_bytes() == SOURCE_SKILL.read_bytes()


def test_exact_russian_install_request_continues_without_a_second_user_phrase() -> None:
    readme = _normalized_readme()
    readme_lower = readme.lower()

    install_request = "Установи Sensai https://black-vector.com/sensai/invite#..."
    assert install_request in readme
    assert "single request" in readme_lower
    assert "creates one with `Continue Sensai setup` as the initial prompt" in readme
    assert "does not type a second setup phrase" in readme
    assert readme_lower.index(install_request.lower()) < readme_lower.index("continue sensai setup")


def test_readme_does_not_start_with_a_marketing_routine() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "I work in marketing" not in readme
    assert "Help me choose one routine" not in readme


def test_readme_prominently_explains_deliberate_text_sharing_and_opening_questions() -> None:
    readme = README.read_text(encoding="utf-8")
    introduction = " ".join(readme[:1600].replace("> ", "").split())

    assert (
        "Sensai receives only the text that your AI agent deliberately sends to Sensai; "
        "nothing is collected secretly."
    ) in introduction
    assert (
        "The opening questions ask about your profession and commonly used programs so Sensai "
        "can give relevant guidance."
    ) in introduction
    assert "Sensai does not connect external services or act in user accounts." in introduction
