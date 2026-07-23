from __future__ import annotations

import json
from pathlib import Path

from sensai_plugin.package_builder import build_packages

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SOURCE_URL = "https://github.com/grayvectorblack/sensai-plugin"


def _regular_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_public_repository_is_a_ready_codex_marketplace(tmp_path: Path) -> None:
    marketplace_path = REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

    assert marketplace == {
        "name": "sensai",
        "interface": {"displayName": "Sensai"},
        "plugins": [
            {
                "name": "sensai",
                "source": {"source": "local", "path": "./plugins/sensai"},
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
        ],
    }

    claude_marketplace = json.loads(
        (REPOSITORY_ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
    )
    assert claude_marketplace == {
        "name": "sensai",
        "owner": {"name": "Black Vector", "email": "sergey@black-vector.com"},
        "description": "Sensai guidance for AI agents.",
        "plugins": [
            {
                "name": "sensai",
                "source": "./plugins/sensai",
                "description": "Practical guidance for an AI agent.",
                "version": "0.2.0",
                "category": "productivity",
            }
        ],
    }

    built = build_packages(
        source_root=REPOSITORY_ROOT / "payload-src",
        output_root=tmp_path / "packages",
    )
    committed = REPOSITORY_ROOT / "plugins" / "sensai"
    committed_files = _regular_files(committed)
    codex_files = _regular_files(built.codex)
    claude_files = _regular_files(built.claude)

    assert committed_files[".codex-plugin/plugin.json"] == codex_files[".codex-plugin/plugin.json"]
    assert (
        committed_files[".claude-plugin/plugin.json"] == claude_files[".claude-plugin/plugin.json"]
    )
    for shared in (".mcp.json", "skills/sensai/SKILL.md"):
        assert committed_files[shared] == codex_files[shared] == claude_files[shared]
    assert set(committed_files) == {
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        ".mcp.json",
        "MANIFEST.sha256",
        "skills/sensai/SKILL.md",
    }


def test_skill_requires_first_call_omission_and_later_conversation_id_continuity() -> None:
    source_skill = REPOSITORY_ROOT / "payload-src" / "shared" / "skills" / "sensai" / "SKILL.md"
    packaged_skill = REPOSITORY_ROOT / "plugins" / "sensai" / "skills" / "sensai" / "SKILL.md"
    first_call_rule = (
        "On the first `tell_sensai` call, omit `conversation_id` entirely. Never send a "
        "placeholder such as `new`, an empty string, a label, or an invented ID."
    )
    later_call_rule = (
        "Only after the first successful call returns a `conversation_id`, retain that exact UUID "
        "and pass it on later calls in the same user conversation."
    )

    normalized_skill = " ".join(source_skill.read_text(encoding="utf-8").split())
    assert first_call_rule in normalized_skill
    assert later_call_rule in normalized_skill
    assert packaged_skill.read_bytes() == source_skill.read_bytes()


def test_both_platform_manifests_expose_the_public_source_repository(tmp_path: Path) -> None:
    built = build_packages(
        source_root=REPOSITORY_ROOT / "payload-src",
        output_root=tmp_path / "packages",
    )

    codex_manifest = json.loads(
        (built.codex / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    claude_manifest = json.loads(
        (built.claude / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    assert codex_manifest["repository"] == PUBLIC_SOURCE_URL
    assert claude_manifest["repository"] == PUBLIC_SOURCE_URL
    assert codex_manifest["homepage"] == PUBLIC_SOURCE_URL
    assert claude_manifest["homepage"] == PUBLIC_SOURCE_URL


def test_public_metadata_states_the_advisory_product_boundary(tmp_path: Path) -> None:
    built = build_packages(
        source_root=REPOSITORY_ROOT / "payload-src",
        output_root=tmp_path / "packages",
    )
    codex_manifest = json.loads(
        (built.codex / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    claude_manifest = json.loads(
        (built.claude / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )

    expected = (
        "Advises an AI agent with installation guidance, problem-solving help, and transparent "
        "reference material."
    )
    assert codex_manifest["description"] == expected
    assert claude_manifest["description"] == expected
    assert "connects external services" not in json.dumps(codex_manifest).lower()
    assert "acts in user accounts" not in json.dumps(claude_manifest).lower()


def test_skill_assigns_connector_setup_to_the_users_local_agent() -> None:
    source_skill = REPOSITORY_ROOT / "payload-src/shared/skills/sensai/SKILL.md"
    packaged_skill = REPOSITORY_ROOT / "plugins/sensai/skills/sensai/SKILL.md"
    normalized = " ".join(source_skill.read_text(encoding="utf-8").split())

    assert "Set up external connectors yourself, following Sensai's guidance." in normalized
    assert (
        "Sensai does not perform local steps or act in your user's external accounts." in normalized
    )
    assert "Perform every step you can automate." in normalized
    assert packaged_skill.read_bytes() == source_skill.read_bytes()
