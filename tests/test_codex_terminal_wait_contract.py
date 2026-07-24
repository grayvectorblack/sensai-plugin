from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SOURCE_SKILL = ROOT / "payload-src/shared/skills/sensai/SKILL.md"
PACKAGED_SKILL = ROOT / "plugins/sensai/skills/sensai/SKILL.md"
FIRST_CONTACT_SPEC = ROOT / "docs/specs/FIRST-CONTACT-001.md"
FAILURE_FIXTURE = ROOT / "tests/fixtures/codex_terminal_wait_empty_poll.json"


@dataclass
class _TerminalWaitModel:
    handle: str | None = None
    running: bool = False
    finalization_allowed: bool = False

    def apply(self, event: dict[str, Any]) -> None:
        event_type = event["type"]
        if event_type == "started":
            self.handle = str(event["handle"])
            self.running = True
            return
        if event_type == "poll":
            assert event["handle"] == self.handle
            if bool(event["exited"]):
                self.running = False
            return
        if event_type == "attempt_finalize":
            self.finalization_allowed = not self.running
            return
        raise AssertionError(f"unknown fixture event: {event_type}")


def test_one_empty_thirty_second_poll_cannot_finalize_a_live_login() -> None:
    fixture = json.loads(FAILURE_FIXTURE.read_text(encoding="utf-8"))
    model = _TerminalWaitModel()

    for event in fixture["events"]:
        model.apply(event)

    assert model.handle == fixture["expected"]["handle"]
    assert model.running is fixture["expected"]["still_running"]
    assert model.finalization_allowed is fixture["expected"]["finalization_allowed"]
