from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from sensai_plugin import package_runner
from sensai_plugin.package_runner import (
    MAX_FILE_BYTES,
    MAX_PACKAGE_BYTES,
    PackageInspection,
    PackageRunResult,
    inspect_package,
    run_package,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_RUNNER = REPOSITORY_ROOT / "src/sensai_plugin/package_runner.py"
PAYLOAD_RUNNER = REPOSITORY_ROOT / "payload-src/shared/skills/sensai/scripts/package_runner.py"
PACKAGED_RUNNER = REPOSITORY_ROOT / "plugins/sensai/skills/sensai/scripts/package_runner.py"

VERIFY_SOURCE = """\
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--report", required=True)
args = parser.parse_args()
if not Path(args.input).is_file():
    raise SystemExit(2)
if Path(args.report).read_text(encoding="utf-8") != "ran\\n":
    raise SystemExit(3)
print("verification details must not be returned")
"""

RUN_SOURCE = """\
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
output = Path(args.output)
output.write_text("ran\\n", encoding="utf-8")
print("run details must not be returned")
"""


@pytest.fixture(autouse=True)
def _isolated_test_trust(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        package_runner,
        "TRUSTED_PACKAGE_DIGESTS",
        dict(package_runner.TRUSTED_PACKAGE_DIGESTS),
    )


def _descriptor(name: str, content: str) -> dict[str, object]:
    encoded = content.encode("utf-8")
    return {
        "name": name,
        "content": content,
        "byte_length": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }


def _payload(
    *,
    package_id: str = "marketing-report",
    manifest_updates: dict[str, object] | None = None,
    content_updates: dict[str, str] | None = None,
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "id": package_id,
        "objective": "Create a local weekly marketing report.",
        "files": ["manifest.json", "report.py", "sample.csv", "verify.py"],
        "entrypoint": "report.py",
        "verifier": "verify.py",
        "sample_input": "sample.csv",
        "generated_outputs": ["report.md"],
        "verification_command": [
            "{python}",
            "{verifier}",
            "--input",
            "{input}",
            "--report",
            "{output}",
        ],
        "run_command": [
            "{python}",
            "{entrypoint}",
            "--input",
            "{input}",
            "--output",
            "{output}",
        ],
    }
    if manifest_updates:
        manifest.update(manifest_updates)
    contents = {
        "report.py": RUN_SOURCE,
        "sample.csv": "campaign,spend\\nAlpha,10\\n",
        "verify.py": VERIFY_SOURCE,
    }
    if content_updates:
        contents.update(content_updates)
    contents["manifest.json"] = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    payload: dict[str, object] = {
        "package": {
            "id": package_id,
            "manifest": manifest,
            "files": [_descriptor(name, contents[name]) for name in sorted(contents)],
        }
    }
    package_runner.TRUSTED_PACKAGE_DIGESTS[package_id] = package_runner.canonical_package_digest(
        payload
    )
    return payload


def _standalone_runner_trusting(payload: dict[str, object]) -> str:
    package = payload["package"]
    assert isinstance(package, dict)
    package_id = package["id"]
    assert isinstance(package_id, str)
    digest = package_runner.canonical_package_digest(payload)
    source = SOURCE_RUNNER.read_text(encoding="utf-8")
    return re.sub(
        r"TRUSTED_PACKAGE_DIGESTS = \{\n"
        r'    "marketing-csv-weekly-report": \(\n'
        r'        "[0-9a-f]{64}"\n'
        r"    \),\n"
        r"\}",
        (f'TRUSTED_PACKAGE_DIGESTS = {{\n    "{package_id}": (\n        "{digest}"\n    ),\n}}'),
        source,
        count=1,
    )


def _assert_failed_without_package(result: PackageRunResult, workspace: Path) -> None:
    assert result.status == "failed"
    assert result.summary
    assert not (workspace / ".sensai" / "automations" / "marketing-report").exists()
    serialized = json.dumps(result.to_dict())
    assert "verification details" not in serialized
    assert "run details" not in serialized


def test_runner_runs_then_verifies_and_returns_only_concise_result(tmp_path: Path) -> None:
    result = run_package(_payload(), tmp_path)

    assert result == PackageRunResult(
        status="completed",
        stage="completed",
        package_id="marketing-report",
        summary="Package ran and was independently verified; 1 declared output is ready.",
        generated_outputs=("report.md",),
        verification_passed=True,
        run_passed=True,
    )
    package = tmp_path / ".sensai" / "automations" / "marketing-report"
    assert (package / "report.md").read_text(encoding="utf-8") == "ran\n"
    assert set(path.name for path in package.iterdir()) == {
        "manifest.json",
        "report.md",
        "report.py",
        "sample.csv",
        "verify.py",
    }
    assert "verification details" not in json.dumps(result.to_dict())
    assert "run details" not in json.dumps(result.to_dict())


def test_inspection_validates_without_writing_and_returns_only_safe_plan(tmp_path: Path) -> None:
    inspection = inspect_package(_payload(), tmp_path)

    assert inspection == PackageInspection(
        status="ready",
        package_id="marketing-report",
        objective="Create a local weekly marketing report.",
        file_count=4,
        generated_outputs=("report.md",),
        summary="Package is valid and ready for local approval.",
    )
    assert not (tmp_path / ".sensai").exists()
    serialized = json.dumps(inspection.to_dict())
    assert "report.py" not in serialized
    assert RUN_SOURCE not in serialized


@pytest.mark.parametrize(
    "package_id",
    ["", "Uppercase", "../escape", "path/name", "path\\name", "-leading", "a" * 65],
)
def test_runner_rejects_invalid_package_ids(tmp_path: Path, package_id: str) -> None:
    result = run_package(_payload(package_id=package_id), tmp_path)

    assert result.status == "failed"
    assert result.stage == "validation"
    assert not (tmp_path / ".sensai" / "automations").exists()


@pytest.mark.parametrize(
    "missing_field",
    [
        "id",
        "objective",
        "files",
        "entrypoint",
        "verifier",
        "sample_input",
        "generated_outputs",
        "verification_command",
        "run_command",
    ],
)
def test_runner_rejects_missing_manifest_fields(tmp_path: Path, missing_field: str) -> None:
    payload = _payload()
    package = payload["package"]
    assert isinstance(package, dict)
    manifest = package["manifest"]
    assert isinstance(manifest, dict)
    manifest.pop(missing_field)

    result = run_package(payload, tmp_path)

    _assert_failed_without_package(result, tmp_path)
    assert result.stage == "validation"


@pytest.mark.parametrize(
    "unsafe_name",
    ["../escape.py", "/tmp/escape.py", "nested/file.py", "nested\\file.py", "C:\\escape.py"],
)
def test_runner_rejects_path_shaped_file_names(tmp_path: Path, unsafe_name: str) -> None:
    payload = _payload()
    package = payload["package"]
    assert isinstance(package, dict)
    manifest = package["manifest"]
    assert isinstance(manifest, dict)
    files = manifest["files"]
    assert isinstance(files, list)
    files.append(unsafe_name)
    records = package["files"]
    assert isinstance(records, list)
    records.append(_descriptor(unsafe_name, "text\n"))

    result = run_package(payload, tmp_path)

    _assert_failed_without_package(result, tmp_path)


def test_runner_rejects_undeclared_missing_or_duplicate_files(tmp_path: Path) -> None:
    for mutation in ("undeclared", "missing", "duplicate"):
        workspace = tmp_path / mutation
        workspace.mkdir()
        payload = _payload()
        package = payload["package"]
        assert isinstance(package, dict)
        records = package["files"]
        assert isinstance(records, list)
        if mutation == "undeclared":
            records.append(_descriptor("extra.txt", "unexpected\n"))
        elif mutation == "missing":
            records.pop()
        else:
            records.append(records[0])

        result = run_package(payload, workspace)

        _assert_failed_without_package(result, workspace)


@pytest.mark.parametrize("field", ["sha256", "byte_length", "content"])
def test_runner_rejects_file_integrity_mismatch(tmp_path: Path, field: str) -> None:
    payload = _payload()
    package = payload["package"]
    assert isinstance(package, dict)
    records = package["files"]
    assert isinstance(records, list)
    record = records[0]
    assert isinstance(record, dict)
    record[field] = "wrong" if field != "byte_length" else 999

    result = run_package(payload, tmp_path)

    _assert_failed_without_package(result, tmp_path)


def test_runner_rejects_manifest_object_that_differs_from_manifest_file(tmp_path: Path) -> None:
    payload = _payload()
    package = payload["package"]
    assert isinstance(package, dict)
    manifest = package["manifest"]
    assert isinstance(manifest, dict)
    manifest["objective"] = "Different object content"

    result = run_package(payload, tmp_path)

    _assert_failed_without_package(result, tmp_path)


@pytest.mark.parametrize(
    "unsafe_content",
    [
        "text\x00binary",
        base64.b64encode(b"MZ" + b"\x00" * 80).decode("ascii"),
        base64.b64encode(b"\x7fELF" + b"\x00" * 80).decode("ascii"),
    ],
)
def test_runner_rejects_binary_or_encoded_executable_content(
    tmp_path: Path, unsafe_content: str
) -> None:
    result = run_package(_payload(content_updates={"sample.csv": unsafe_content}), tmp_path)

    _assert_failed_without_package(result, tmp_path)


def test_runner_enforces_file_and_package_size_limits(tmp_path: Path) -> None:
    oversized_file = "x" * (MAX_FILE_BYTES + 1)
    result = run_package(_payload(content_updates={"sample.csv": oversized_file}), tmp_path)
    _assert_failed_without_package(result, tmp_path)

    many_files_payload = _payload()
    package = many_files_payload["package"]
    assert isinstance(package, dict)
    records = package["files"]
    assert isinstance(records, list)
    manifest = package["manifest"]
    assert isinstance(manifest, dict)
    inventory = manifest["files"]
    assert isinstance(inventory, list)
    index = 0
    while len(json.dumps(many_files_payload).encode("utf-8")) <= MAX_PACKAGE_BYTES:
        name = f"padding-{index}.txt"
        inventory.append(name)
        records.append(_descriptor(name, "x" * 1024))
        index += 1
    result = run_package(many_files_payload, tmp_path / "package-limit")
    assert result.status == "failed"
    assert result.stage == "validation"


@pytest.mark.parametrize(
    "command",
    [
        ["{python}", "{unknown}"],
        ["{python}", "prefix-{entrypoint}"],
        ["python", "{entrypoint}"],
        ["{python}", "{verifier}", "--flag", "{entrypoint}"],
        ["{python}", "{entrypoint}", ";", "other"],
    ],
)
def test_runner_rejects_unsafe_commands_and_placeholders(
    tmp_path: Path, command: list[str]
) -> None:
    result = run_package(_payload(manifest_updates={"verification_command": command}), tmp_path)

    _assert_failed_without_package(result, tmp_path)


def test_runner_rejects_symlinked_workspace_boundaries(tmp_path: Path) -> None:
    real_workspace = tmp_path / "real"
    real_workspace.mkdir()
    linked_workspace = tmp_path / "linked"
    linked_workspace.symlink_to(real_workspace, target_is_directory=True)
    result = run_package(_payload(), linked_workspace)
    assert result.status == "failed"
    assert not (real_workspace / ".sensai").exists()

    outside = tmp_path / "outside"
    outside.mkdir()
    (real_workspace / ".sensai").symlink_to(outside, target_is_directory=True)
    result = run_package(_payload(), real_workspace)
    assert result.status == "failed"
    assert not (outside / "automations").exists()


def test_runner_never_overwrites_an_existing_package(tmp_path: Path) -> None:
    package = tmp_path / ".sensai" / "automations" / "marketing-report"
    package.mkdir(parents=True)
    marker = package / "user-file.txt"
    marker.write_text("keep me\n", encoding="utf-8")

    result = run_package(_payload(), tmp_path)

    assert result.status == "failed"
    assert marker.read_text(encoding="utf-8") == "keep me\n"
    assert set(package.iterdir()) == {marker}


def test_failure_rolls_back_transaction_but_preserves_unrelated_files(tmp_path: Path) -> None:
    unrelated = tmp_path / "keep.txt"
    unrelated.write_text("untouched\n", encoding="utf-8")
    failing_verifier = VERIFY_SOURCE.replace(
        'print("verification details must not be returned")', "raise SystemExit(7)"
    )

    result = run_package(_payload(content_updates={"verify.py": failing_verifier}), tmp_path)

    _assert_failed_without_package(result, tmp_path)
    assert result.stage == "verification"
    assert unrelated.read_text(encoding="utf-8") == "untouched\n"


def test_timeout_and_output_limits_are_sanitized_and_rolled_back(tmp_path: Path) -> None:
    timeout_workspace = tmp_path / "timeout"
    timeout_workspace.mkdir()
    timeout_source = "import time\ntime.sleep(10)\n"
    timeout_result = run_package(
        _payload(content_updates={"verify.py": timeout_source}),
        timeout_workspace,
        timeout_seconds=0.5,
    )
    assert timeout_result.status == "failed"
    assert timeout_result.stage == "verification"
    assert "10" not in json.dumps(timeout_result.to_dict())

    noisy_workspace = tmp_path / "noisy"
    noisy_workspace.mkdir()
    noisy_source = 'print("SECRET-LIKE-OUTPUT-" * 100000)\n'
    noisy_result = run_package(
        _payload(content_updates={"verify.py": noisy_source}), noisy_workspace
    )
    assert noisy_result.status == "failed"
    serialized = json.dumps(noisy_result.to_dict())
    assert "SECRET-LIKE-OUTPUT" not in serialized


def test_runner_uses_a_bounded_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SENSAI_TEST_SECRET", "must-not-reach-child")
    environment_probe = RUN_SOURCE.replace(
        'output.write_text("ran\\n", encoding="utf-8")',
        "import os\n"
        'if "SENSAI_TEST_SECRET" in os.environ:\n'
        "    raise SystemExit(4)\n"
        'output.write_text("ran\\n", encoding="utf-8")',
    )

    result = run_package(_payload(content_updates={"report.py": environment_probe}), tmp_path)

    assert result.status == "completed"
    output = tmp_path / ".sensai" / "automations" / "marketing-report" / "report.md"
    assert output.read_text(encoding="utf-8") == "ran\n"


def test_cli_reads_payload_from_stdin_and_emits_only_structured_result(tmp_path: Path) -> None:
    payload = _payload()
    runner = tmp_path / "runner.py"
    runner.write_text(_standalone_runner_trusting(payload), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--workspace",
            str(tmp_path),
        ],
        cwd=REPOSITORY_ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env={"PATH": os.environ.get("PATH", "")},
        check=False,
    )

    assert completed.returncode == 0
    result = json.loads(completed.stdout)
    assert result["status"] == "completed"
    assert result["generated_outputs"] == ["report.md"]
    assert "verification details" not in completed.stdout
    assert "run details" not in completed.stdout
    assert completed.stderr == ""


def test_cli_inspection_is_read_only(tmp_path: Path) -> None:
    payload = _payload()
    runner = tmp_path / "runner.py"
    runner.write_text(_standalone_runner_trusting(payload), encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--inspect",
            "--workspace",
            str(tmp_path),
        ],
        cwd=REPOSITORY_ROOT,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env={"PATH": os.environ.get("PATH", "")},
        check=False,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["status"] == "ready"
    assert not (tmp_path / ".sensai").exists()


def test_runner_source_is_shipped_byte_for_byte_in_both_payload_layers() -> None:
    assert PAYLOAD_RUNNER.read_bytes() == SOURCE_RUNNER.read_bytes()
    assert PACKAGED_RUNNER.read_bytes() == SOURCE_RUNNER.read_bytes()
