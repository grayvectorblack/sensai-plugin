#!/usr/bin/env python3
"""Install one verified Codex release through an isolated local marketplace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import zipfile
from contextlib import suppress
from pathlib import Path, PurePosixPath
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VERIFY_RELEASE = REPOSITORY_ROOT / "scripts" / "verify_release.py"
CODEX_TIMEOUT_SECONDS = 30
TERMINATION_GRACE_SECONDS = 2
MAX_ARCHIVE_MEMBERS = 128
MAX_MEMBER_BYTES = 2 * 1024 * 1024
MAX_EXTRACTED_BYTES = 8 * 1024 * 1024
READ_CHUNK_BYTES = 64 * 1024
PASSTHROUGH_ENVIRONMENT_NAMES = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)
PLUGIN_LIFECYCLE_BOUNDARY = (
    ".tmp/marketplaces",
    "plugins/cache/sensai-local",
)
SENSAI_TMP_PLUGIN_PARENTS = (
    ".tmp/plugins",
    ".tmp/plugins/.agents/plugins",
    ".tmp/plugins/plugins",
)


class LifecycleError(AssertionError):
    """Raised when Codex lifecycle acceptance fails closed."""


def _json_object_bytes(content: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LifecycleError(f"Invalid JSON object: {label}") from error
    if not isinstance(value, dict):
        raise LifecycleError(f"Expected JSON object: {label}")
    return value


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(READ_CHUNK_BYTES):
                digest.update(chunk)
    except OSError as error:
        raise LifecycleError(f"Could not read release file: {path.name}") from error
    return digest.hexdigest()


def _fingerprint(path: Path) -> tuple[tuple[str, str], ...]:
    if not path.exists() and not path.is_symlink():
        return ((".", "missing"),)
    if path.is_symlink():
        return ((".", f"symlink:{os.readlink(path)}"),)
    if path.is_file():
        return ((".", _sha256_file(path)),)

    entries: list[tuple[str, str]] = []
    pending = [path]
    while pending:
        directory = pending.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda child: child.name, reverse=True)
        except OSError as error:
            raise LifecycleError("Could not enumerate real Codex profile") from error
        for child in children:
            child_path = Path(child.path)
            relative = child_path.relative_to(path).as_posix()
            try:
                if child.is_symlink():
                    entries.append((relative, f"symlink:{os.readlink(child.path)}"))
                elif child.is_file(follow_symlinks=False):
                    entries.append((relative, _sha256_file(child_path)))
                elif child.is_dir(follow_symlinks=False):
                    entries.append((relative, "directory"))
                    pending.append(child_path)
                else:
                    entries.append((relative, "other"))
            except OSError as error:
                raise LifecycleError("Could not fingerprint real Codex profile") from error
    return tuple(sorted(entries))


def _real_codex_profile_fingerprint(real_codex_home: Path) -> tuple[Any, ...]:
    """Fingerprint every real-profile path mutable by this plugin lifecycle."""
    configured = real_codex_home.absolute()
    resolved = configured.resolve(strict=False)
    boundary_paths = {resolved / relative for relative in PLUGIN_LIFECYCLE_BOUNDARY}
    if resolved.is_dir():
        boundary_paths.update(resolved.glob("config.toml*"))
        boundary_paths.update(resolved.glob(".codex-global-state.json*"))
        boundary_paths.update(resolved.glob("..codex-global-state.json.tmp-*"))
    boundary = tuple(
        (
            path.relative_to(resolved).as_posix(),
            _fingerprint(path),
        )
        for path in sorted(boundary_paths)
    )
    tmp_plugins = _sensai_tmp_plugins_fingerprint(resolved)
    if configured.is_symlink():
        return (
            ("configured", f"symlink:{os.readlink(configured)}"),
            ("resolved", str(resolved)),
            boundary,
            tmp_plugins,
        )
    return (("configured", "direct"), boundary, tmp_plugins)


def _sensai_tmp_plugins_fingerprint(resolved_codex_home: Path) -> tuple[Any, ...]:
    parents: list[tuple[Any, ...]] = []
    for relative in SENSAI_TMP_PLUGIN_PARENTS:
        parent = resolved_codex_home / relative
        if parent.is_symlink():
            parents.append((relative, f"symlink:{os.readlink(parent)}"))
            continue
        if not parent.exists():
            parents.append((relative, "missing"))
            continue
        if not parent.is_dir():
            parents.append((relative, "not-directory", _fingerprint(parent)))
            continue
        try:
            owned = sorted(
                Path(entry.path)
                for entry in os.scandir(parent)
                if "sensai" in entry.name.casefold()
            )
        except OSError as error:
            raise LifecycleError("Could not enumerate Sensai plugin staging boundary") from error
        parents.append(
            (
                relative,
                "directory",
                tuple((path.name, _fingerprint(path)) for path in owned),
            )
        )
    return tuple(parents)


def _run(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: Path = REPOSITORY_ROOT,
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
        stdout, stderr = process.communicate(timeout=CODEX_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=TERMINATION_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        raise LifecycleError(f"Command timed out: {command[0]} {command[1]}") from error
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _verify_release(bundle: Path) -> dict[str, Any]:
    completed = _run(
        [sys.executable, str(VERIFY_RELEASE), "--bundle", str(bundle)],
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "independent verifier rejected the bundle"
        raise LifecycleError(detail)
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise LifecycleError("Independent verifier returned invalid JSON") from error
    if not isinstance(value, dict) or value.get("verified") is not True:
        raise LifecycleError("Independent verifier did not confirm the release")
    return value


def _read_release(bundle: Path) -> tuple[bytes, dict[str, Any]]:
    release_path = bundle / "release.json"
    if release_path.is_symlink() or not release_path.is_file():
        raise LifecycleError("Release metadata is not a regular file")
    content = release_path.read_bytes()
    return content, _json_object_bytes(content, "release.json")


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
        raise LifecycleError(f"Unsafe archive member: {name!r}")
    return relative


def _extract_codex_archive(
    *,
    bundle: Path,
    release: dict[str, Any],
    destination: Path,
) -> dict[str, bytes]:
    platforms = release.get("platforms")
    if not isinstance(platforms, dict) or not isinstance(platforms.get("codex"), dict):
        raise LifecycleError("Release has no Codex platform metadata")
    codex = platforms["codex"]
    archive_name = codex.get("archive")
    expected_archive_digest = codex.get("archive_sha256")
    expected_files = codex.get("files")
    if (
        not isinstance(archive_name, str)
        or PurePosixPath(archive_name).name != archive_name
        or not isinstance(expected_archive_digest, str)
        or not isinstance(expected_files, dict)
        or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in expected_files.items()
        )
    ):
        raise LifecycleError("Invalid Codex release metadata")
    archive_path = bundle / archive_name
    if archive_path.is_symlink() or not archive_path.is_file():
        raise LifecycleError("Codex archive is not a regular file")
    if _sha256_file(archive_path) != expected_archive_digest:
        raise LifecycleError("Codex archive changed after independent verification")

    actual: dict[str, bytes] = {}
    total = 0
    try:
        opened = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as error:
        raise LifecycleError("Could not open verified Codex archive") from error
    with opened:
        members = opened.infolist()
        if len(members) > MAX_ARCHIVE_MEMBERS:
            raise LifecycleError("Codex archive contains too many members")
        for member in members:
            relative = _safe_member(member.filename)
            mode = member.external_attr >> 16
            if (
                member.filename in actual
                or member.is_dir()
                or not stat.S_ISREG(mode)
                or stat.S_IMODE(mode) != 0o444
                or member.file_size > MAX_MEMBER_BYTES
            ):
                raise LifecycleError(f"Unsafe Codex archive member: {member.filename}")
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            content = bytearray()
            try:
                with opened.open(member) as source, target.open("xb") as output:
                    while chunk := source.read(READ_CHUNK_BYTES):
                        total += len(chunk)
                        if (
                            total > MAX_EXTRACTED_BYTES
                            or len(content) + len(chunk) > MAX_MEMBER_BYTES
                        ):
                            raise LifecycleError("Codex archive exceeds extraction limits")
                        content.extend(chunk)
                        output.write(chunk)
            except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                raise LifecycleError(
                    f"Could not extract Codex member: {member.filename}"
                ) from error
            if len(content) != member.file_size:
                raise LifecycleError(f"Codex member size changed: {member.filename}")
            target.chmod(0o444)
            actual[member.filename] = bytes(content)
    if _sha256_file(archive_path) != expected_archive_digest:
        raise LifecycleError("Codex archive changed during extraction")
    actual_digests = {name: _sha256_bytes(content) for name, content in actual.items()}
    if actual_digests != expected_files:
        raise LifecycleError("Extracted Codex bytes do not match release metadata")
    return actual


def _verify_manifest_and_attestation(files: dict[str, bytes], release: dict[str, Any]) -> None:
    prefix = "plugins/sensai/"
    manifest_name = prefix + "MANIFEST.sha256"
    manifest = files.get(manifest_name)
    if manifest is None:
        raise LifecycleError("Codex plugin MANIFEST.sha256 is missing")
    expected_lines = "".join(
        f"{_sha256_bytes(content)}  {name.removeprefix(prefix)}\n"
        for name, content in sorted(files.items())
        if name.startswith(prefix) and name != manifest_name
    ).encode()
    if manifest != expected_lines:
        raise LifecycleError("Codex plugin MANIFEST.sha256 does not match extracted bytes")

    attestation = _json_object_bytes(
        files.get(prefix + "sensai-mcp-attestation.json", b""),
        "sensai-mcp-attestation.json",
    )
    expected_attestation = {
        "format_version": "1",
        "mcp_contract_version": release.get("mcp_contract_version"),
        "mcp_schema_sha256": release.get("mcp_schema_sha256"),
        "mcp_url": release.get("mcp_url"),
    }
    if attestation != expected_attestation:
        raise LifecycleError("Codex MCP attestation does not match release metadata")


def _make_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_dir():
            path.chmod(0o555)
        elif path.is_file():
            path.chmod(0o444)
    root.chmod(0o555)


def _isolated_environment(profile: Path) -> dict[str, str]:
    environment = {
        name: os.environ[name] for name in PASSTHROUGH_ENVIRONMENT_NAMES if name in os.environ
    }
    environment.update(
        {
            "CODEX_HOME": str(profile / "codex-home"),
            "HOME": str(profile / "home"),
            "TMPDIR": str(profile / "tmp"),
            "TMP": str(profile / "tmp"),
            "TEMP": str(profile / "tmp"),
            "XDG_CACHE_HOME": str(profile / "xdg-cache"),
            "XDG_CONFIG_HOME": str(profile / "xdg-config"),
            "XDG_DATA_HOME": str(profile / "xdg-data"),
        }
    )
    for value in environment.values():
        if "\x00" in value:
            raise LifecycleError("Unsafe environment value")
    return environment


def _run_codex_json(
    codex: str,
    environment: dict[str, str],
    profile: Path,
    *arguments: str,
) -> Any:
    completed = _run([codex, *arguments], env=environment, cwd=profile)
    if completed.returncode != 0:
        raise LifecycleError(
            f"Codex command failed: codex {' '.join(arguments[:3])}\n{completed.stderr.strip()}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise LifecycleError(
            f"Codex command returned invalid JSON: {' '.join(arguments)}"
        ) from error


def _plugin_contract(files: dict[str, bytes]) -> tuple[str, str, str]:
    marketplace = _json_object_bytes(files[".agents/plugins/marketplace.json"], "marketplace.json")
    marketplace_name = marketplace.get("name")
    plugins = marketplace.get("plugins")
    manifest = _json_object_bytes(
        files["plugins/sensai/.codex-plugin/plugin.json"],
        "plugin.json",
    )
    mcp = _json_object_bytes(files["plugins/sensai/.mcp.json"], ".mcp.json")
    if not isinstance(plugins, list) or len(plugins) != 1 or not isinstance(plugins[0], dict):
        raise LifecycleError("Codex marketplace must contain exactly one plugin")
    try:
        listed_name = plugins[0]["name"]
        version = manifest["version"]
        mcp_url = mcp["mcpServers"]["sensai"]["url"]
    except (IndexError, KeyError, TypeError) as error:
        raise LifecycleError("Codex marketplace contract is incomplete") from error
    if (
        not isinstance(marketplace_name, str)
        or not isinstance(listed_name, str)
        or not isinstance(version, str)
        or not isinstance(mcp_url, str)
        or listed_name != manifest.get("name")
    ):
        raise LifecycleError("Codex marketplace contract is inconsistent")
    return f"{listed_name}@{marketplace_name}", version, mcp_url


def _assert_installed(result: Any, *, profile: Path, version: str, source: Path) -> None:
    if not isinstance(result, dict) or result.get("version") != version:
        raise LifecycleError(f"Codex did not install exact plugin version {version}")
    installed_value = result.get("installedPath")
    if not isinstance(installed_value, str):
        raise LifecycleError("Codex did not report an installed plugin path")
    installed = Path(installed_value).resolve()
    if not installed.is_relative_to((profile / "codex-home").resolve()):
        raise LifecycleError("Codex installed the plugin outside the isolated profile")
    if _fingerprint(installed) != _fingerprint(source):
        raise LifecycleError("Codex mutated plugin bytes while installing")


def _assert_mcp(result: Any, expected_url: str) -> None:
    if not isinstance(result, list):
        raise LifecycleError("codex mcp list --json did not return a list")
    matching = [item for item in result if isinstance(item, dict) and item.get("name") == "sensai"]
    if len(matching) != 1:
        raise LifecycleError("Codex did not expose exactly one Sensai MCP server")
    transport = matching[0].get("transport")
    if (
        not isinstance(transport, dict)
        or transport.get("type") != "streamable_http"
        or transport.get("url") != expected_url
    ):
        raise LifecycleError("Codex MCP URL does not match the verified release")


def _run_lifecycle(codex: str, bundle: Path, profile: Path) -> tuple[str, str, str]:
    release_before, release = _read_release(bundle)
    archive_name = release.get("platforms", {}).get("codex", {}).get("archive")
    if not isinstance(archive_name, str):
        raise LifecycleError("Release has no Codex archive name")
    archive_before = _sha256_file(bundle / archive_name)
    verified = _verify_release(bundle)
    if verified.get("release_version") != release.get("release_version"):
        raise LifecycleError("Verifier and release metadata disagree on version")
    if (bundle / "release.json").read_bytes() != release_before:
        raise LifecycleError("Release metadata changed during independent verification")
    if _sha256_file(bundle / archive_name) != archive_before:
        raise LifecycleError("Codex archive changed during independent verification")

    marketplace = profile / "marketplace"
    marketplace.mkdir(parents=True)
    extracted = _extract_codex_archive(bundle=bundle, release=release, destination=marketplace)
    _verify_manifest_and_attestation(extracted, release)
    selector, version, mcp_url = _plugin_contract(extracted)
    if (
        version != release.get("release_version")
        or mcp_url != release.get("mcp_url")
        or mcp_url != release["platforms"]["codex"].get("mcp_url")
    ):
        raise LifecycleError("Codex selector, version, or MCP URL does not match release metadata")
    _make_read_only(marketplace)

    for relative in (
        "codex-home",
        "home",
        "tmp",
        "xdg-cache",
        "xdg-config",
        "xdg-data",
    ):
        (profile / relative).mkdir()
    environment = _isolated_environment(profile)
    marketplace_result = _run_codex_json(
        codex,
        environment,
        profile,
        "plugin",
        "marketplace",
        "add",
        str(marketplace),
        "--json",
    )
    if (
        not isinstance(marketplace_result, dict)
        or marketplace_result.get("marketplaceName") != selector.split("@", 1)[1]
    ):
        raise LifecycleError("Codex registered a different marketplace")
    installed = _run_codex_json(
        codex,
        environment,
        profile,
        "plugin",
        "add",
        selector,
        "--json",
    )
    _assert_installed(
        installed,
        profile=profile,
        version=version,
        source=marketplace / "plugins" / "sensai",
    )
    _assert_mcp(
        _run_codex_json(codex, environment, profile, "mcp", "list", "--json"),
        mcp_url,
    )
    if (bundle / "release.json").read_bytes() != release_before or _sha256_file(
        bundle / archive_name
    ) != archive_before:
        raise LifecycleError("Release bundle was mutated during Codex lifecycle")
    return selector, version, mcp_url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    arguments = parser.parse_args()
    bundle = arguments.bundle.resolve()
    codex = shutil.which("codex")
    if codex is None:
        parser.error("codex is required on PATH")

    real_codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).absolute()
    real_before = _real_codex_profile_fingerprint(real_codex_home)
    temporary_path: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="sensai-codex-lifecycle-") as temporary:
            temporary_path = Path(temporary).resolve()
            if temporary_path.is_relative_to(real_codex_home) or real_codex_home.is_relative_to(
                temporary_path
            ):
                raise LifecycleError("Isolated profile overlaps the real Codex profile")
            selector, version, mcp_url = _run_lifecycle(codex, bundle, temporary_path)
    except LifecycleError as error:
        parser.exit(1, f"codex lifecycle failed: {error}\n")
    if temporary_path is None or temporary_path.exists():
        parser.exit(1, "codex lifecycle failed: isolated profile was not removed\n")
    if _real_codex_profile_fingerprint(real_codex_home) != real_before:
        parser.exit(1, "codex lifecycle failed: real Codex profile changed\n")

    print(f"PASS selector={selector}")
    print(f"PASS version={version}")
    print(f"PASS mcp={mcp_url}")
    print("PASS verified-release=independent exact-bytes=read-only")
    print("PASS isolated-profile=removed real-plugin-lifecycle-boundary=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
