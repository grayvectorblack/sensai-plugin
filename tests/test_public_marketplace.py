from __future__ import annotations

import json
from pathlib import Path

from sensai_plugin.package_builder import build_packages

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


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
