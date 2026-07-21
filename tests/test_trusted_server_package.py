from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

import pytest

from sensai_plugin import package_runner

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SERVER_ROOT = PLUGIN_ROOT.parent / "server"
PACKAGE_ROOT = SERVER_ROOT / "src" / "sensai" / "workflows" / "marketing_csv_weekly_report"
PACKAGE_ID = "marketing-csv-weekly-report"
EXPECTED_OUTPUT = "weekly-marketing-report.md"


def _descriptor(name: str, content: str) -> dict[str, object]:
    encoded = content.encode("utf-8")
    return {
        "name": name,
        "content": content,
        "byte_length": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _real_payload() -> dict[str, object]:
    manifest = json.loads((PACKAGE_ROOT / "manifest.json").read_text(encoding="utf-8"))
    records = [
        _descriptor(name, (PACKAGE_ROOT / name).read_text(encoding="utf-8"))
        for name in manifest["files"]
    ]
    return {
        "package": {
            "id": manifest["id"],
            "manifest": manifest,
            "files": records,
        }
    }


def _package(payload: dict[str, object]) -> dict[str, Any]:
    package = payload["package"]
    assert isinstance(package, dict)
    return package


def test_server_manifest_declares_one_exact_generated_output() -> None:
    payload = _real_payload()
    manifest = _package(payload)["manifest"]
    assert isinstance(manifest, dict)

    assert manifest["generated_outputs"] == [EXPECTED_OUTPUT]


def test_runner_embeds_exact_canonical_digest_for_real_server_package() -> None:
    payload = _real_payload()
    digest = package_runner.canonical_package_digest(payload)

    assert {PACKAGE_ID: digest} == package_runner.TRUSTED_PACKAGE_DIGESTS
    assert len(digest) == 64
    assert digest == digest.lower()

    distributed = (
        PLUGIN_ROOT / "plugins" / "sensai" / "skills" / "sensai" / "scripts" / "package_runner.py"
    ).read_text(encoding="utf-8")
    assert digest in distributed


def test_real_server_payload_runs_then_verifies_through_distributed_runner(
    tmp_path: Path,
) -> None:
    runner = (
        PLUGIN_ROOT / "plugins" / "sensai" / "skills" / "sensai" / "scripts" / "package_runner.py"
    )
    result = subprocess.run(
        [sys.executable, str(runner), "--workspace", str(tmp_path)],
        input=json.dumps(_real_payload()),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    response = json.loads(result.stdout)
    assert response == {
        "generated_outputs": [EXPECTED_OUTPUT],
        "package_id": PACKAGE_ID,
        "run_passed": True,
        "stage": "completed",
        "status": "completed",
        "summary": "Package ran and was independently verified; 1 declared output is ready.",
        "verification_passed": True,
    }
    report = tmp_path / ".sensai" / "automations" / PACKAGE_ID / EXPECTED_OUTPUT
    assert report.is_file()
    assert "# Weekly Marketing Report" in report.read_text(encoding="utf-8")


@pytest.mark.parametrize("damage", ["unknown_id", "modified_file"])
def test_unknown_or_modified_package_never_writes_or_executes(
    tmp_path: Path,
    damage: str,
) -> None:
    payload = _real_payload()
    package = _package(payload)
    if damage == "unknown_id":
        package["id"] = "unknown-package"
        manifest = package["manifest"]
        assert isinstance(manifest, dict)
        manifest["id"] = "unknown-package"
    else:
        records = package["files"]
        assert isinstance(records, list)
        record = next(item for item in records if item["name"] == "report.py")
        record["content"] += "\nraise RuntimeError('must not execute')\n"
        encoded = record["content"].encode("utf-8")
        record["byte_length"] = len(encoded)
        record["sha256"] = hashlib.sha256(encoded).hexdigest()

    result = package_runner.run_package(payload, tmp_path)

    assert result.status == "failed"
    assert result.stage == "validation"
    assert not (tmp_path / ".sensai").exists()


def test_untrusted_outside_write_attempt_never_executes(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    manifest = {
        "id": "untrusted-package",
        "objective": "Must never run.",
        "files": ["manifest.json", "report.py", "sample.csv", "verify.py"],
        "entrypoint": "report.py",
        "verifier": "verify.py",
        "sample_input": "sample.csv",
        "generated_outputs": ["report.md"],
        "run_command": ["{python}", "{entrypoint}", "--output", "{output}"],
        "verification_command": ["{python}", "{verifier}", "--report", "{output}"],
    }
    contents = {
        "manifest.json": json.dumps(manifest, sort_keys=True),
        "report.py": (
            "from pathlib import Path\n"
            f"Path({str(outside)!r}).write_text('executed', encoding='utf-8')\n"
        ),
        "sample.csv": "campaign,spend,clicks,conversions\nA,1,1,1\n",
        "verify.py": "raise SystemExit(0)\n",
    }
    payload = {
        "package": {
            "id": manifest["id"],
            "manifest": manifest,
            "files": [_descriptor(name, contents[name]) for name in manifest["files"]],
        }
    }

    result = package_runner.run_package(payload, tmp_path)

    assert result.status == "failed"
    assert result.stage == "validation"
    assert not outside.exists()
    assert not (tmp_path / ".sensai").exists()


def test_failure_removes_entire_transaction_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = package_runner._run_command

    def fail_after_surprise(
        command: Sequence[str],
        *,
        package_directory: Path,
        timeout_seconds: float,
        stage: Literal["verification", "run"],
    ) -> None:
        (package_directory / "surprise.txt").write_text("unexpected", encoding="utf-8")
        original(
            command,
            package_directory=package_directory,
            timeout_seconds=timeout_seconds,
            stage=stage,
        )
        raise package_runner._RunnerError("run", "Forced transaction failure.")

    monkeypatch.setattr(package_runner, "_run_command", fail_after_surprise)
    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")

    result = package_runner.run_package(_real_payload(), tmp_path)

    assert result.status == "failed"
    assert not (tmp_path / ".sensai" / "automations" / PACKAGE_ID).exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_malformed_csv_fails_cleanly_without_report(tmp_path: Path) -> None:
    malformed = tmp_path / "bad.csv"
    malformed.write_text("campaign,spend,clicks\nA,10,2\n", encoding="utf-8")
    report = tmp_path / "must-not-exist.md"

    result = subprocess.run(
        [
            sys.executable,
            str(PACKAGE_ROOT / "report.py"),
            "--input",
            str(malformed),
            "--output",
            str(report),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode != 0
    assert not report.exists()
    assert "traceback" not in f"{result.stdout}\n{result.stderr}".casefold()
