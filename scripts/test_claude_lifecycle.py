#!/usr/bin/env python3
"""Install one verified Sensai release with Claude Code in an isolated profile."""

from __future__ import annotations

import argparse
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

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFY_RELEASE = REPOSITORY_ROOT / "scripts" / "verify_release.py"
EXPECTED_CLAUDE_VERSION = "2.1.193 (Claude Code)"
CLAUDE_TIMEOUT_SECONDS = 45
CLAUDE_TERMINATION_GRACE_SECONDS = 2
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


class LifecycleError(RuntimeError):
    """Raised when the release or isolated Claude lifecycle is not exact."""


@dataclass(frozen=True)
class VerifiedClaudeRelease:
    marketplace: Path
    selector: str
    version: str
    mcp_url: str
    mcp_attestation: dict[str, str]
    files: dict[str, str]


def _emit(message: str) -> None:
    print(message, flush=True)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LifecycleError(f"invalid JSON document: {path.name}") from error
    if not isinstance(value, dict):
        raise LifecycleError(f"expected JSON object: {path.name}")
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
        raise LifecycleError(f"command timed out: {command[:3]!r}") from error
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check and completed.returncode != 0:
        raise LifecycleError(
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
        raise LifecycleError(f"release verification failed: {detail}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise LifecycleError("release verifier returned invalid JSON") from error
    if not isinstance(result, dict) or result.get("verified") is not True:
        raise LifecycleError("release verifier did not attest success")
    return result


def _set_tree_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_symlink():
            raise LifecycleError(f"read-only tree contains a symlink: {path}")
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)
    writable = [
        path
        for path in (root, *root.rglob("*"))
        if path.stat().st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
    ]
    if writable:
        raise LifecycleError("filesystem did not enforce read-only marketplace permissions")


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
        raise LifecycleError("Claude lifecycle temporary root is not a directory")
    return root


@contextmanager
def _immutable_bundle_snapshot(bundle: Path, parent: Path) -> Iterator[Path]:
    if bundle.is_symlink() or not bundle.is_dir():
        raise LifecycleError("release bundle must be a regular directory")
    parent.mkdir(parents=True, exist_ok=True)
    snapshot_root = Path(tempfile.mkdtemp(prefix=".sensai-claude-snapshot-", dir=parent))
    snapshot = snapshot_root / "bundle"
    snapshot.mkdir()
    try:
        entries = sorted(bundle.iterdir())
        if not entries:
            raise LifecycleError("release bundle is empty")
        for source in entries:
            if source.is_symlink() or not source.is_file():
                raise LifecycleError(f"release bundle contains a non-regular entry: {source.name}")
            target = snapshot / source.name
            with source.open("rb") as input_file, target.open("xb") as output_file:
                shutil.copyfileobj(input_file, output_file, length=64 * 1024)
        _set_tree_read_only(snapshot)
        yield snapshot
    finally:
        remove_readonly_tree(snapshot_root)


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
        raise LifecycleError(f"unsafe archive path: {name!r}")
    return relative


def _extract_exact_archive(
    archive_path: Path,
    destination: Path,
    expected_files: dict[str, str],
) -> dict[str, str]:
    if destination.exists() or destination.is_symlink():
        raise LifecycleError("marketplace extraction destination already exists")
    destination.mkdir(parents=True)
    actual: dict[str, str] = {}
    total = 0
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_MEMBERS:
                raise LifecycleError("archive member count exceeds limit")
            seen: set[str] = set()
            for info in members:
                relative = _safe_member(info.filename)
                if info.filename in seen:
                    raise LifecycleError(f"duplicate archive path: {info.filename}")
                seen.add(info.filename)
                mode = info.external_attr >> 16
                if info.is_dir() or not stat.S_ISREG(mode):
                    raise LifecycleError(f"archive entry is not a regular file: {info.filename}")
                if info.file_size > MAX_MEMBER_BYTES:
                    raise LifecycleError("archive member exceeds size limit")
                total += info.file_size
                if total > MAX_EXTRACTED_BYTES:
                    raise LifecycleError("archive extracted bytes exceed size limit")
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
        raise LifecycleError("could not safely extract Claude marketplace archive") from error
    if actual != expected_files:
        raise LifecycleError("extracted Claude marketplace bytes do not match release metadata")
    return actual


def _manifest_entries(manifest: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if separator != "  " or _SHA256.fullmatch(digest) is None:
            raise LifecycleError("Claude plugin MANIFEST.sha256 is malformed")
        if relative in entries or _safe_member(relative).as_posix() != relative:
            raise LifecycleError("Claude plugin MANIFEST.sha256 contains an unsafe path")
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
        raise LifecycleError("extracted Claude plugin does not match MANIFEST.sha256")

    marketplace_manifest = _load_object(marketplace / ".claude-plugin" / "marketplace.json")
    if marketplace_manifest.get("name") != "sensai-local":
        raise LifecycleError("unexpected Claude marketplace name")
    plugins = marketplace_manifest.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        raise LifecycleError("Claude marketplace must contain exactly one plugin")
    plugin_entry = plugins[0]
    if not isinstance(plugin_entry, dict) or plugin_entry.get("name") != "sensai":
        raise LifecycleError("unexpected Claude marketplace plugin selector")
    if plugin_entry.get("source") != "./plugins/sensai":
        raise LifecycleError("Claude marketplace plugin source is not exact")

    attestation_value = _load_object(plugin / "sensai-mcp-attestation.json")
    attestation = {key: str(value) for key, value in attestation_value.items()}
    expected_attestation = {
        "format_version": "1",
        "mcp_contract_version": str(metadata["mcp_contract_version"]),
        "mcp_schema_sha256": str(metadata["mcp_schema_sha256"]),
        "mcp_url": str(metadata["mcp_url"]),
    }
    if attestation != expected_attestation:
        raise LifecycleError("Claude MCP attestation does not match release metadata")
    return "sensai@sensai-local", attestation


def prepare_verified_marketplace(bundle: Path, destination: Path) -> VerifiedClaudeRelease:
    """Verify an existing bundle, then extract its exact Claude archive once."""
    bundle = bundle.resolve(strict=True)
    try:
        with _immutable_bundle_snapshot(bundle, destination.parent) as snapshot:
            snapshot_fingerprint = _fingerprint(snapshot)
            verification = _verify_release_independently(snapshot)
            if _fingerprint(snapshot) != snapshot_fingerprint:
                raise LifecycleError("immutable release snapshot changed after verification")
            metadata = _load_object(snapshot / "release.json")
            claude = metadata.get("platforms", {}).get("claude")
            if not isinstance(claude, dict):
                raise LifecycleError("release metadata has no Claude platform")
            files = claude.get("files")
            if not isinstance(files, dict) or not files:
                raise LifecycleError("Claude release has no file manifest")
            expected_files = {str(path): str(digest) for path, digest in files.items()}
            archive_name = claude.get("archive")
            if (
                not isinstance(archive_name, str)
                or PurePosixPath(archive_name).name != archive_name
            ):
                raise LifecycleError("Claude archive path is unsafe")
            if verification.get("release_version") != metadata.get("release_version"):
                raise LifecycleError("release verifier version does not match metadata")
            if verification.get("mcp_url") != metadata.get("mcp_url"):
                raise LifecycleError("release verifier MCP URL does not match metadata")

            actual_files = _extract_exact_archive(
                snapshot / archive_name,
                destination,
                expected_files,
            )
            selector, attestation = _verify_extracted_payload(destination, metadata)
            if _fingerprint(snapshot) != snapshot_fingerprint:
                raise LifecycleError("immutable release snapshot changed during extraction")
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
        raise LifecycleError(f"Claude command returned invalid JSON: {arguments[:2]!r}") from error


def _assert_installed(result: Any, release: VerifiedClaudeRelease, profile: Path) -> None:
    if not isinstance(result, list):
        raise LifecycleError("claude plugin list --json did not return a list")
    matches = [entry for entry in result if entry.get("id") == release.selector]
    if len(matches) != 1:
        raise LifecycleError("exact Claude plugin selector was not installed once")
    entry = matches[0]
    if entry.get("version") != release.version or entry.get("scope") != "user":
        raise LifecycleError("installed Claude plugin version or scope is not exact")
    if entry.get("enabled") is not True:
        raise LifecycleError("installed Claude plugin is not enabled")
    if entry.get("mcpServers") != {"sensai": {"type": "http", "url": release.mcp_url}}:
        raise LifecycleError("installed Claude plugin MCP URL is not exact")
    install_path = Path(str(entry.get("installPath", ""))).resolve(strict=True)
    if not install_path.is_relative_to((profile / "plugin-cache").resolve()):
        raise LifecycleError("Claude installed the plugin outside the isolated cache")


def _assert_mcp_get(completed: subprocess.CompletedProcess[str], mcp_url: str) -> None:
    output = completed.stdout + completed.stderr
    expected = (
        f"{PLUGIN_MCP_NAME}:",
        "Type: http",
        f"URL: {mcp_url}",
    )
    if missing := [value for value in expected if value not in output]:
        raise LifecycleError(f"claude mcp get omitted exact plugin details: {missing!r}")


def run_lifecycle(bundle: Path, claude_executable: str) -> None:
    before = _real_profile_fingerprint()
    profile = Path(
        tempfile.mkdtemp(prefix="sensai-claude-profile-", dir=_temporary_root())
    ).resolve()
    try:
        environment = _isolated_environment(profile)
        work = profile / "work"
        work.mkdir()
        marketplace = work / "marketplace"
        release = prepare_verified_marketplace(bundle, marketplace)
        marketplace_before = _fingerprint(marketplace)

        version = _claude(claude_executable, environment, work, "--version").stdout.strip()
        if version != EXPECTED_CLAUDE_VERSION:
            raise LifecycleError(
                f"expected Claude CLI {EXPECTED_CLAUDE_VERSION!r}, observed {version!r}"
            )
        _claude(
            claude_executable,
            environment,
            work,
            "plugin",
            "marketplace",
            "add",
            str(marketplace),
        )
        _claude(
            claude_executable,
            environment,
            work,
            "plugin",
            "install",
            release.selector,
            "--scope",
            "user",
        )
        installed = _claude_json(
            claude_executable,
            environment,
            work,
            "plugin",
            "list",
            "--json",
        )
        _assert_installed(installed, release, profile)
        mcp = _claude(
            claude_executable,
            environment,
            work,
            "mcp",
            "get",
            PLUGIN_MCP_NAME,
        )
        _assert_mcp_get(mcp, release.mcp_url)
        if _fingerprint(marketplace) != marketplace_before:
            raise LifecycleError("Claude mutated the verified read-only marketplace")
        _emit(
            f"PASS selector={release.selector} version={release.version} mcp_url={release.mcp_url}"
        )
        _emit("PASS release=verified archive=extracted-once marketplace=unchanged")
    finally:
        remove_readonly_tree(profile)
        after = _real_profile_fingerprint()
        changed = sorted(set(before) | set(after))
        changed = [key for key in changed if before.get(key) != after.get(key)]
        if changed:
            raise LifecycleError(f"real Claude profile changed: {changed!r}")
    _emit("PASS isolated-profile=deleted real-profile=unchanged")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    arguments = parser.parse_args()
    claude = shutil.which("claude")
    if claude is None:
        parser.error("claude is required on PATH")
    try:
        run_lifecycle(arguments.bundle, claude)
    except (LifecycleError, FileNotFoundError) as error:
        parser.exit(1, f"Claude lifecycle failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
