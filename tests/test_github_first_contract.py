from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
FIRST_CONTACT_SPEC = ROOT / "docs/specs/FIRST-CONTACT-001.md"
CODEX_MARKETPLACE_COMMAND = "codex plugin marketplace add grayvectorblack/sensai-plugin"
CODEX_INSTALL_COMMAND = "codex plugin add sensai@sensai"
CLAUDE_MARKETPLACE_COMMAND = "claude plugin marketplace add grayvectorblack/sensai-plugin"
CLAUDE_INSTALL_COMMAND = "claude plugin install sensai@sensai --scope user"


def _text_files() -> list[Path]:
    files = [ROOT / "README.md"]
    for relative in ("docs", "payload-src", "plugins", "scripts", "src"):
        files.extend(path for path in (ROOT / relative).rglob("*") if path.is_file())
    return files


def test_public_readme_has_the_short_install_prompt_and_documented_codex_handoff() -> None:
    readme = README.read_text(encoding="utf-8")
    normalized = " ".join(readme.split())

    assert "Install Sensai https://github.com/grayvectorblack/sensai-plugin" in readme
    assert "[Codex](https://chatgpt.com/download/)" in readme
    assert "[Claude Code](https://claude.ai/download)" in readme
    assert "tell the person in the person's language that Google sign-in is needed" in normalized
    assert "The link only fills the new-chat composer; it does not send the message." in normalized
    assert "Continue with Sensai and contact Sensai automatically." not in readme
    assert (
        "That loaded context must contact Sensai immediately with authorization already present."
        in normalized
    )
    assert "Install Sensai only through the host's native plugin installation system." in normalized
    assert "Never use a skill installer or copy an internal plugin directory by hand." in normalized
    assert "Do not invent a fallback installation." in normalized
    assert normalized.count(CODEX_MARKETPLACE_COMMAND) == 1
    assert normalized.count(CODEX_INSTALL_COMMAND) == 1
    assert normalized.count(CLAUDE_MARKETPLACE_COMMAND) == 1
    assert normalized.count(CLAUDE_INSTALL_COMMAND) == 1
    assert normalized.index(CODEX_MARKETPLACE_COMMAND) < normalized.index(CODEX_INSTALL_COMMAND)
    assert normalized.index(CLAUDE_MARKETPLACE_COMMAND) < normalized.index(CLAUDE_INSTALL_COMMAND)
    assert (
        "Run the commands for the current host instead of inferring that native installation is "
        "unsupported." in normalized
    )
    assert (
        "Only infer or report that native installation is unsupported, or say that Sensai could "
        "not be installed, after one of the applicable commands actually exits with a nonzero "
        "status." in normalized
    )
    assert (
        "Keep the commands, exit status, marketplace, and other installation mechanics private "
        "from the person." in normalized
    )
    assert (
        "While still in this installer chat, immediately complete the host's native Sensai Google "
        "sign-in yourself." in normalized
    )
    assert normalized.index(
        "tell the person in the person's language that Google sign-in is needed"
    ) < normalized.index("codex mcp login sensai")
    assert "Run `codex mcp login sensai` once as one long-running terminal operation." in normalized
    assert "Do not open the authorization URL manually." in normalized
    assert normalized.index(
        "Do not create or offer a fresh chat before sign-in succeeds."
    ) < normalized.index("tell the person in the person's language the equivalent of:")
    assert "Never ask the person to greet Sensai manually." in normalized
    assert "Never ask the person to introduce themselves." in normalized
    assert "A brief ordinary-language progress acknowledgement is allowed." in normalized
    assert (
        "Do not include MCP, commands, paths, a plugin version, or transport details in that "
        "sentence or in a status update."
    ) in normalized
    assert (
        "Never show the person the plugin manager, internal repository paths, a plugin version, "
        "MCP or transport details, or installation commands."
    ) in normalized
    assert "Keep every progress update free of technical details." in normalized
    assert "Public source:" not in readme
    assert "Privacy:" not in readme
    assert "## MCP authorization" not in readme
    assert "## Development" not in readme
    assert "black-vector.com/sensai/invite" not in readme
    assert "one-time code" not in readme.lower()
    assert "bootstrap" not in readme.lower()
    assert "powershell" not in readme.lower()

    assert "Make `new chat` a `codex://new?prompt=...` link." in readme
    assert (
        "Its visible label and its prepared prompt must be in the person's language too."
        in normalized
    )


def test_first_contact_spec_matches_the_public_codex_handoff() -> None:
    spec = FIRST_CONTACT_SPEC.read_text(encoding="utf-8")
    normalized = " ".join(spec.split())

    assert "> Install Sensai https://github.com/grayvectorblack/sensai-plugin" in spec
    assert "offers a clickable `new chat` link in that language" in normalized
    assert "decoded prompt is also in the person's language" in normalized
    assert "It only fills Codex's composer; the person presses Enter to send it." in normalized
    assert "Continue with Sensai and contact Sensai automatically." not in spec
    for command in (
        CODEX_MARKETPLACE_COMMAND,
        CODEX_INSTALL_COMMAND,
        CLAUDE_MARKETPLACE_COMMAND,
        CLAUDE_INSTALL_COMMAND,
    ):
        assert normalized.count(command) == 1
    assert normalized.index(CODEX_MARKETPLACE_COMMAND) < normalized.index(CODEX_INSTALL_COMMAND)
    assert normalized.index(CLAUDE_MARKETPLACE_COMMAND) < normalized.index(CLAUDE_INSTALL_COMMAND)
    assert (
        "only after an applicable installation command actually returns a nonzero result"
        in normalized
    )
    assert normalized.index(
        "tells the person in the person's language that Google sign-in is needed"
    ) < normalized.index("After sign-in succeeds, Codex tells the person")
    assert (
        "runs `codex mcp login sensai` once and never opens the authorization URL manually"
        in normalized
    )


def test_public_repository_exposes_native_codex_and_claude_marketplaces() -> None:
    codex = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    claude = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))

    assert codex["plugins"][0]["source"] == {
        "source": "local",
        "path": "./plugins/sensai",
    }
    assert claude["owner"] == {
        "name": "Black Vector",
        "email": "sergey@black-vector.com",
    }
    assert claude["plugins"][0]["source"] == "./plugins/sensai"
    plugin = ROOT / "plugins/sensai"
    assert (plugin / ".codex-plugin/plugin.json").is_file()
    assert (plugin / ".claude-plugin/plugin.json").is_file()


def test_remote_mcp_uses_native_oauth_discovery_without_static_credentials() -> None:
    expected = {
        "mcpServers": {
            "sensai": {
                "type": "http",
                "url": "https://black-vector.com/sensai/mcp",
            }
        }
    }
    source = json.loads((ROOT / "payload-src/shared/.mcp.json").read_text(encoding="utf-8"))
    public = json.loads((ROOT / "plugins/sensai/.mcp.json").read_text(encoding="utf-8"))

    assert source == expected
    assert public == expected


def test_public_plugin_contains_no_server_supplied_executable_package_path() -> None:
    forbidden_names = {"package_runner.py", "install-sensai.ps1"}
    forbidden_phrases = (
        "curated implementation package",
        "ready package",
        "package_runner",
        "trusted_package_digests",
    )

    public_and_build_files = _text_files()
    assert not any(path.name in forbidden_names for path in public_and_build_files)
    for path in public_and_build_files:
        if path == Path(__file__):
            continue
        try:
            content = path.read_text(encoding="utf-8").lower()
        except (UnicodeDecodeError, OSError):
            continue
        assert not any(phrase in content for phrase in forbidden_phrases), path


def test_skill_assigns_all_local_implementation_to_the_users_agent() -> None:
    skill = (ROOT / "payload-src/shared/skills/sensai/SKILL.md").read_text(encoding="utf-8")
    normalized = " ".join(skill.split())

    assert (
        "Sensai provides advice, detailed implementation instructions, architecture, and optional "
        "non-executed reference snippets."
    ) in normalized
    assert (
        "Write, review, install dependencies for, run, and verify all code locally through your "
        "platform's normal controls."
    ) in normalized
