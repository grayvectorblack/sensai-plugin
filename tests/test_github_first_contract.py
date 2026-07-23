from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
FIRST_CONTACT_SPEC = ROOT / "docs/specs/FIRST-CONTACT-001.md"
CODEX_NEW_CHAT_PROMPT = (
    "[@Sensai](plugin://sensai@sensai) Start Sensai. Introduce yourself briefly, then ask the "
    "human for their role and the five main programs or sites they use at work."
)


def test_public_readme_has_the_short_install_prompt_and_documented_codex_handoff() -> None:
    readme = README.read_text(encoding="utf-8")
    normalized = " ".join(readme.split())

    assert "Install Sensai https://github.com/grayvectorblack/sensai-plugin" in readme
    assert "[Codex](https://chatgpt.com/download/)" in readme
    assert "[Claude Code](https://claude.ai/download)" in readme
    assert "Google sign-in is needed to connect Sensai to this Codex session." in normalized
    assert "The link only fills the new-chat composer; it does not send the message." in normalized
    assert "Continue with Sensai and contact Sensai automatically." not in readme

    link_start = readme.index("[new chat](") + len("[new chat](")
    link_end = readme.index(")", link_start)
    link = readme[link_start:link_end]
    parsed = urlparse(link)
    assert parsed.scheme == "codex"
    assert parsed.netloc == "new"
    assert parse_qs(parsed.query) == {"prompt": [CODEX_NEW_CHAT_PROMPT]}


def test_first_contact_spec_matches_the_public_codex_handoff() -> None:
    spec = FIRST_CONTACT_SPEC.read_text(encoding="utf-8")
    normalized = " ".join(spec.split())

    assert "> Install Sensai https://github.com/grayvectorblack/sensai-plugin" in spec
    assert CODEX_NEW_CHAT_PROMPT in normalized
    assert "It only fills Codex's composer; the person presses Enter to send it." in normalized
    assert "Continue with Sensai and contact Sensai automatically." not in spec


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
