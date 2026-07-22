from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_REQUEST = "Установи Sensai https://github.com/grayvectorblack/sensai-plugin"


def _text_files() -> list[Path]:
    files = [ROOT / "README.md"]
    for relative in ("docs", "payload-src", "plugins", "scripts", "src"):
        files.extend(path for path in (ROOT / relative).rglob("*") if path.is_file())
    return files


def test_readme_has_one_github_first_install_request() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert readme.count(INSTALL_REQUEST) == 1
    assert "black-vector.com/sensai/invite" not in readme
    assert "one-time code" not in readme.lower()
    assert "bootstrap" not in readme.lower()
    assert "powershell" not in readme.lower()


def test_public_repository_exposes_native_codex_and_claude_marketplaces() -> None:
    codex = json.loads(
        (ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8")
    )
    claude = json.loads(
        (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )

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
        "готовый пакет",
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
        "Write, review, install dependencies for, run, and verify all code locally as the user's "
        "AI agent through the platform's normal controls."
    ) in normalized
