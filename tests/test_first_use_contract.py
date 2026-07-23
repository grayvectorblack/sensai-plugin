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
        "After the plugin is loaded, call `tell_sensai` immediately with a brief, natural greeting"
        in skill
    )
    assert "asks Sensai to introduce itself and explain what it needs next" in skill
    assert "Authorization may pause this first call" in skill


def test_users_agent_handles_native_oauth_without_manual_credential_copying() -> None:
    skill = _normalized_skill()

    assert "use your host's native MCP sign-in for the installed Sensai server" in skill
    assert "In Codex, run `codex mcp login sensai` yourself" in skill
    assert "Never ask the user to run this command." in skill
    assert "Codex's native callback window is five minutes." in skill
    assert "continue polling the same command throughout that window" in skill
    assert (
        "Do not end the turn, ask the user to reply when done, or ask the user to run any command "
        "while the login command is still running."
    ) in skill
    assert "If the native callback window actually times out" in skill
    assert "immediately start a fresh native login yourself" in skill
    assert "complete only the browser login and consent screen" in skill
    assert "then retry the same greeting" in skill
    assert (
        "Never ask your user to copy an authorization URL, code, or credential into chat or local "
        "configuration."
    ) in skill
    assert (
        "While authorization is pending, speak to your user in ordinary language only."
    ) in skill
    assert (
        "Never mention MCP, a callback or listener, a process, command, path, plugin version, or "
        "internal session."
    ) in skill
    assert ("Never claim a browser opened until navigation is actually observed.") in skill
    assert (
        "The only safe installation status updates are that Sensai is being connected or Sensai "
        "is ready."
    ) in skill
    assert "Do not ask the user to run commands or report `done`." in skill


def test_first_use_prefers_automatic_activation_and_has_one_safe_handoff() -> None:
    skill = _normalized_skill()
    continuation = "Continue with Sensai and contact Sensai automatically."

    assert (
        "After successful installation, if the host can load or activate the plugin in the current "
        "chat, continue automatically and contact Sensai without waiting for another user message."
    ) in skill
    assert (
        "If the host can create a fresh chat or task itself, create it and continue there "
        "automatically."
    ) in skill
    assert (
        "Only if the platform truly requires the user to start a fresh chat, offer exactly one "
        f"short copyable continuation sentence: `{continuation}`"
    ) in skill
    assert skill.count(continuation) == 1
    assert "Never ask the user to greet Sensai manually." in skill
    assert (
        "Do not include MCP, commands, paths, a plugin version, or transport details in that "
        "sentence or in a status update."
    ) in skill


def test_native_plugin_installation_has_no_skill_installer_fallback() -> None:
    skill = _normalized_skill()

    assert "Native plugin installation is the only supported installation path." in skill
    assert "Never use a skill installer" in skill
    assert "do not copy files from an internal repository path" in skill
    assert (
        "If native plugin installation is unavailable, say plainly that Sensai could not be "
        "installed and stop."
    ) in skill
    assert "Do not invent a fallback installation." in skill


def test_installation_status_never_exposes_technical_details_to_the_human() -> None:
    skill = _normalized_skill()

    assert (
        "Never show the user a plugin manager, an internal repository path, a plugin version, MCP "
        "or transport details, or an installation command."
    ) in skill
    assert (
        "The only safe installation status updates are that Sensai is being connected or Sensai "
        "is ready."
    ) in skill


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
    assert (
        "During discovery, relay the user's factual answer without adding a request to recommend, "
        "choose, design, or set up one scenario."
    ) in skill
    assert "Let Sensai decide when to ask the next question or present options." in skill
    assert "lack of confirmation is not evidence of failure or disconnection" in skill


def test_public_marketplace_contains_the_exact_first_use_contract() -> None:
    assert PACKAGED_SKILL.read_bytes() == SOURCE_SKILL.read_bytes()


def test_readme_hands_off_from_the_person_to_the_installed_agent() -> None:
    readme = _normalized_readme()
    continuation = "Continue with Sensai and contact Sensai automatically."

    assert "## Installation (human)" in readme
    assert "This is the person's only action:" in readme
    assert (
        "Install the Sensai plugin from https://github.com/grayvectorblack/sensai-plugin" in readme
    )
    assert "## After installation (AI agent)" in readme
    assert "without waiting for another human command" in readme.casefold()
    assert "starts native sign-in if needed and returns the next instruction" in readme
    assert "Never use a skill installer" in readme
    assert "Never ask the person to greet Sensai manually." in readme
    assert readme.count(continuation) == 1


def test_readme_does_not_start_with_a_marketing_routine() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "I work in marketing" not in readme
    assert "Help me choose one routine" not in readme


def test_readme_preserves_product_context_and_removes_only_requested_copy() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "Sensai is an AI agent that advises another AI agent." in readme
    assert "Sensai may return advice, architecture, detailed implementation instructions" in readme
    assert "Public source:" not in readme
    assert "Privacy:" not in readme
    assert "After this one request" not in readme


def test_public_runtime_contains_no_legacy_install_or_manual_auth_flow() -> None:
    forbidden = (
        "black-vector.com/sensai/invite",
        "continue sensai setup",
        "one-time code",
        "invitation code",
        "bootstrap runner",
        "install-sensai.ps1",
        "package_runner",
        "sensai_token",
        "bearer_token_env_var",
        "paste the token",
        "copy the token",
    )
    roots = (
        README,
        REPOSITORY_ROOT / "payload-src",
        REPOSITORY_ROOT / "plugins",
        REPOSITORY_ROOT / ".agents",
        REPOSITORY_ROOT / ".claude-plugin",
    )

    for root in roots:
        paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
        for path in paths:
            content = path.read_text(encoding="utf-8").lower()
            assert not any(fragment in content for fragment in forbidden), path


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


def test_public_repository_contains_no_cyrillic_text() -> None:
    ignored_parts = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv"}
    for path in REPOSITORY_ROOT.rglob("*"):
        if not path.is_file() or any(part in ignored_parts for part in path.parts):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        assert not any("\u0400" <= character <= "\u04ff" for character in content), path
