"""Validate and execute one curated Sensai package inside a local workspace."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

MAX_FILE_BYTES = 64 * 1024
MAX_PACKAGE_BYTES = 256 * 1024
MAX_PACKAGE_FILES = 32
MAX_GENERATED_OUTPUT_BYTES = 1024 * 1024
MAX_PROCESS_OUTPUT_BYTES = 32 * 1024
MAX_COMMAND_ARGUMENTS = 32
MAX_COMMAND_ARGUMENT_BYTES = 256
DEFAULT_TIMEOUT_SECONDS = 30.0

# Generated from the reviewed server package by scripts/sync_public_marketplace.py.
# This is a public trust record, not a secret. Package code runs only when the
# canonical manifest and every declared file byte match this exact digest.
TRUSTED_PACKAGE_DIGESTS = {
    "marketing-csv-weekly-report": (
        "56533ef3243b5c775b69e613880b5614593fa8560635493d56311f90daffff3d"
    ),
}

_PACKAGE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+){0,15}\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_BASE64 = re.compile(r"[A-Za-z0-9+/]+={0,2}\Z")
_EXECUTABLE_SIGNATURES = (b"MZ", b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf")
_REQUIRED_MANIFEST_FIELDS = frozenset(
    {
        "id",
        "objective",
        "files",
        "entrypoint",
        "verifier",
        "sample_input",
        "generated_outputs",
        "verification_command",
        "run_command",
    }
)
_FILE_REFERENCE_FIELDS = ("entrypoint", "verifier", "sample_input")
_COMMAND_PLACEHOLDERS = frozenset({"{python}", "{entrypoint}", "{verifier}", "{input}", "{output}"})
_SAFE_ENVIRONMENT_NAMES = frozenset(
    {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TMP", "TEMP", "TMPDIR"}
)
_SHELL_METACHARACTERS = frozenset(";&|><")

Stage = Literal["validation", "write", "verification", "run", "output", "completed"]


@dataclass(frozen=True, slots=True)
class PackageRunResult:
    """Public-safe outcome returned to the calling agent."""

    status: Literal["completed", "failed"]
    stage: Stage
    package_id: str | None
    summary: str
    generated_outputs: tuple[str, ...] = ()
    verification_passed: bool = False
    run_passed: bool = False

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON-compatible result surface."""
        return {
            "status": self.status,
            "stage": self.stage,
            "package_id": self.package_id,
            "summary": self.summary,
            "generated_outputs": list(self.generated_outputs),
            "verification_passed": self.verification_passed,
            "run_passed": self.run_passed,
        }


@dataclass(frozen=True, slots=True)
class PackageInspection:
    """Validated, content-free plan safe to explain before local approval."""

    status: Literal["ready", "failed"]
    package_id: str | None
    objective: str | None
    file_count: int
    generated_outputs: tuple[str, ...]
    summary: str

    def to_dict(self) -> dict[str, object]:
        """Return the stable JSON-compatible inspection surface."""
        return {
            "status": self.status,
            "package_id": self.package_id,
            "objective": self.objective,
            "file_count": self.file_count,
            "generated_outputs": list(self.generated_outputs),
            "summary": self.summary,
        }


class _RunnerError(ValueError):
    def __init__(self, stage: Stage, summary: str) -> None:
        super().__init__(summary)
        self.stage = stage
        self.summary = summary


@dataclass(frozen=True, slots=True)
class _ValidatedPackage:
    package_id: str
    manifest: Mapping[str, Any]
    files: Mapping[str, str]
    generated_outputs: tuple[str, ...]


@dataclass(slots=True)
class _Transaction:
    workspace: Path
    package_directory: Path
    created_parents: list[Path]
    created_files: list[Path]
    generated_outputs: tuple[Path, ...]


def _hash_part(hasher: Any, payload: bytes) -> None:
    hasher.update(len(payload).to_bytes(8, "big"))
    hasher.update(payload)


def _canonical_digest(
    manifest: Mapping[str, Any],
    inventory: Sequence[str],
    files: Mapping[str, str],
) -> str:
    hasher = hashlib.sha256(b"sensai-trusted-package-v1\x00")
    canonical_manifest = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    _hash_part(hasher, canonical_manifest)
    for name in inventory:
        _hash_part(hasher, name.encode("utf-8"))
        _hash_part(hasher, files[name].encode("utf-8"))
    return hasher.hexdigest()


def canonical_package_digest(payload: object) -> str:
    """Return the release digest for one structured package payload."""
    root = _object(payload, "Package payload")
    package = _object(root.get("package"), "Package")
    manifest = _object(package.get("manifest"), "Manifest")
    inventory = _string_list(manifest.get("files"), "Manifest file inventory")
    raw_records = package.get("files")
    if not isinstance(raw_records, list):
        raise _RunnerError("validation", "Package files must be a list.")
    files: dict[str, str] = {}
    for raw_record in raw_records:
        record = _object(raw_record, "Package file")
        name = _safe_name(record.get("name"), "Package file name")
        content = record.get("content")
        if not isinstance(content, str) or name in files:
            raise _RunnerError("validation", "Package files are invalid.")
        files[name] = content
    if set(files) != set(inventory):
        raise _RunnerError("validation", "Package files do not match the manifest inventory.")
    return _canonical_digest(manifest, inventory, files)


def _failed(
    stage: Stage,
    summary: str,
    package_id: str | None = None,
    *,
    verification_passed: bool = False,
    run_passed: bool = False,
) -> PackageRunResult:
    return PackageRunResult(
        status="failed",
        stage=stage,
        package_id=package_id,
        summary=summary,
        verification_passed=verification_passed,
        run_passed=run_passed,
    )


def _encoded_json_size(value: object) -> int:
    try:
        return len(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise _RunnerError("validation", "Package payload is not valid JSON data.") from error


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise _RunnerError("validation", f"{label} must be an object.")
    return value


def _safe_name(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 128
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or ":" in value
        or "\x00" in value
    ):
        raise _RunnerError("validation", f"{label} is not a safe file name.")
    return value


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise _RunnerError("validation", f"{label} must be a non-empty list.")
    names = tuple(_safe_name(item, label) for item in value)
    if len(names) != len(set(names)):
        raise _RunnerError("validation", f"{label} contains duplicates.")
    return names


def _contains_encoded_executable(content: str) -> bool:
    compact = "".join(content.split())
    if len(compact) < 16 or len(compact) % 4 or _BASE64.fullmatch(compact) is None:
        return False
    try:
        decoded = base64.b64decode(compact, validate=True)
    except (binascii.Error, ValueError):
        return False
    return decoded.startswith(_EXECUTABLE_SIGNATURES)


def _validate_text(content: str) -> bytes:
    try:
        encoded = content.encode("utf-8")
    except UnicodeEncodeError as error:
        raise _RunnerError("validation", "Package contains invalid text.") from error
    if len(encoded) > MAX_FILE_BYTES:
        raise _RunnerError("validation", "Package contains an oversized file.")
    if "\x00" in content or any(
        ord(character) < 32 and character not in {"\n", "\r", "\t"} for character in content
    ):
        raise _RunnerError("validation", "Package contains binary content.")
    if _contains_encoded_executable(content):
        raise _RunnerError("validation", "Package contains an encoded executable.")
    return encoded


def _validate_command(
    value: object,
    *,
    label: str,
    required_script: str,
    permitted_placeholders: frozenset[str],
) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not 2 <= len(value) <= MAX_COMMAND_ARGUMENTS
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise _RunnerError("validation", f"{label} must be an argv array.")
    command = tuple(value)
    if command[:2] != ("{python}", required_script):
        raise _RunnerError("validation", f"{label} must run the declared Python file.")
    for argument in command:
        if len(argument.encode("utf-8")) > MAX_COMMAND_ARGUMENT_BYTES:
            raise _RunnerError("validation", f"{label} contains an oversized argument.")
        if "{" in argument or "}" in argument:
            if argument not in _COMMAND_PLACEHOLDERS or argument not in permitted_placeholders:
                raise _RunnerError("validation", f"{label} contains an invalid placeholder.")
        elif any(character in _SHELL_METACHARACTERS for character in argument) or any(
            ord(character) < 32 for character in argument
        ):
            raise _RunnerError("validation", f"{label} contains an unsafe argument.")
    return command


def _validate_payload(payload: object) -> _ValidatedPackage:
    if _encoded_json_size(payload) > MAX_PACKAGE_BYTES:
        raise _RunnerError("validation", "Package payload is oversized.")
    root = _object(payload, "Package payload")
    if set(root) != {"package"}:
        raise _RunnerError("validation", "Package payload has unexpected fields.")
    package = _object(root["package"], "Package")
    if set(package) != {"id", "manifest", "files"}:
        raise _RunnerError("validation", "Package has unexpected fields.")

    package_id = package["id"]
    if (
        not isinstance(package_id, str)
        or len(package_id) > 64
        or _PACKAGE_ID.fullmatch(package_id) is None
    ):
        raise _RunnerError("validation", "Package ID is invalid.")
    trusted_digest = TRUSTED_PACKAGE_DIGESTS.get(package_id)
    if trusted_digest is None:
        raise _RunnerError("validation", "Package is not trusted by this Sensai release.")

    manifest = _object(package["manifest"], "Manifest")
    missing = _REQUIRED_MANIFEST_FIELDS - manifest.keys()
    if missing:
        raise _RunnerError("validation", "Manifest is missing required fields.")
    if manifest["id"] != package_id:
        raise _RunnerError("validation", "Manifest ID does not match the package ID.")
    objective = manifest["objective"]
    if not isinstance(objective, str) or not objective.strip() or len(objective) > 2_000:
        raise _RunnerError("validation", "Manifest objective is invalid.")

    inventory = _string_list(manifest["files"], "Manifest file inventory")
    if "manifest.json" not in inventory or len(inventory) > MAX_PACKAGE_FILES:
        raise _RunnerError("validation", "Manifest file inventory is invalid.")
    references: dict[str, str] = {}
    for field in _FILE_REFERENCE_FIELDS:
        references[field] = _safe_name(manifest[field], f"Manifest {field}")
        if references[field] not in inventory:
            raise _RunnerError("validation", f"Manifest {field} is not a declared file.")

    generated_outputs = _string_list(manifest["generated_outputs"], "Generated outputs")
    if set(generated_outputs) & set(inventory):
        raise _RunnerError("validation", "Generated outputs overlap package files.")
    if len(generated_outputs) != 1:
        raise _RunnerError("validation", "This runner requires exactly one generated output.")

    _validate_command(
        manifest["verification_command"],
        label="Verification command",
        required_script="{verifier}",
        permitted_placeholders=frozenset({"{python}", "{verifier}", "{input}", "{output}"}),
    )
    _validate_command(
        manifest["run_command"],
        label="Run command",
        required_script="{entrypoint}",
        permitted_placeholders=frozenset({"{python}", "{entrypoint}", "{input}", "{output}"}),
    )

    raw_records = package["files"]
    if not isinstance(raw_records, list) or not raw_records:
        raise _RunnerError("validation", "Package files must be a non-empty list.")
    files: dict[str, str] = {}
    total_file_bytes = 0
    for raw_record in raw_records:
        record = _object(raw_record, "Package file")
        if set(record) != {"name", "content", "byte_length", "sha256"}:
            raise _RunnerError("validation", "Package file has unexpected fields.")
        name = _safe_name(record["name"], "Package file name")
        if name in files:
            raise _RunnerError("validation", "Package contains duplicate files.")
        content = record["content"]
        if not isinstance(content, str):
            raise _RunnerError("validation", "Package file content must be text.")
        encoded = _validate_text(content)
        byte_length = record["byte_length"]
        digest = record["sha256"]
        if (
            not isinstance(byte_length, int)
            or isinstance(byte_length, bool)
            or byte_length != len(encoded)
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
            or not hmac.compare_digest(hashlib.sha256(encoded).hexdigest(), digest)
        ):
            raise _RunnerError("validation", "Package file integrity check failed.")
        total_file_bytes += len(encoded)
        if total_file_bytes > MAX_PACKAGE_BYTES:
            raise _RunnerError("validation", "Package files are oversized.")
        files[name] = content

    if set(files) != set(inventory):
        raise _RunnerError("validation", "Package files do not match the manifest inventory.")
    try:
        manifest_file = json.loads(files["manifest.json"])
    except json.JSONDecodeError as error:
        raise _RunnerError("validation", "Manifest file is invalid JSON.") from error
    if manifest_file != manifest:
        raise _RunnerError("validation", "Manifest object does not match manifest.json.")
    actual_digest = _canonical_digest(manifest, inventory, files)
    if not hmac.compare_digest(actual_digest, trusted_digest):
        raise _RunnerError("validation", "Package does not match the trusted Sensai release.")

    return _ValidatedPackage(
        package_id=package_id,
        manifest=manifest,
        files=files,
        generated_outputs=generated_outputs,
    )


def _regular_directory(path: Path, label: str) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as error:
        raise _RunnerError("validation", f"{label} is unavailable.") from error
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise _RunnerError("validation", f"{label} must be a regular directory.")


def _ensure_directory(path: Path, transaction: _Transaction) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        try:
            path.mkdir()
        except OSError as error:
            raise _RunnerError("write", "Could not create the package boundary.") from error
        transaction.created_parents.append(path)
        mode = path.lstat().st_mode
    except OSError as error:
        raise _RunnerError("write", "Could not inspect the package boundary.") from error
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise _RunnerError("validation", "Package boundary is unsafe.")


def _start_transaction(workspace: Path, package: _ValidatedPackage) -> _Transaction:
    _regular_directory(workspace, "Target workspace")
    package_directory = workspace / ".sensai" / "automations" / package.package_id
    transaction = _Transaction(
        workspace=workspace,
        package_directory=package_directory,
        created_parents=[],
        created_files=[],
        generated_outputs=tuple(package_directory / name for name in package.generated_outputs),
    )
    _ensure_directory(workspace / ".sensai", transaction)
    _ensure_directory(workspace / ".sensai" / "automations", transaction)
    if package_directory.exists() or package_directory.is_symlink():
        raise _RunnerError("validation", "Package directory already exists; refusing overwrite.")
    try:
        package_directory.mkdir()
    except OSError as error:
        raise _RunnerError("write", "Could not create the package directory.") from error
    transaction.created_parents.append(package_directory)
    return transaction


def _atomic_write(path: Path, content: str, transaction: _Transaction) -> None:
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".sensai-write-", dir=transaction.package_directory
        )
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists() or path.is_symlink():
            raise _RunnerError("write", "A package file appeared during installation.")
        os.replace(temporary, path)
        temporary = None
        transaction.created_files.append(path)
    except _RunnerError:
        raise
    except OSError as error:
        raise _RunnerError("write", "Could not write a package file.") from error
    finally:
        if temporary is not None:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


def _write_package(package: _ValidatedPackage, transaction: _Transaction) -> None:
    for name in sorted(package.files):
        _atomic_write(transaction.package_directory / name, package.files[name], transaction)


def _resolved_command(
    template: Sequence[str], package: _ValidatedPackage, transaction: _Transaction
) -> list[str]:
    manifest = package.manifest
    replacements = {
        "{python}": sys.executable,
        "{entrypoint}": str(transaction.package_directory / str(manifest["entrypoint"])),
        "{verifier}": str(transaction.package_directory / str(manifest["verifier"])),
        "{input}": str(transaction.package_directory / str(manifest["sample_input"])),
        "{output}": str(transaction.generated_outputs[0]),
    }
    return [replacements.get(argument, argument) for argument in template]


def _child_environment() -> dict[str, str]:
    environment = {
        name: value
        for name in _SAFE_ENVIRONMENT_NAMES
        if (value := os.environ.get(name)) is not None
    }
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUTF8"] = "1"
    return environment


def _drain_pipe(
    pipe: Any,
    byte_count: list[int],
    exceeded: threading.Event,
) -> None:
    try:
        while chunk := pipe.read(4096):
            byte_count[0] += len(chunk)
            if byte_count[0] > MAX_PROCESS_OUTPUT_BYTES:
                exceeded.set()
                return
    finally:
        pipe.close()


def _run_command(
    command: Sequence[str],
    *,
    package_directory: Path,
    timeout_seconds: float,
    stage: Literal["verification", "run"],
) -> None:
    try:
        process = subprocess.Popen(
            list(command),
            cwd=package_directory,
            env=_child_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as error:
        raise _RunnerError(stage, f"{stage.capitalize()} command could not start.") from error
    assert process.stdout is not None
    assert process.stderr is not None
    exceeded = threading.Event()
    byte_count = [0]
    readers = [
        threading.Thread(
            target=_drain_pipe,
            args=(pipe, byte_count, exceeded),
            daemon=True,
        )
        for pipe in (process.stdout, process.stderr)
    ]
    for reader in readers:
        reader.start()

    deadline = time.monotonic() + timeout_seconds
    failure: str | None = None
    while process.poll() is None:
        if exceeded.is_set():
            failure = f"{stage.capitalize()} output exceeded the safe limit."
            process.kill()
            break
        if time.monotonic() >= deadline:
            failure = f"{stage.capitalize()} timed out."
            process.kill()
            break
        time.sleep(0.01)
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    for reader in readers:
        reader.join(timeout=1)
    if failure is not None:
        raise _RunnerError(stage, failure)
    if exceeded.is_set():
        raise _RunnerError(stage, f"{stage.capitalize()} output exceeded the safe limit.")
    if process.returncode != 0:
        raise _RunnerError(stage, f"{stage.capitalize()} command failed.")


def _check_package_tree(package: _ValidatedPackage, transaction: _Transaction) -> None:
    expected = set(package.files) | set(package.generated_outputs)
    try:
        entries = list(transaction.package_directory.iterdir())
    except OSError as error:
        raise _RunnerError("output", "Could not inspect package outputs.") from error
    for path in entries:
        if path.name not in expected:
            raise _RunnerError("output", "Package created an undeclared output.")
        try:
            mode = path.lstat().st_mode
        except OSError as error:
            raise _RunnerError("output", "Could not inspect package outputs.") from error
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise _RunnerError("output", "Package output is not a regular file.")


def _check_generated_outputs(package: _ValidatedPackage, transaction: _Transaction) -> None:
    _check_package_tree(package, transaction)
    for path in transaction.generated_outputs:
        try:
            payload = path.read_bytes()
        except OSError as error:
            raise _RunnerError("output", "A declared output is missing.") from error
        if len(payload) > MAX_GENERATED_OUTPUT_BYTES or b"\x00" in payload:
            raise _RunnerError("output", "A declared output is unsafe or oversized.")
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise _RunnerError("output", "A declared output is not UTF-8 text.") from error


def _unlink_transaction_path(path: Path) -> None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    except OSError:
        return
    if stat.S_ISREG(mode) or stat.S_ISLNK(mode):
        with suppress(OSError):
            path.unlink()


def _rollback(transaction: _Transaction | None) -> None:
    if transaction is None:
        return
    created_parents = list(transaction.created_parents)
    if transaction.package_directory in created_parents:
        with suppress(OSError):
            shutil.rmtree(transaction.package_directory)
        created_parents.remove(transaction.package_directory)
    else:
        for path in (*transaction.generated_outputs, *reversed(transaction.created_files)):
            _unlink_transaction_path(path)
    for path in reversed(created_parents):
        with suppress(OSError):
            path.rmdir()


def inspect_package(payload: object, workspace: Path) -> PackageInspection:
    """Validate a package and workspace without writing or running anything."""
    try:
        package = _validate_payload(payload)
        _regular_directory(workspace, "Target workspace")
    except _RunnerError as error:
        return PackageInspection(
            status="failed",
            package_id=None,
            objective=None,
            file_count=0,
            generated_outputs=(),
            summary=error.summary,
        )
    return PackageInspection(
        status="ready",
        package_id=package.package_id,
        objective=str(package.manifest["objective"]),
        file_count=len(package.files),
        generated_outputs=package.generated_outputs,
        summary="Package is valid and ready for local approval.",
    )


def run_package(
    payload: object,
    workspace: Path,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> PackageRunResult:
    """Validate, install, run, and independently verify one trusted package."""
    package: _ValidatedPackage | None = None
    transaction: _Transaction | None = None
    verification_passed = False
    run_passed = False
    try:
        if not 0.05 <= timeout_seconds <= 120.0:
            raise _RunnerError("validation", "Command timeout is outside the allowed range.")
        package = _validate_payload(payload)
        transaction = _start_transaction(workspace, package)
        _write_package(package, transaction)
        run = _resolved_command(package.manifest["run_command"], package, transaction)
        _run_command(
            run,
            package_directory=transaction.package_directory,
            timeout_seconds=timeout_seconds,
            stage="run",
        )
        run_passed = True
        _check_generated_outputs(package, transaction)
        verification = _resolved_command(
            package.manifest["verification_command"], package, transaction
        )
        _run_command(
            verification,
            package_directory=transaction.package_directory,
            timeout_seconds=timeout_seconds,
            stage="verification",
        )
        verification_passed = True
        _check_generated_outputs(package, transaction)
    except _RunnerError as error:
        _rollback(transaction)
        return _failed(
            error.stage,
            error.summary,
            package.package_id if package is not None else None,
            verification_passed=verification_passed,
            run_passed=run_passed,
        )
    except BaseException:
        _rollback(transaction)
        return _failed(
            "run",
            "Package execution failed safely.",
            package.package_id if package is not None else None,
            verification_passed=verification_passed,
            run_passed=run_passed,
        )

    assert package is not None
    count = len(package.generated_outputs)
    noun = "output is" if count == 1 else "outputs are"
    return PackageRunResult(
        status="completed",
        stage="completed",
        package_id=package.package_id,
        summary=(f"Package ran and was independently verified; {count} declared {noun} ready."),
        generated_outputs=package.generated_outputs,
        verification_passed=True,
        run_passed=True,
    )


def _read_stdin_payload() -> object:
    payload = sys.stdin.buffer.read(MAX_PACKAGE_BYTES + 1)
    if len(payload) > MAX_PACKAGE_BYTES:
        raise _RunnerError("validation", "Package payload is oversized.")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _RunnerError("validation", "Package payload is not valid JSON.") from error


def main(argv: Sequence[str] | None = None) -> int:
    """Run the safe package protocol from a platform-neutral CLI."""
    parser = argparse.ArgumentParser(description="Run one curated Sensai package safely.")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    arguments = parser.parse_args(argv)
    result: PackageRunResult | PackageInspection
    try:
        payload = _read_stdin_payload()
    except _RunnerError as error:
        result = _failed(error.stage, error.summary)
    else:
        if arguments.inspect:
            result = inspect_package(payload, arguments.workspace)
        else:
            result = run_package(
                payload,
                arguments.workspace,
                timeout_seconds=arguments.timeout_seconds,
            )
    print(json.dumps(result.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0 if result.status in {"completed", "ready"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
