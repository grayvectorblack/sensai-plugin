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

    built = build_packages(
        source_root=REPOSITORY_ROOT / "payload-src",
        output_root=tmp_path / "packages",
    )
    committed = REPOSITORY_ROOT / "plugins" / "sensai"

    assert _regular_files(committed) == _regular_files(built.codex)


def test_skill_requires_conversation_id_continuity() -> None:
    source_skill = REPOSITORY_ROOT / "payload-src" / "shared" / "skills" / "sensai" / "SKILL.md"
    packaged_skill = REPOSITORY_ROOT / "plugins" / "sensai" / "skills" / "sensai" / "SKILL.md"
    required_rule = (
        "Retain the `conversation_id` returned by `tell_sensai` for the current user conversation "
        "and pass it on every subsequent `tell_sensai` call. Never invent an ID or reuse one "
        "across unrelated conversations."
    )

    normalized_skill = " ".join(source_skill.read_text(encoding="utf-8").split())
    assert required_rule in normalized_skill
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
    assert codex_manifest["homepage"] == "https://black-vector.com/"
    assert claude_manifest["homepage"] == "https://black-vector.com/"


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

    assert "Set up external connectors locally as the user's AI agent" in normalized
    assert "Sensai never connects to or acts in the user's external accounts." in normalized
    assert "Ask the person to handle any required authorization or consent." in normalized
    assert packaged_skill.read_bytes() == source_skill.read_bytes()
