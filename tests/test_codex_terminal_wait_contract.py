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

PROTOCOL_SENTENCES = (
    "Run `codex mcp login sensai` as one long-running terminal operation.",
    (
        "When the terminal tool yields a running session or handle, preserve it and poll that "
        "same handle every 5-10 seconds until the command actually exits or reports its native "
        "five-minute timeout."
    ),
    (
        "An empty poll or a poll with no new output still means the operation is running; it is "
        "not completion."
    ),
    (
        "Never launch another login, close the process, end the turn, or return a final response "
        "while that session is alive."
    ),
    ("Only a real process exit decides whether login succeeded or reached its native timeout."),
    "Keep this entire terminal-wait mechanism private from the person.",
)


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_terminal_wait_protocol_is_complete_and_ordered_in_every_agent_contract() -> None:
    for path in (README, SOURCE_SKILL, PACKAGED_SKILL, FIRST_CONTACT_SPEC):
        text = _normalized(path)
        positions = [text.index(sentence) for sentence in PROTOCOL_SENTENCES]

        assert positions == sorted(positions), path
        assert all(text.count(sentence) == 1 for sentence in PROTOCOL_SENTENCES), path


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
