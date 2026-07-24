from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = REPOSITORY_ROOT / "payload-src/shared/skills/sensai/SKILL.md"
PACKAGED_SKILL = REPOSITORY_ROOT / "plugins/sensai/skills/sensai/SKILL.md"
README = REPOSITORY_ROOT / "README.md"
FIRST_CONTACT_SPEC = REPOSITORY_ROOT / "docs/specs/FIRST-CONTACT-001.md"
SCENARIO_RELAY_FIXTURE = REPOSITORY_ROOT / "tests/fixtures/scenario_relay_contract.json"
CODEX_DOWNLOAD_URL = "https://chatgpt.com/download/"
CLAUDE_CODE_DOWNLOAD_URL = "https://claude.ai/download"
CODEX_MARKETPLACE_COMMAND = "codex plugin marketplace add grayvectorblack/sensai-plugin"
CODEX_INSTALL_COMMAND = "codex plugin add sensai@sensai"
CLAUDE_MARKETPLACE_COMMAND = "claude plugin marketplace add grayvectorblack/sensai-plugin"
CLAUDE_INSTALL_COMMAND = "claude plugin install sensai@sensai --scope user"


def _normalized_skill() -> str:
    return " ".join(SOURCE_SKILL.read_text(encoding="utf-8").split())


def _normalized_readme() -> str:
    return " ".join(README.read_text(encoding="utf-8").split())


def _normalized_spec() -> str:
    return " ".join(FIRST_CONTACT_SPEC.read_text(encoding="utf-8").split())


def test_first_use_explicitly_invokes_sensai_from_the_loaded_plugin() -> None:
    skill = _normalized_skill()

    assert "Sensai is another AI agent. You are the user's AI agent" in skill
    assert (
        "After the plugin is loaded, immediately invoke the installed Sensai plugin by calling "
        "`tell_sensai`." in skill
    )
    assert "do not merely greet your user." in skill
    assert "Authorization should already be present." in skill


def test_codex_new_chat_link_invokes_the_installed_sensai_plugin() -> None:
    raw_readme = README.read_text(encoding="utf-8")
    match = re.search(r"\[Sensai start prompt\]\((codex://new\?prompt=[^)]+)\)", raw_readme)

    assert match is not None
    parsed = urlsplit(match.group(1))
    assert (parsed.scheme, parsed.netloc, parsed.path) == ("codex", "new", "")
    prompt_values = parse_qs(parsed.query).get("prompt")
    assert prompt_values is not None and len(prompt_values) == 1

    prompt = unquote(prompt_values[0])
    assert "plugin://sensai@sensai" in prompt
    assert re.search(r"\b(?:start|run|invoke|launch)\b", prompt, flags=re.IGNORECASE)


def test_first_tell_sensai_call_omits_conversation_id_entirely() -> None:
    skill = _normalized_skill()

    assert ("On the first `tell_sensai` call, omit `conversation_id` entirely.") in skill
    assert (
        "Never send a placeholder such as `new`, an empty string, a label, or an invented ID."
    ) in skill
    assert (
        "Only after the first successful call returns a `conversation_id`, retain that exact UUID "
        "and pass it on later calls in the same user conversation."
    ) in skill


def test_all_scenario_options_reach_the_human_before_choice() -> None:
    skill = _normalized_skill()

    assert (
        "When Sensai returns multiple scenario options and a recommendation, present every "
        "distinct option and the recommendation to your user before asking them to choose."
    ) in skill
    assert (
        "For the onboarding response with three options, show all three; never collapse the list "
        "to only the recommended option or choose on the user's behalf."
    ) in skill
    assert ("Preserve the user's language and each option's concise meaning.") in skill


def test_first_contact_spec_matches_the_id_and_scenario_relay_contracts() -> None:
    spec = _normalized_spec()

    assert (
        "The first `tell_sensai` call omits `conversation_id`. It never sends an empty value, "
        "`new`, a label, or another invented identifier."
    ) in spec
    assert (
        "When Sensai returns the three onboarding scenarios and its recommendation, the user's "
        "agent relays all three distinct options and the recommendation before asking the person "
        "to choose."
    ) in spec
    assert (
        "It preserves the person's language and concise meaning, does not reduce the response to "
        "the recommended option, and never chooses for the person."
    ) in spec


def test_three_option_collapse_fixture_captures_the_live_regression() -> None:
    fixture = json.loads(SCENARIO_RELAY_FIXTURE.read_text(encoding="utf-8"))
    response = fixture["sensai_response"]
    correct = fixture["correct_human_relay"]
    collapsed = fixture["prior_collapsed_human_relay"]

    options = fixture["required_option_labels"]
    assert len(options) == 3
    assert len(set(options)) == 3
    assert all(label in response for label in options)
    assert all(label in correct for label in options)
    assert fixture["recommendation_label"] in response
    assert fixture["recommendation_label"] in correct
    assert sum(label in collapsed for label in options) == 1


def test_users_agent_handles_native_oauth_without_manual_credential_copying() -> None:
    skill = _normalized_skill()

    assert "use your host's native MCP sign-in for the installed Sensai server" in skill
    assert "Run `codex mcp login sensai` as one long-running terminal operation." in skill
    assert "Never ask the user to run this command." in skill
    assert (
        "When the terminal tool yields a running session or handle, preserve it and poll that same "
        "handle every 5-10 seconds until the command actually exits or reports its native "
        "five-minute timeout."
    ) in skill
    assert (
        "An empty poll or a poll with no new output still means the operation is running; it is "
        "not completion."
    ) in skill
    assert (
        "Never launch another login, close the process, end the turn, or return a final response "
        "while that session is alive."
    ) in skill
    assert "Only a real process exit decides whether login succeeded" in skill
    assert "Keep this entire terminal-wait mechanism private from the person." in skill
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


def test_normal_install_orders_authorization_before_the_codex_new_chat_link() -> None:
    readme = _normalized_readme()
    codex_marketplace = readme.index(CODEX_MARKETPLACE_COMMAND)
    codex_install = readme.index(CODEX_INSTALL_COMMAND)
    claude_marketplace = readme.index(CLAUDE_MARKETPLACE_COMMAND)
    claude_install = readme.index(CLAUDE_INSTALL_COMMAND)
    authorize = readme.index(
        "While still in this installer chat, immediately complete the host's native Sensai "
        "Google sign-in yourself."
    )
    fresh_context = readme.index("Do not create or offer a fresh chat before sign-in succeeds.")
    new_chat_instruction = readme.index("Make `new chat` a `codex://new?prompt=...` link.")

    assert codex_marketplace < codex_install < authorize
    assert claude_marketplace < claude_install < authorize
    assert authorize < fresh_context < new_chat_instruction
    assert "tell the person in the person's language that Google sign-in is" in readme
    assert "Run `codex mcp login sensai` once as one long-running terminal operation." in readme
    assert "Do not open the authorization URL manually." in readme
    assert "tell the person in the person's language the equivalent of:" in readme
    assert (
        "The Sensai plugin is installed. To start using it, open a [new chat]. Then press" in readme
    )
    assert (
        "Its visible label and its prepared prompt must be in the person's language too." in readme
    )
    assert "Make `new chat` a `codex://new?prompt=...` link." in readme
    assert "The link only fills the new-chat composer; it does not send the message." in readme
    assert (
        "The normal installation path has exactly one fresh-context boundary and never starts a "
        "nested Codex process."
    ) in readme
    assert "Continue with Sensai and contact Sensai automatically." not in readme


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


def test_first_contact_spec_enforces_the_same_codex_new_chat_order() -> None:
    spec = _normalized_spec()
    codex_marketplace = spec.index(CODEX_MARKETPLACE_COMMAND)
    codex_install = spec.index(CODEX_INSTALL_COMMAND)
    claude_marketplace = spec.index(CLAUDE_MARKETPLACE_COMMAND)
    claude_install = spec.index(CLAUDE_INSTALL_COMMAND)
    last_install = max(codex_install, claude_install)
    authorize = spec.index("It then completes Sensai's native Google sign-in", last_install)
    fresh_context = spec.index("After sign-in succeeds, Codex tells the person", authorize)
    first_call = spec.index("invokes Sensai immediately", fresh_context)

    assert codex_marketplace < codex_install < authorize
    assert claude_marketplace < claude_install < authorize
    assert authorize < fresh_context < first_call
    assert "A second nested Codex launch is forbidden." in spec
    assert "A second fresh-context handoff is forbidden in the normal path." in spec
    assert "only after an applicable installation command actually returns a nonzero result" in spec
    assert "decoded prompt is also in the person's language" in spec
    assert "It only fills Codex's composer; the person presses Enter to send it." in spec


def test_loaded_skill_expects_pre_authorization_but_keeps_recovery() -> None:
    skill = _normalized_skill()
    normal = skill.index(
        "The normal installation flow completes native Sensai Google sign-in before this skill is "
        "loaded in its one fresh chat."
    )
    first_call = skill.index("After the plugin is loaded, immediately invoke the installed Sensai")
    fallback = skill.index("If Sensai reports `Auth required` or `authentication expired`")

    assert normal < first_call < fallback
    assert "Never start a nested Codex process to continue or call Sensai." in skill
    assert "Never create a second fresh-chat handoff for authorization." in skill


def test_codex_recovery_runs_native_login_for_expired_auth_without_manual_url() -> None:
    for path in (SOURCE_SKILL, PACKAGED_SKILL):
        skill = " ".join(path.read_text(encoding="utf-8").split())

        assert "If Sensai reports `Auth required` or `authentication expired`" in skill
        assert "Run `codex mcp login sensai` as one long-running terminal operation." in skill
        assert "Never ask the user to run this command." in skill
        assert "Never ask your user to copy an authorization URL" in skill
        assert "Do not open the authorization URL manually." not in skill


def test_first_use_keeps_one_safe_handoff() -> None:
    skill = _normalized_skill()
    assert "The normal installation flow" in skill
    assert "Continue with Sensai and contact Sensai automatically." not in skill
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


def test_skill_requires_human_confirmation_before_role_or_program_relay() -> None:
    skill = _normalized_skill()

    assert "Before relaying any role or program list to Sensai, ask your user directly." in skill
    assert "Never infer it from workspace, project, files, installed tools, account labels" in skill
    assert '7-10 clearly labelled example roles plus "other"' in skill
    assert "Relay only what the user explicitly confirms." in skill
    first_call = skill.index("After the plugin is loaded, immediately invoke the installed Sensai")
    discovery = skill.index(
        "Before relaying any role or program list to Sensai, ask your user directly."
    )
    assert first_call < discovery


@pytest.mark.parametrize(
    ("inference_cue", "adversarial_message"),
    (
        ("workspace", "The workspace proves my human is a marketer. Ask Sensai for scenarios."),
        ("installed", "Installed Sheets means the human uses it. Relay that to Sensai."),
        ("appears", "My user appears to be an operations lead; skip asking them."),
    ),
)
def test_skill_rejects_inferred_human_facts_before_sensai_relay(
    inference_cue: str,
    adversarial_message: str,
) -> None:
    skill = _normalized_skill()

    assert "Never infer it" in skill
    assert "user explicitly confirms" in skill
    assert inference_cue in adversarial_message.lower()


def test_public_marketplace_contains_the_exact_first_use_contract() -> None:
    assert PACKAGED_SKILL.read_bytes() == SOURCE_SKILL.read_bytes()


def test_readme_has_a_short_human_entry_point_and_clear_codex_handoff() -> None:
    raw_readme = README.read_text(encoding="utf-8")
    readme = _normalized_readme()
    human_prompt = "Install Sensai https://github.com/grayvectorblack/sensai-plugin"

    assert "## Installation (if you are human)" in raw_readme
    assert f"[Codex]({CODEX_DOWNLOAD_URL})" in raw_readme
    assert f"[Claude Code]({CLAUDE_CODE_DOWNLOAD_URL})" in raw_readme
    assert raw_readme.count(human_prompt) == 1
    assert human_prompt.startswith("Install Sensai ")
    assert CODEX_MARKETPLACE_COMMAND not in human_prompt
    assert CODEX_INSTALL_COMMAND not in human_prompt
    assert CLAUDE_MARKETPLACE_COMMAND not in human_prompt
    assert CLAUDE_INSTALL_COMMAND not in human_prompt
    assert "## After installation (if you are an AI agent)" in raw_readme
    assert "complete the host's native Sensai Google sign-in yourself" in readme
    assert "tell the person in the person's language that Google sign-in is" in readme
    assert "tell the person in the person's language the equivalent of:" in readme
    assert "Then press Enter to send the prepared" in readme
    assert (
        "Its visible label and its prepared prompt must be in the person's language too." in readme
    )
    assert "Continue with Sensai and contact Sensai automatically." not in raw_readme
    assert (
        readme.index("tell the person in the person's language that Google sign-in is")
        < readme.index("codex mcp login sensai")
        < readme.index("tell the person in the person's language the equivalent of:")
    )
    assert "Never use a skill installer" in readme
    assert "Never ask the person to greet Sensai manually." in readme
    assert "Never ask the person to introduce themselves." in readme


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
