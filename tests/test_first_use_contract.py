from __future__ import annotations

import shlex
import subprocess
import sys
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
    assert "Native OAuth may pause this first call" in skill


def test_users_agent_handles_native_oauth_without_manual_credential_copying() -> None:
    skill = _normalized_skill()

    assert "use your host's native MCP sign-in for the installed Sensai server" in skill
    assert "complete only the browser login and consent screen" in skill
    assert "then retry the same greeting" in skill
    assert (
        "Never ask your user to copy an authorization URL, code, or credential into chat or local "
        "configuration."
    ) in skill


def test_first_use_requires_no_second_human_command() -> None:
    skill = _normalized_skill()

    assert "Do not use a fixed setup phrase" in skill
    assert "require your user to type another command" in skill


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
    assert "never claims the current task hot-loaded the plugin" in readme
    assert "opening one fresh task is the only remaining action" in readme
    assert "restarting Claude Code is the only remaining action" in readme


def test_readme_does_not_start_with_a_marketing_routine() -> None:
    readme = README.read_text(encoding="utf-8")

    assert "I work in marketing" not in readme
    assert "Help me choose one routine" not in readme


def test_readme_has_a_short_precise_privacy_boundary() -> None:
    readme = README.read_text(encoding="utf-8")
    introduction = " ".join(readme[:1600].replace("> ", "").split())

    assert (
        "Sensai receives only text that the user's AI agent explicitly sends to it." in introduction
    )
    assert "Sensai does not connect to external accounts or run code" in introduction
    assert "https://github.com/grayvectorblack/sensai-plugin" in introduction
    assert "Connector setup also happens locally." in introduction
    assert "The person completes any authorization or consent screen." in introduction


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


def test_documented_release_build_command_matches_and_executes_the_cli(tmp_path: Path) -> None:
    readme = README.read_text(encoding="utf-8")
    command_line = next(
        line
        for line in readme.splitlines()
        if line.startswith("uv run python scripts/build_release.py ")
    )
    documented = shlex.split(command_line)

    assert documented[:4] == ["uv", "run", "python", "scripts/build_release.py"]
    assert documented[4:] == [
        "--output",
        "/path/to/release",
        "--mcp-url",
        "https://black-vector.com/sensai/mcp",
    ]

    output = tmp_path / "release"
    arguments = documented[4:]
    arguments[arguments.index("/path/to/release")] = str(output)
    subprocess.run(
        [sys.executable, str(REPOSITORY_ROOT / documented[3]), *arguments],
        cwd=REPOSITORY_ROOT,
        check=True,
    )
    assert (output / "release.json").is_file()


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
