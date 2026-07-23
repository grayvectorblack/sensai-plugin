from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIRST_CONTACT_SPEC = ROOT / "docs/specs/FIRST-CONTACT-001.md"
INSTALL_REQUEST = (
    "Open https://github.com/grayvectorblack/sensai-plugin, follow its installation instructions "
    "without technical details, complete Google sign-in, and continue automatically; only after "
    "sign-in, if a new chat is required, give me exactly this copyable sentence: Continue with "
    "Sensai and contact Sensai automatically."
)
INSTALL_URL = "https://github.com/grayvectorblack/sensai-plugin"
CONTINUATION = "Continue with Sensai and contact Sensai automatically."


def _text_files() -> list[Path]:
    files = [ROOT / "README.md"]
    for relative in ("docs", "payload-src", "plugins", "scripts", "src"):
        files.extend(path for path in (ROOT / relative).rglob("*") if path.is_file())
    return files


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


def test_readme_has_one_github_first_install_request() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())
    continuation = CONTINUATION

    assert readme.count(INSTALL_REQUEST) == 1
    assert INSTALL_REQUEST.startswith("Open ")
    assert ", follow " in INSTALL_REQUEST
    assert not INSTALL_REQUEST.startswith("Install ")
    assert "Install the Sensai plugin" not in INSTALL_REQUEST
    assert _sentence_count(INSTALL_REQUEST) == 1
    _assert_pre_authorized_human_request(INSTALL_REQUEST)
    assert "follow its installation instructions without technical details" in INSTALL_REQUEST
    assert "complete Google sign-in" in INSTALL_REQUEST
    assert "continue automatically" in INSTALL_REQUEST
    assert (
        "only after sign-in, if a new chat is required, give me exactly this copyable sentence: "
        f"{continuation}" in INSTALL_REQUEST
    )
    assert "## Installation (human)" in readme
    assert "This is the person's only action:" in readme
    assert "## After installation (AI agent)" in readme
    assert "without waiting for another human command" in normalized.casefold()
    assert (
        "That fresh chat must contact Sensai immediately with authorization already present."
        in normalized
    )
    assert "Install Sensai only through the host's native plugin installation system." in normalized
    assert "Never use a skill installer" in normalized
    assert "Do not copy an internal plugin directory by hand." in normalized
    assert (
        "If native plugin installation is unavailable, tell the person plainly that Sensai could "
        "not be installed and stop."
    ) in normalized
    assert "Do not invent a fallback installation." in normalized
    assert (
        "While still in this installer chat, immediately complete the host's native Sensai Google "
        "sign-in yourself." in normalized
    )
    assert (
        "If the host can create that fresh context itself, create it and continue there "
        "automatically."
    ) in normalized
    assert (
        "Only if the platform truly requires the person to start it, offer exactly the "
        "copyable continuation sentence already provided in the human request and nothing else."
    ) in normalized
    assert normalized.index(
        "Do not create, offer, or start the fresh chat before sign-in succeeds."
    ) < normalized.index("offer exactly the copyable continuation sentence")
    assert normalized.count(continuation) == 1
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
    assert "### Codex" not in readme
    assert "### Claude Code" not in readme
    assert "## MCP authorization" not in readme
    assert "## Development" not in readme
    assert "black-vector.com/sensai/invite" not in readme
    assert "one-time code" not in readme.lower()
    assert "bootstrap" not in readme.lower()
    assert "powershell" not in readme.lower()


def test_first_contact_spec_uses_the_same_one_sentence_human_request() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    spec = FIRST_CONTACT_SPEC.read_text(encoding="utf-8")

    assert readme.count(INSTALL_REQUEST) == 1
    assert spec.count(INSTALL_REQUEST) == 1
    assert _sentence_count(INSTALL_REQUEST) == 1
    _assert_pre_authorized_human_request(INSTALL_REQUEST)
    assert "follow its installation instructions without technical details" in INSTALL_REQUEST
    assert "complete Google sign-in" in INSTALL_REQUEST
    assert "continue automatically" in INSTALL_REQUEST
    assert (
        "only after sign-in, if a new chat is required, give me exactly this copyable sentence: "
        "Continue with Sensai and contact Sensai automatically." in INSTALL_REQUEST
    )
    normalized_spec = " ".join(spec.split())
    assert (
        "The continuation must never be emitted before Google sign-in has confirmed success."
        in normalized_spec
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
