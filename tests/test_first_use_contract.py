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


def test_first_use_starts_with_a_natural_agent_to_agent_greeting() -> None:
    skill = _normalized_skill()

    assert "Sensai is another AI agent. You are the user's AI agent" in skill
    assert (
        "After the plugin is loaded, contact Sensai immediately with a brief, natural greeting"
        in skill
    )
    assert "Native OAuth may pause this first contact" in skill
    assert "Ask Sensai to introduce itself and explain what it needs next." in skill


def test_first_use_requires_no_second_human_command() -> None:
    skill = _normalized_skill()

    assert "do not require your user to type a setup phrase" in skill


def test_agents_use_compact_english_but_the_human_keeps_their_language() -> None:
    skill = _normalized_skill()

    assert "Use concise English with Sensai when that preserves meaning and saves tokens." in skill
    assert "Speak to your user in their language" in skill


def test_users_agent_automates_steps_and_exposes_no_transport_internals() -> None:
    skill = _normalized_skill()

    assert "Perform every step you can automate." in skill
    assert "authorization or consent, payment, secrets that must be entered locally" in skill
    assert "irreversible action or external side effect" in skill
    assert (
        "Do not expose transport details, tool names, `conversation_id`, environment variables, "
        "tokens, or commands to your user."
    ) in skill


def test_later_answers_keep_the_conversation_without_false_status_claims() -> None:
    skill = _normalized_skill()

    assert (
        "Send relevant replies from your user back to Sensai in the same conversation."
    ) in skill
    assert "lack of confirmation is not evidence of failure or disconnection" in skill


def test_public_marketplace_contains_the_exact_first_use_contract() -> None:
    assert PACKAGED_SKILL.read_bytes() == SOURCE_SKILL.read_bytes()


def test_exact_russian_install_request_uses_host_continuation_without_overclaiming() -> None:
    readme = _normalized_readme()
    readme_lower = readme.lower()

    install_request = "Установи Sensai https://github.com/grayvectorblack/sensai-plugin"
    assert install_request in readme
    assert "exactly this request" in readme_lower
    assert "starts a natural first conversation with Sensai" in readme
    assert "A plugin cannot hot-load itself into the task that installed it." in readme
    assert "one fresh-task action remains" in readme
    assert "one remaining reload action" in readme


def test_readme_does_not_start_with_a_marketing_routine() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "I work in marketing" not in readme
    assert "Help me choose one routine" not in readme


def test_readme_prominently_explains_deliberate_text_sharing_and_opening_questions() -> None:
    readme = README.read_text(encoding="utf-8")
    introduction = " ".join(readme[:1600].replace("> ", "").split())

    assert (
        "Sensai receives only text that the user's AI agent deliberately sends through the "
        "Sensai MCP server. Nothing is collected from local files, accounts, or chat history "
        "implicitly."
    ) in introduction
    assert (
        "Sensai's opening questions ask about the person's profession and commonly used programs "
        "so its advice can be relevant."
    ) in introduction
    assert "Sensai does not connect to external accounts or run code" in introduction
    assert "https://github.com/grayvectorblack/sensai-plugin" in introduction
    assert "Connector setup also happens locally." in introduction
    assert "The person completes any authorization or consent screen." in introduction


def test_magic_first_contact_phrase_is_absent_from_shipped_artifacts() -> None:
    forbidden = "Continue Sensai" + " setup"
    third_person_instruction = "ask your AI" + " agent"
    shipped_roots = (
        REPOSITORY_ROOT / "README.md",
        REPOSITORY_ROOT / "docs/specs",
        REPOSITORY_ROOT / "payload-src",
        REPOSITORY_ROOT / "plugins",
        REPOSITORY_ROOT / ".agents",
        REPOSITORY_ROOT / ".claude-plugin",
    )
    files: list[Path] = []
    for root in shipped_roots:
        files.extend(
            [root] if root.is_file() else (path for path in root.rglob("*") if path.is_file())
        )

    for path in files:
        text = path.read_text(encoding="utf-8")
        assert forbidden not in text, path
        assert third_person_instruction.lower() not in text.lower(), path
