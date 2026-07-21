#!/usr/bin/env python3
"""Public acceptance context for one verified Claude plugin release."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VERIFY_RELEASE = REPOSITORY_ROOT / "scripts" / "verify_release.py"
CLAUDE_TIMEOUT_SECONDS = 45
CLAUDE_TERMINATION_GRACE_SECONDS = 2
MAX_BUNDLE_ENTRIES = 3
MAX_BUNDLE_FILE_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 128
MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_EXTRACTED_BYTES = 8 * 1024 * 1024
PLUGIN_MCP_NAME = "plugin:sensai:sensai"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PASSTHROUGH_ENVIRONMENT_NAMES = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)


class ClaudeAcceptanceError(AssertionError):
    """Raised when the release or isolated Claude lifecycle is not exact."""


@dataclass(frozen=True)
class VerifiedClaudeRelease:
    marketplace: Path
    selector: str
    version: str
    mcp_url: str
    mcp_attestation: dict[str, str]
    files: dict[str, str]


@dataclass(frozen=True, slots=True)
class InstalledClaudePlugin:
    """Observed plugin identity while its isolated Claude profile is alive."""

    selector: str
    version: str
    mcp_url: str
    profile: Path


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ClaudeAcceptanceError(f"invalid JSON document: {path.name}") from error
    if not isinstance(value, dict):
        raise ClaudeAcceptanceError(f"expected JSON object: {path.name}")
    return value


def _run_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=CLAUDE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=CLAUDE_TERMINATION_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        raise ClaudeAcceptanceError(f"command timed out: {command[:3]!r}") from error
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check and completed.returncode != 0:
        raise ClaudeAcceptanceError(
            f"command failed ({completed.returncode}): {command[:3]!r}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return completed


def _verify_release_independently(bundle: Path) -> dict[str, Any]:
    completed = _run_process(
        [sys.executable, str(VERIFY_RELEASE), "--bundle", str(bundle)],
        cwd=REPOSITORY_ROOT,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ClaudeAcceptanceError(f"release verification failed: {detail}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ClaudeAcceptanceError("release verifier returned invalid JSON") from error
    if not isinstance(result, dict) or result.get("verified") is not True:
        raise ClaudeAcceptanceError("release verifier did not attest success")
    return result


def _set_tree_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink():
            raise ClaudeAcceptanceError(f"read-only tree contains a symlink: {path}")
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)
    writable = [
        path
        for path in (root, *root.rglob("*"))
        if path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    ]
    if writable:
        raise ClaudeAcceptanceError("filesystem did not enforce read-only marketplace permissions")


def remove_readonly_tree(root: Path) -> None:
    """Remove one owned temporary tree without leaving its contents writable."""
    if not root.exists() and not root.is_symlink():
        return
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink():
            continue
        path.chmod(0o700 if path.is_dir() else 0o600)
    if not root.is_symlink():
        root.chmod(0o700)
    shutil.rmtree(root)


def _temporary_root() -> Path:
    configured = os.environ.get("SENSAI_CLAUDE_LIFECYCLE_TMPDIR", "/tmp")
    root = Path(configured).resolve(strict=True)
    if not root.is_dir():
        raise ClaudeAcceptanceError("Claude lifecycle temporary root is not a directory")
    return root


def _regular_bundle_path(bundle: Path) -> Path:
    """Validate the caller-provided bundle path before any symlink resolution."""
    try:
        bundle_stat = os.lstat(bundle)
    except OSError as error:
        raise ClaudeAcceptanceError("release bundle is unavailable") from error
    if stat.S_ISLNK(bundle_stat.st_mode):
        raise ClaudeAcceptanceError("release bundle must not be a symlink")
    if not stat.S_ISDIR(bundle_stat.st_mode):
        raise ClaudeAcceptanceError("release bundle must be a regular directory")
    return bundle.absolute()


@contextmanager
def _immutable_bundle_snapshot(bundle: Path, parent: Path) -> Iterator[Path]:
    if bundle.is_symlink() or not bundle.is_dir():
        raise ClaudeAcceptanceError("release bundle must be a regular directory")
    parent.mkdir(parents=True, exist_ok=True)
    snapshot_root = Path(tempfile.mkdtemp(prefix=".sensai-claude-snapshot-", dir=parent))
    snapshot = snapshot_root / "bundle"
    snapshot.mkdir()
    try:
        entries = sorted(os.scandir(bundle), key=lambda entry: entry.name)
        if not entries:
            raise ClaudeAcceptanceError("release bundle is empty")
        if len(entries) > MAX_BUNDLE_ENTRIES:
            raise ClaudeAcceptanceError("release bundle contains too many entries")
        for source in entries:
            if not source.is_file(follow_symlinks=False):
                raise ClaudeAcceptanceError(
                    f"release bundle contains a non-regular entry: {source.name}"
                )
            target = snapshot / source.name
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(source.path, flags)
                with os.fdopen(descriptor, "rb") as input_file:
                    before = os.fstat(input_file.fileno())
                    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BUNDLE_FILE_BYTES:
                        raise ClaudeAcceptanceError("invalid release bundle file")
                    content = input_file.read(MAX_BUNDLE_FILE_BYTES + 1)
                    after = os.fstat(input_file.fileno())
            except OSError as error:
                raise ClaudeAcceptanceError("could not snapshot release bundle") from error
            if len(content) > MAX_BUNDLE_FILE_BYTES or (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
            ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise ClaudeAcceptanceError("release bundle changed while snapshotting")
            target.write_bytes(content)
            target.chmod(0o444)
        _set_tree_read_only(snapshot)
        yield snapshot
    finally:
        remove_readonly_tree(snapshot_root)


def _snapshot_identity(snapshot: Path) -> tuple[tuple[object, ...], ...]:
    """Bind the snapshot path to its root and direct regular-file identities."""
    try:
        root_before = os.lstat(snapshot)
    except OSError as error:
        raise ClaudeAcceptanceError("private release snapshot disappeared") from error
    if not stat.S_ISDIR(root_before.st_mode):
        raise ClaudeAcceptanceError("private release snapshot is not a directory")

    result: list[tuple[object, ...]] = [
        (
            ".",
            "directory",
            stat.S_IMODE(root_before.st_mode),
            root_before.st_dev,
            root_before.st_ino,
            root_before.st_mtime_ns,
        )
    ]
    try:
        entries = sorted(os.scandir(snapshot), key=lambda entry: entry.name)
    except OSError as error:
        raise ClaudeAcceptanceError("could not enumerate private release snapshot") from error
    for entry in entries:
        try:
            before = os.lstat(entry.path)
        except OSError as error:
            raise ClaudeAcceptanceError("could not inspect private snapshot entry") from error
        if not stat.S_ISREG(before.st_mode):
            raise ClaudeAcceptanceError("private release snapshot contains a non-regular entry")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(entry.path, flags)
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                content = handle.read()
                after = os.fstat(handle.fileno())
        except OSError as error:
            raise ClaudeAcceptanceError("could not fingerprint private snapshot file") from error
        expected = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if expected != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
            opened.st_mtime_ns,
        ) or expected != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise ClaudeAcceptanceError(
                "private release snapshot file changed while fingerprinting"
            )
        result.append(
            (
                entry.name,
                "file",
                stat.S_IMODE(before.st_mode),
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                hashlib.sha256(content).hexdigest(),
            )
        )
    try:
        root_after = os.lstat(snapshot)
    except OSError as error:
        raise ClaudeAcceptanceError("private release snapshot disappeared") from error
    if (
        root_before.st_dev,
        root_before.st_ino,
        root_before.st_mode,
        root_before.st_mtime_ns,
    ) != (
        root_after.st_dev,
        root_after.st_ino,
        root_after.st_mode,
        root_after.st_mtime_ns,
    ):
        raise ClaudeAcceptanceError("private release snapshot changed while fingerprinting")
    return tuple(result)


def _safe_member(name: str) -> PurePosixPath:
    relative = PurePosixPath(name)
    if (
        not name
        or name.endswith("/")
        or relative.is_absolute()
        or ".." in relative.parts
        or "\\" in name
        or any(part in {"", "."} for part in relative.parts)
    ):
        raise ClaudeAcceptanceError(f"unsafe archive path: {name!r}")
    return relative


def _extract_exact_archive(
    archive_path: Path,
    destination: Path,
    expected_files: dict[str, str],
) -> dict[str, str]:
    if destination.exists() or destination.is_symlink():
        raise ClaudeAcceptanceError("marketplace extraction destination already exists")
    destination.mkdir(parents=True)
    actual: dict[str, str] = {}
    total = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise ClaudeAcceptanceError("archive member count exceeds limit")
            seen: set[str] = set()
            for info in members:
                relative = _safe_member(info.filename)
                if info.filename in seen:
                    raise ClaudeAcceptanceError(f"duplicate archive path: {info.filename}")
                seen.add(info.filename)
                mode = info.external_attr >> 16
                if info.is_dir() or not stat.S_ISREG(mode):
                    raise ClaudeAcceptanceError(
                        f"archive entry is not a regular file: {info.filename}"
                    )
                if info.file_size > MAX_MEMBER_BYTES:
                    raise ClaudeAcceptanceError("archive member exceeds size limit")
                total += info.file_size
                if total > MAX_EXTRACTED_BYTES:
                    raise ClaudeAcceptanceError("archive extracted bytes exceed size limit")
                target = destination.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                with archive.open(info) as source, target.open("xb") as output:
                    while chunk := source.read(64 * 1024):
                        digest.update(chunk)
                        output.write(chunk)
                target.chmod(0o444)
                actual[info.filename] = digest.hexdigest()
    except (OSError, zipfile.BadZipFile) as error:
        raise ClaudeAcceptanceError(
            "could not safely extract Claude marketplace archive"
        ) from error
    if actual != expected_files:
        raise ClaudeAcceptanceError(
            "extracted Claude marketplace bytes do not match release metadata"
        )
    return actual


def _manifest_entries(manifest: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if separator != "  " or _SHA256.fullmatch(digest) is None:
            raise ClaudeAcceptanceError("Claude plugin MANIFEST.sha256 is malformed")
        if relative in entries or _safe_member(relative).as_posix() != relative:
            raise ClaudeAcceptanceError("Claude plugin MANIFEST.sha256 contains an unsafe path")
        entries[relative] = digest
    return entries


def _verify_extracted_payload(
    marketplace: Path,
    metadata: dict[str, Any],
) -> tuple[str, dict[str, str]]:
    plugin = marketplace / "plugins" / "sensai"
    manifest = plugin / "MANIFEST.sha256"
    expected = _manifest_entries(manifest)
    actual = {
        path.relative_to(plugin).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(plugin.rglob("*"))
        if path.is_file() and path != manifest
    }
    if actual != expected:
        raise ClaudeAcceptanceError("extracted Claude plugin does not match MANIFEST.sha256")

    marketplace_manifest = _load_object(marketplace / ".claude-plugin" / "marketplace.json")
    if marketplace_manifest.get("name") != "sensai-local":
        raise ClaudeAcceptanceError("unexpected Claude marketplace name")
    plugins = marketplace_manifest.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        raise ClaudeAcceptanceError("Claude marketplace must contain exactly one plugin")
    plugin_entry = plugins[0]
    if not isinstance(plugin_entry, dict) or plugin_entry.get("name") != "sensai":
        raise ClaudeAcceptanceError("unexpected Claude marketplace plugin selector")
    if plugin_entry.get("source") != "./plugins/sensai":
        raise ClaudeAcceptanceError("Claude marketplace plugin source is not exact")

    attestation_value = _load_object(plugin / "sensai-mcp-attestation.json")
    attestation = {key: str(value) for key, value in attestation_value.items()}
    expected_attestation = {
        "format_version": "1",
        "mcp_contract_version": str(metadata["mcp_contract_version"]),
        "mcp_schema_sha256": str(metadata["mcp_schema_sha256"]),
        "mcp_url": str(metadata["mcp_url"]),
    }
    if attestation != expected_attestation:
        raise ClaudeAcceptanceError("Claude MCP attestation does not match release metadata")
    return "sensai@sensai-local", attestation


def _prepare_verified_marketplace_from_snapshot(
    snapshot: Path,
    destination: Path,
) -> VerifiedClaudeRelease:
    """Verify one private snapshot and extract its exact Claude marketplace payload."""
    snapshot_before = _snapshot_identity(snapshot)
    try:
        verification = _verify_release_independently(snapshot)
        if _snapshot_identity(snapshot) != snapshot_before:
            raise ClaudeAcceptanceError(
                "private release snapshot changed after independent verification"
            )
        metadata = _load_object(snapshot / "release.json")
        claude = metadata.get("platforms", {}).get("claude")
        if not isinstance(claude, dict):
            raise ClaudeAcceptanceError("release metadata has no Claude platform")
        files = claude.get("files")
        if not isinstance(files, dict) or not files:
            raise ClaudeAcceptanceError("Claude release has no file manifest")
        expected_files = {str(path): str(digest) for path, digest in files.items()}
        archive_name = claude.get("archive")
        if not isinstance(archive_name, str) or PurePosixPath(archive_name).name != archive_name:
            raise ClaudeAcceptanceError("Claude archive path is unsafe")
        if verification.get("release_version") != metadata.get("release_version"):
            raise ClaudeAcceptanceError("release verifier version does not match metadata")
        if verification.get("mcp_url") != metadata.get("mcp_url"):
            raise ClaudeAcceptanceError("release verifier MCP URL does not match metadata")

        actual_files = _extract_exact_archive(snapshot / archive_name, destination, expected_files)
        selector, attestation = _verify_extracted_payload(destination, metadata)
        if _snapshot_identity(snapshot) != snapshot_before:
            raise ClaudeAcceptanceError(
                "private release snapshot changed during archive extraction"
            )
        _set_tree_read_only(destination)
    except BaseException:
        if destination.exists():
            remove_readonly_tree(destination)
        raise
    return VerifiedClaudeRelease(
        marketplace=destination,
        selector=selector,
        version=str(metadata["release_version"]),
        mcp_url=str(metadata["mcp_url"]),
        mcp_attestation=attestation,
        files=actual_files,
    )


def prepare_verified_marketplace(bundle: Path, destination: Path) -> VerifiedClaudeRelease:
    """Prepare a verified marketplace for focused archive tests.

    The public installed-plugin context keeps its snapshot alive longer; this helper
    remains useful for direct extraction tests only.
    """
    source = _regular_bundle_path(bundle)
    with _immutable_bundle_snapshot(source, destination.parent) as snapshot:
        return _prepare_verified_marketplace_from_snapshot(snapshot, destination)


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.exists() and not path.is_symlink():
        return "missing"
    roots = [path]
    if path.is_dir() and not path.is_symlink():
        roots.extend(sorted(path.rglob("*")))
    for entry in roots:
        relative = "." if entry == path else entry.relative_to(path).as_posix()
        digest.update(relative.encode())
        mode = entry.lstat().st_mode
        digest.update(str(stat.S_IMODE(mode)).encode())
        if entry.is_symlink():
            digest.update(b"L")
            digest.update(os.readlink(entry).encode())
        elif entry.is_file():
            digest.update(b"F")
            digest.update(entry.read_bytes())
        elif entry.is_dir():
            digest.update(b"D")
        else:
            digest.update(b"O")
    return digest.hexdigest()


def _fingerprint_shallow(path: Path) -> str:
    if not path.exists() and not path.is_symlink():
        return "missing"
    if path.is_symlink() or path.is_file():
        return _fingerprint(path)
    digest = hashlib.sha256()
    for entry in sorted(path.iterdir()):
        digest.update(entry.name.encode())
        mode = entry.lstat().st_mode
        if entry.is_symlink():
            digest.update(b"L")
            digest.update(os.readlink(entry).encode())
        elif entry.is_file():
            digest.update(b"F")
            digest.update(entry.read_bytes())
        elif entry.is_dir():
            digest.update(b"D")
        else:
            digest.update(b"O")
        digest.update(str(stat.S_IMODE(mode)).encode())
    return digest.hexdigest()


def _real_config_roots() -> tuple[Path, ...]:
    home = Path.home()
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude")).expanduser().absolute()
    return tuple(dict.fromkeys((config, config.resolve(strict=False))))


def _real_profile_paths() -> tuple[Path, ...]:
    home = Path.home()
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude"))
    plugin_cache = Path(os.environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR", config / "plugins"))
    xdg_cache = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
    xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    candidates = [
        config / "plugins",
        config / "backups",
        plugin_cache,
        home / ".claude.json",
        xdg_cache / "claude",
        xdg_cache / "claude-cli-nodejs",
        xdg_config / "claude",
        xdg_data / "claude",
        xdg_data / "claude-code",
        REPOSITORY_ROOT / ".claude",
    ]
    if secure_storage := os.environ.get("CLAUDE_SECURESTORAGE_CONFIG_DIR"):
        candidates.append(Path(secure_storage))
    resolved_config = config.expanduser().resolve(strict=False)
    if resolved_config.is_dir():
        candidates.extend(
            path for path in resolved_config.iterdir() if path.is_file() or path.is_symlink()
        )
    paths: list[Path] = []
    for candidate in candidates:
        absolute = candidate.expanduser().absolute()
        paths.extend((absolute, absolute.resolve(strict=False)))
    return tuple(dict.fromkeys(paths))


def _real_profile_fingerprint() -> dict[str, str]:
    result = {f"recursive:{path}": _fingerprint(path) for path in _real_profile_paths()}
    result.update({f"shallow:{path}": _fingerprint_shallow(path) for path in _real_config_roots()})
    return result


def _real_profile_boundaries() -> tuple[Path, ...]:
    """Return every real Claude-owned path that an isolated profile must not overlap."""
    paths: list[Path] = []
    for path in (*_real_config_roots(), *_real_profile_paths()):
        absolute = path.expanduser().absolute()
        paths.extend((absolute, absolute.resolve(strict=False)))
    return tuple(dict.fromkeys(paths))


def _assert_isolated_profile_separate(profile: Path) -> None:
    physical_profile = profile.resolve(strict=False)
    for boundary in _real_profile_boundaries():
        physical_boundary = boundary.resolve(strict=False)
        if physical_profile.is_relative_to(physical_boundary) or physical_boundary.is_relative_to(
            physical_profile
        ):
            raise ClaudeAcceptanceError("isolated profile overlaps real Claude profile boundary")


def _isolated_environment(profile: Path) -> dict[str, str]:
    roots = {
        "CLAUDE_CONFIG_DIR": profile / "config",
        "CLAUDE_CODE_PLUGIN_CACHE_DIR": profile / "plugin-cache",
        "CLAUDE_SECURESTORAGE_CONFIG_DIR": profile / "secure-storage",
        "HOME": profile / "home",
        "TMPDIR": profile / "tmp",
        "TMP": profile / "tmp",
        "TEMP": profile / "tmp",
        "XDG_CACHE_HOME": profile / "xdg-cache",
        "XDG_CONFIG_HOME": profile / "xdg-config",
        "XDG_DATA_HOME": profile / "xdg-data",
    }
    for path in roots.values():
        path.mkdir(parents=True, exist_ok=True)
    environment = {
        name: os.environ[name] for name in _PASSTHROUGH_ENVIRONMENT_NAMES if name in os.environ
    }
    environment.update({name: str(path) for name, path in roots.items()})
    environment["DISABLE_AUTOUPDATER"] = "1"
    return environment


def _claude(
    executable: str,
    environment: dict[str, str],
    cwd: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return _run_process([executable, *arguments], cwd=cwd, env=environment)


def _claude_json(
    executable: str,
    environment: dict[str, str],
    cwd: Path,
    *arguments: str,
) -> Any:
    completed = _claude(executable, environment, cwd, *arguments)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ClaudeAcceptanceError(
            f"Claude command returned invalid JSON: {arguments[:2]!r}"
        ) from error


def _regular_payload_bytes(root: Path) -> dict[str, bytes]:
    """Read a plugin payload fail-closed, rejecting links and non-regular entries."""
    try:
        root_stat = os.lstat(root)
    except OSError as error:
        raise ClaudeAcceptanceError("installed Claude plugin payload is unavailable") from error
    if not stat.S_ISDIR(root_stat.st_mode):
        raise ClaudeAcceptanceError("installed Claude plugin payload is not a directory")

    files: dict[str, bytes] = {}
    pending = [root]
    total = 0
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name, reverse=True)
        except OSError as error:
            raise ClaudeAcceptanceError(
                "could not enumerate installed Claude plugin payload"
            ) from error
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            try:
                entry_stat = os.lstat(path)
            except OSError as error:
                raise ClaudeAcceptanceError(
                    "could not inspect installed Claude plugin payload"
                ) from error
            if stat.S_ISLNK(entry_stat.st_mode):
                raise ClaudeAcceptanceError("installed Claude plugin payload contains a symlink")
            if stat.S_ISDIR(entry_stat.st_mode):
                pending.append(path)
                continue
            if not stat.S_ISREG(entry_stat.st_mode):
                raise ClaudeAcceptanceError(
                    "installed Claude plugin payload has a non-regular entry"
                )
            if entry_stat.st_size > MAX_MEMBER_BYTES:
                raise ClaudeAcceptanceError(
                    "installed Claude plugin payload has an oversized entry"
                )
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(path, flags)
                with os.fdopen(descriptor, "rb") as handle:
                    opened = os.fstat(handle.fileno())
                    content = handle.read(MAX_MEMBER_BYTES + 1)
                    after = os.fstat(handle.fileno())
            except OSError as error:
                raise ClaudeAcceptanceError(
                    "could not read installed Claude plugin payload"
                ) from error
            expected = (
                entry_stat.st_dev,
                entry_stat.st_ino,
                entry_stat.st_size,
                entry_stat.st_mtime_ns,
            )
            if expected != (
                opened.st_dev,
                opened.st_ino,
                opened.st_size,
                opened.st_mtime_ns,
            ) or expected != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                raise ClaudeAcceptanceError("installed Claude plugin payload changed while reading")
            if len(content) > MAX_MEMBER_BYTES or len(content) != entry_stat.st_size:
                raise ClaudeAcceptanceError("installed Claude plugin payload changed while reading")
            total += len(content)
            if total > MAX_EXTRACTED_BYTES:
                raise ClaudeAcceptanceError("installed Claude plugin payload exceeds size limits")
            files[relative] = content
    return dict(sorted(files.items()))


def _assert_installed(
    result: Any,
    release: VerifiedClaudeRelease,
    profile: Path,
    marketplace: Path,
) -> None:
    if not isinstance(result, list):
        raise ClaudeAcceptanceError("claude plugin list --json did not return a list")
    matches = [entry for entry in result if entry.get("id") == release.selector]
    if len(matches) != 1:
        raise ClaudeAcceptanceError("exact Claude plugin selector was not installed once")
    entry = matches[0]
    if entry.get("version") != release.version or entry.get("scope") != "user":
        raise ClaudeAcceptanceError("installed Claude plugin version or scope is not exact")
    if entry.get("enabled") is not True:
        raise ClaudeAcceptanceError("installed Claude plugin is not enabled")
    if entry.get("mcpServers") != {"sensai": {"type": "http", "url": release.mcp_url}}:
        raise ClaudeAcceptanceError("installed Claude plugin MCP URL is not exact")
    raw_install_path = Path(str(entry.get("installPath", "")))
    if not raw_install_path.is_absolute():
        raise ClaudeAcceptanceError("Claude did not report an absolute installed plugin path")
    try:
        raw_stat = os.lstat(raw_install_path)
    except OSError as error:
        raise ClaudeAcceptanceError(
            "Claude reported an unavailable installed plugin path"
        ) from error
    if stat.S_ISLNK(raw_stat.st_mode) or not stat.S_ISDIR(raw_stat.st_mode):
        raise ClaudeAcceptanceError("Claude reported an unsafe installed plugin path")
    expected_cache = profile / "plugin-cache"
    try:
        cache_stat = os.lstat(expected_cache)
    except OSError as error:
        raise ClaudeAcceptanceError("isolated Claude plugin cache is unavailable") from error
    if stat.S_ISLNK(cache_stat.st_mode) or not stat.S_ISDIR(cache_stat.st_mode):
        raise ClaudeAcceptanceError("isolated Claude plugin cache is unsafe")
    if not raw_install_path.is_relative_to(expected_cache):
        raise ClaudeAcceptanceError("Claude installed the plugin outside the isolated cache")
    install_path = raw_install_path.resolve(strict=True)
    cache = expected_cache.resolve(strict=True)
    if not install_path.is_relative_to(cache):
        raise ClaudeAcceptanceError("Claude installed the plugin outside the isolated cache")
    expected_payload = _regular_payload_bytes(marketplace / "plugins" / "sensai")
    actual_payload = _regular_payload_bytes(install_path)
    if actual_payload != expected_payload:
        raise ClaudeAcceptanceError(
            "installed Claude plugin payload differs from verified marketplace payload"
        )


def _assert_mcp_get(completed: subprocess.CompletedProcess[str], mcp_url: str) -> None:
    lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    if lines.count(f"{PLUGIN_MCP_NAME}:") != 1:
        raise ClaudeAcceptanceError("claude mcp get did not report exact plugin details")
    fields: dict[str, str] = {}
    for line in lines:
        key, separator, value = line.partition(":")
        if separator != ":" or key not in {"Type", "URL"}:
            continue
        normalized = value.strip()
        if not normalized or key in fields:
            raise ClaudeAcceptanceError("claude mcp get did not report exact plugin details")
        fields[key] = normalized
    if fields != {"Type": "http", "URL": mcp_url}:
        raise ClaudeAcceptanceError("claude mcp get did not report exact plugin details")


@contextmanager
def installed_claude_plugin(
    bundle: Path,
    *,
    claude_executable: str | None = None,
) -> Iterator[InstalledClaudePlugin]:
    """Install one verified release and keep its isolated Claude profile alive."""
    claude = claude_executable or shutil.which("claude")
    if claude is None:
        raise ClaudeAcceptanceError("claude is required on PATH")
    source = _regular_bundle_path(bundle)
    before = _real_profile_fingerprint()
    source_before = _fingerprint(source)
    profile = Path(
        tempfile.mkdtemp(prefix="sensai-claude-profile-", dir=_temporary_root())
    ).resolve()
    body_error: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    try:
        _assert_isolated_profile_separate(profile)
        environment = _isolated_environment(profile)
        work = profile / "work"
        work.mkdir()
        marketplace = work / "marketplace"
        with _immutable_bundle_snapshot(source, profile) as snapshot:
            snapshot_before = _snapshot_identity(snapshot)
            release = _prepare_verified_marketplace_from_snapshot(snapshot, marketplace)
            if _snapshot_identity(snapshot) != snapshot_before:
                raise ClaudeAcceptanceError(
                    "private release snapshot changed after marketplace preparation"
                )
            marketplace_before = _fingerprint(marketplace)
            _claude(
                claude,
                environment,
                work,
                "plugin",
                "marketplace",
                "add",
                str(marketplace),
            )
            _claude(
                claude,
                environment,
                work,
                "plugin",
                "install",
                release.selector,
                "--scope",
                "user",
            )
            installed = _claude_json(
                claude,
                environment,
                work,
                "plugin",
                "list",
                "--json",
            )
            _assert_installed(installed, release, profile, marketplace)
            mcp = _claude(
                claude,
                environment,
                work,
                "mcp",
                "get",
                PLUGIN_MCP_NAME,
            )
            _assert_mcp_get(mcp, release.mcp_url)
            if _fingerprint(marketplace) != marketplace_before:
                raise ClaudeAcceptanceError("Claude mutated the verified read-only marketplace")
            if _snapshot_identity(snapshot) != snapshot_before:
                raise ClaudeAcceptanceError(
                    "private release snapshot changed after Claude installation"
                )
            if _fingerprint(source) != source_before:
                raise ClaudeAcceptanceError("source release bundle changed during installation")
            try:
                yield InstalledClaudePlugin(
                    release.selector, release.version, release.mcp_url, profile
                )
                if not profile.exists():
                    raise ClaudeAcceptanceError("isolated Claude profile disappeared while in use")
            finally:
                if _snapshot_identity(snapshot) != snapshot_before:
                    raise ClaudeAcceptanceError("private release snapshot changed before cleanup")
    except BaseException as error:
        body_error = error
    finally:
        try:
            remove_readonly_tree(profile)
        except BaseException as error:
            cleanup_errors.append(error)
        try:
            after = _real_profile_fingerprint()
            changed = sorted(set(before) | set(after))
            changed = [key for key in changed if before.get(key) != after.get(key)]
            if changed:
                raise ClaudeAcceptanceError(f"real Claude profile changed: {changed!r}")
        except BaseException as error:
            cleanup_errors.append(error)
        try:
            if _fingerprint(source) != source_before:
                raise ClaudeAcceptanceError("source release bundle changed")
        except BaseException as error:
            cleanup_errors.append(error)
    if body_error is not None and cleanup_errors:
        raise BaseExceptionGroup(
            "Claude acceptance and cleanup failed", [body_error, *cleanup_errors]
        )
    if cleanup_errors:
        raise BaseExceptionGroup("Claude acceptance cleanup failed", cleanup_errors)
    if body_error is not None:
        raise body_error
