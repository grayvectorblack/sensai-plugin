from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = REPOSITORY_ROOT / "payload-src/shared/skills/sensai/SKILL.md"
PACKAGED_SKILL = REPOSITORY_ROOT / "plugins/sensai/skills/sensai/SKILL.md"
README = REPOSITORY_ROOT / "README.md"
FIRST_CONTACT_SPEC = REPOSITORY_ROOT / "docs/specs/FIRST-CONTACT-001.md"
INSTALL_URL = "https://github.com/grayvectorblack/sensai-plugin"
CONTINUATION = "Continue with Sensai and contact Sensai automatically."
CODEX_MARKETPLACE_COMMAND = "codex plugin marketplace add grayvectorblack/sensai-plugin"
CODEX_INSTALL_COMMAND = "codex plugin add sensai@sensai"
CLAUDE_MARKETPLACE_COMMAND = "claude plugin marketplace add grayvectorblack/sensai-plugin"
CLAUDE_INSTALL_COMMAND = "claude plugin install sensai@sensai --scope user"
INSTALL_REQUEST = (
    "Open https://github.com/grayvectorblack/sensai-plugin, follow its installation instructions "
    "without technical details, complete Google sign-in, and continue automatically; only after "
    "sign-in, if a new chat is required, give me exactly this copyable sentence: "
    f"{CONTINUATION}"
)


def _normalized_skill() -> str:
    return " ".join(SOURCE_SKILL.read_text(encoding="utf-8").split())


def _normalized_readme() -> str:
    return " ".join(README.read_text(encoding="utf-8").split())


def _normalized_spec() -> str:
    return " ".join(FIRST_CONTACT_SPEC.read_text(encoding="utf-8").split())


def _sentence_count(text: str) -> int:
    without_url = text.replace(INSTALL_URL, "URL")
    return sum(without_url.count(mark) for mark in ".!?")


def _assert_pre_authorized_human_request(text: str) -> None:
    open_repository = text.index(f"Open {INSTALL_URL}")
    read_installation = text.index("follow its installation instructions")
    complete_sign_in = text.index("complete Google sign-in")
    only_after_sign_in = text.index("only after sign-in")
    new_chat_continuation = text.index(
        f"if a new chat is required, give me exactly this copyable sentence: {CONTINUATION}"
    )

    assert (
        open_repository
        < read_installation
        < complete_sign_in
        < only_after_sign_in
        < new_chat_continuation
    )


def test_first_use_starts_with_a_natural_agent_to_agent_greeting() -> None:
    skill = _normalized_skill()

    assert "Sensai is another AI agent. You are the user's AI agent" in skill
    assert (
        "After the plugin is loaded, call `tell_sensai` immediately with a brief, natural greeting"
        in skill
    )
    assert "asks Sensai to introduce itself and explain what it needs next" in skill
    assert "Authorization should already be present." in skill


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
    assert "A brief ordinary-language progress acknowledgement is allowed." in skill
    assert "Keep every progress update free of technical details." in skill
    assert "Do not ask the user to run commands or report `done`." in skill


def test_normal_install_orders_authorization_before_the_single_fresh_chat() -> None:
    readme = _normalized_readme()
    codex_marketplace = readme.index(CODEX_MARKETPLACE_COMMAND)
    codex_install = readme.index(CODEX_INSTALL_COMMAND)
    claude_marketplace = readme.index(CLAUDE_MARKETPLACE_COMMAND)
    claude_install = readme.index(CLAUDE_INSTALL_COMMAND)
    authorize = readme.index(
        "While still in this installer chat, immediately complete the host's native Sensai "
        "Google sign-in yourself."
    )
    fresh_context = readme.index("Only after sign-in succeeds, load Sensai once:")
    first_call = readme.index(
        "That loaded context must contact Sensai immediately with authorization already present."
    )

    assert codex_marketplace < codex_install < authorize
    assert claude_marketplace < claude_install < authorize
    assert authorize < fresh_context < first_call
    assert "Do not create, offer, or start the fresh chat before sign-in succeeds." in readme
    assert (
        "The normal installation path has exactly one fresh-context boundary and never starts a "
        "nested Codex process."
    ) in readme
    assert readme.count(CONTINUATION) == 1


def test_readme_requires_real_native_install_commands_before_reporting_unsupported() -> None:
    readme = _normalized_readme()

    for command in (
        CODEX_MARKETPLACE_COMMAND,
        CODEX_INSTALL_COMMAND,
        CLAUDE_MARKETPLACE_COMMAND,
        CLAUDE_INSTALL_COMMAND,
    ):
        assert readme.count(command) == 1

    run_commands = readme.index(
        "Run the commands for the current host instead of inferring that native installation is "
        "unsupported."
    )
    nonzero = readme.index(
        "Only infer or report that native installation is unsupported, or say that Sensai could "
        "not be installed, after one of the applicable commands actually exits with a nonzero "
        "status."
    )
    private = readme.index(
        "Keep the commands, exit status, marketplace, and other installation mechanics private "
        "from the person."
    )

    assert run_commands < readme.index(CODEX_MARKETPLACE_COMMAND) < nonzero < private
    assert run_commands < readme.index(CLAUDE_MARKETPLACE_COMMAND) < nonzero < private
    assert "Never use a skill installer" in readme


def test_first_contact_spec_enforces_the_same_one_chat_order() -> None:
    spec = _normalized_spec()
    codex_marketplace = spec.index(CODEX_MARKETPLACE_COMMAND)
    codex_install = spec.index(CODEX_INSTALL_COMMAND)
    claude_marketplace = spec.index(CLAUDE_MARKETPLACE_COMMAND)
    claude_install = spec.index(CLAUDE_INSTALL_COMMAND)
    last_install = max(codex_install, claude_install)
    authorize = spec.index(
        "installing agent completes Sensai's native Google sign-in", last_install
    )
    fresh_context = spec.index("After sign-in succeeds", authorize)
    first_call = spec.index("greets Sensai immediately", fresh_context)

    assert codex_marketplace < codex_install < authorize
    assert claude_marketplace < claude_install < authorize
    assert authorize < fresh_context < first_call
    assert "A second nested Codex launch is forbidden." in spec
    assert "A second fresh-context handoff is forbidden in the normal path." in spec
    assert "only after an applicable installation command actually returns a nonzero result" in spec


def test_loaded_skill_expects_pre_authorization_but_keeps_recovery() -> None:
    skill = _normalized_skill()
    normal = skill.index(
        "The normal installation flow completes native Sensai Google sign-in before this skill is "
        "loaded in its one fresh chat."
    )
    first_call = skill.index("After the plugin is loaded, call `tell_sensai` immediately")
    fallback = skill.index("If authorization is unexpectedly absent")

    assert normal < first_call < fallback
    assert "Never start a nested Codex process to continue or call Sensai." in skill
    assert "Never create a second fresh-chat handoff for authorization." in skill


def test_first_use_prefers_automatic_activation_and_has_one_safe_handoff() -> None:
    skill = _normalized_skill()
    assert "The normal installation flow" in skill
    assert skill.count(CONTINUATION) == 0
    assert "Never ask the user to greet Sensai manually." in skill
    assert "Never ask the user to introduce themselves." in skill
    assert "Never create a second fresh-chat handoff for authorization." in skill


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

    assert "A brief ordinary-language progress acknowledgement is allowed." in skill
    assert (
        "Never show the user a plugin manager, an internal repository path, a plugin version, MCP "
        "or transport details, or an installation command."
    ) in skill
    assert "Keep every progress update free of technical details." in skill


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
    install_request = INSTALL_REQUEST

    assert "## Installation (human)" in readme
    assert "This is the person's only action:" in readme
    assert readme.count(install_request) == 1
    assert install_request.startswith("Open ")
    assert ", follow " in install_request
    assert not install_request.startswith("Install ")
    assert _sentence_count(install_request) == 1
    _assert_pre_authorized_human_request(install_request)
    assert "follow its installation instructions without technical details" in install_request
    assert "complete Google sign-in" in install_request
    assert "continue automatically" in install_request
    assert CODEX_MARKETPLACE_COMMAND not in install_request
    assert CODEX_INSTALL_COMMAND not in install_request
    assert CLAUDE_MARKETPLACE_COMMAND not in install_request
    assert CLAUDE_INSTALL_COMMAND not in install_request
    assert (
        "only after sign-in, if a new chat is required, give me exactly this copyable sentence: "
        f"{CONTINUATION}" in install_request
    )
    assert "## After installation (AI agent)" in readme
    assert "without waiting for another human command" in readme.casefold()
    assert "complete the host's native Sensai Google sign-in yourself" in readme
    assert "Do not create, offer, or start the fresh chat before sign-in succeeds." in readme
    no_early_handoff = readme.index(
        "Do not create, offer, or start the fresh chat before sign-in succeeds."
    )
    continuation_handoff = readme.index("offer exactly the copyable continuation sentence")
    assert no_early_handoff < continuation_handoff
    assert "Never use a skill installer" in readme
    assert "Never ask the person to greet Sensai manually." in readme
    assert "Never ask the person to introduce themselves." in readme
    assert readme.count(CONTINUATION) == 1


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
