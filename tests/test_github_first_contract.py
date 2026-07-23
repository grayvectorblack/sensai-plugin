from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_REQUEST = "Install Sensai from https://github.com/grayvectorblack/sensai-plugin"


def _text_files() -> list[Path]:
    files = [ROOT / "README.md"]
    for relative in ("docs", "payload-src", "plugins", "scripts", "src"):
        files.extend(path for path in (ROOT / relative).rglob("*") if path.is_file())
    return files


def test_readme_has_one_github_first_install_request() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    normalized = " ".join(readme.split())

    assert readme.count(INSTALL_REQUEST) == 1
    assert "## Installation (human)" in readme
    assert "This is the person's only action:" in readme
    assert "## After installation (AI agent)" in readme
    assert "without waiting for another human command" in normalized.casefold()
    assert "brief, natural greeting through the installed Sensai MCP" in normalized
    assert "starts native sign-in if needed and returns the next instruction" in normalized
    assert "If loading the plugin requires a new chat" in readme
    assert readme.count(
        "Sensai is already installed; use the Sensai plugin, connect through its configured MCP, "
        "and send Sensai a brief natural greeting."
    ) == 1
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
