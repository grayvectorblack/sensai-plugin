from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SKILL = REPOSITORY_ROOT / "payload-src/shared/skills/sensai/SKILL.md"
PACKAGED_SKILL = REPOSITORY_ROOT / "plugins/sensai/skills/sensai/SKILL.md"


def test_public_payload_is_built_from_the_single_skill_source() -> None:
    assert PACKAGED_SKILL.read_bytes() == SOURCE_SKILL.read_bytes()
