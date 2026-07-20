"""Independent verification of an untrusted Sensai local release bundle."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from itertools import islice
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_PLATFORMS = ("claude", "codex")
_ARCHIVE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_MAX_BUNDLE_BYTES = 20 * 1024 * 1024
_MAX_BUNDLE_ENTRIES = 3
_MAX_METADATA_BYTES = 1024 * 1024
_MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
_MAX_ARCHIVE_MEMBERS = 128
_MAX_MEMBER_BYTES = 2 * 1024 * 1024
_MAX_EXTRACTED_BYTES = 8 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_MARKETPLACE_NAME = "sensai-local"
_TRUSTED_SOURCE_FILES = frozenset(
    {
        "shared/.mcp.json",
        "shared/skills/sensai/SKILL.md",
        "codex/.codex-plugin/plugin.json",
        "claude/.claude-plugin/plugin.json",
    }
)
_TRUSTED_SOURCE_DIRECTORIES = frozenset(
    {
        "shared",
        "shared/skills",
        "shared/skills/sensai",
        "codex",
        "codex/.codex-plugin",
        "claude",
        "claude/.claude-plugin",
    }
)
_METADATA_FIELDS = {
    "format_version",
    "mcp_contract_version",
    "mcp_schema_sha256",
    "mcp_url",
    "platforms",
    "release_version",
}
_PLATFORM_FIELDS = {
    "archive",
    "archive_sha256",
    "files",
    "mcp_url",
    "plugin_version",
}


class ReleaseVerificationError(ValueError):
    """Raised when release bytes do not match the public release contract."""


def _read_limited(path: Path, maximum: int, label: str) -> bytes:
    try:
        size = path.stat().st_size
        if size > maximum:
            raise ReleaseVerificationError(f"{label} exceeds size limit")
        chunks: list[bytes] = []
        total = 0
        with path.open("rb") as handle:
            while chunk := handle.read(_READ_CHUNK_BYTES):
                total += len(chunk)
                if total > maximum:
                    raise ReleaseVerificationError(f"{label} exceeds size limit")
                chunks.append(chunk)
        return b"".join(chunks)
    except OSError as error:
        raise ReleaseVerificationError(f"Could not read {label}") from error


def _object(path: Path, *, maximum: int = _MAX_METADATA_BYTES) -> dict[str, Any]:
    try:
        value = json.loads(_read_limited(path, maximum, path.name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseVerificationError(f"Invalid JSON document: {path.name}") from error
    if not isinstance(value, dict):
        raise ReleaseVerificationError(f"Expected JSON object: {path.name}")
    return value


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(path: Path, maximum: int, label: str) -> str:
    digest = hashlib.sha256()
    try:
        size = path.stat().st_size
        if size > maximum:
            raise ReleaseVerificationError(f"{label} exceeds size limit")
        total = 0
        with path.open("rb") as handle:
            while chunk := handle.read(_READ_CHUNK_BYTES):
                total += len(chunk)
                if total > maximum:
                    raise ReleaseVerificationError(f"{label} exceeds size limit")
                digest.update(chunk)
    except OSError as error:
        raise ReleaseVerificationError(f"Could not read {label}") from error
    return digest.hexdigest()


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseVerificationError(f"Metadata field must be a non-empty string: {field}")
    return value


def _sha256(value: object, field: str) -> str:
    text = _string(value, field)
    if _SHA256.fullmatch(text) is None:
        raise ReleaseVerificationError(f"Metadata field must be lowercase SHA-256: {field}")
    return text


def _safe_relative(value: object, field: str) -> str:
    text = _string(value, field)
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts or "\\" in text or len(path.parts) != 1:
        raise ReleaseVerificationError(f"Unsafe bundle-relative path: {field}")
    return text


def _safe_member(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or name.endswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or any(part in {"", "."} for part in path.parts)
    ):
        raise ReleaseVerificationError(f"Unsafe archive path: {name!r}")
    return path


def _validate_mcp_url(mcp_url: str) -> None:
    parsed = urlsplit(mcp_url)
    try:
        _ = parsed.port
    except ValueError as error:
        raise ReleaseVerificationError("Release contains an unsafe MCP URL") from error
    if (
        any(ord(character) <= 32 or ord(character) == 127 for character in mcp_url)
        or "\\" in mcp_url
        or parsed.geturl() != mcp_url
        or parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/")
    ):
        raise ReleaseVerificationError("Release contains an unsafe MCP URL")


def _extract_archive(archive_path: Path, destination: Path) -> dict[str, bytes]:
    actual: dict[str, bytes] = {}
    try:
        archive = zipfile.ZipFile(archive_path)
    except (OSError, zipfile.BadZipFile) as error:
        raise ReleaseVerificationError(f"Invalid archive: {archive_path.name}") from error
    with archive:
        members = archive.infolist()
        if len(members) > _MAX_ARCHIVE_MEMBERS:
            raise ReleaseVerificationError("Archive member count exceeds limit")
        declared_total = 0
        for info in members:
            if info.file_size > _MAX_MEMBER_BYTES:
                raise ReleaseVerificationError("Archive member exceeds size limit")
            declared_total += info.file_size
            if declared_total > _MAX_EXTRACTED_BYTES:
                raise ReleaseVerificationError("Archive extracted bytes exceed size limit")
        seen: set[str] = set()
        extracted_total = 0
        for info in members:
            relative = _safe_member(info.filename)
            if info.filename in seen:
                raise ReleaseVerificationError(f"Duplicate archive path: {info.filename}")
            seen.add(info.filename)
            mode = info.external_attr >> 16
            if (
                info.is_dir()
                or not stat.S_ISREG(mode)
                or stat.S_IMODE(mode) != 0o444
                or info.date_time != _ARCHIVE_TIMESTAMP
                or info.compress_type != zipfile.ZIP_STORED
            ):
                raise ReleaseVerificationError(
                    f"Archive member metadata is not canonical and read-only: {info.filename}"
                )
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                content = bytearray()
                with archive.open(info, "r") as source, target.open("xb") as output:
                    while chunk := source.read(_READ_CHUNK_BYTES):
                        extracted_total += len(chunk)
                        if len(content) + len(chunk) > _MAX_MEMBER_BYTES:
                            raise ReleaseVerificationError("Archive member exceeds size limit")
                        if extracted_total > _MAX_EXTRACTED_BYTES:
                            raise ReleaseVerificationError(
                                "Archive extracted bytes exceed size limit"
                            )
                        content.extend(chunk)
                        output.write(chunk)
            except (OSError, RuntimeError, zipfile.BadZipFile) as error:
                raise ReleaseVerificationError(
                    f"Could not extract archive member: {info.filename}"
                ) from error
            if len(content) != info.file_size:
                raise ReleaseVerificationError("Archive member size changed during extraction")
            actual[info.filename] = bytes(content)
    return actual


def _document_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _trusted_source_bytes(repository_root: Path) -> dict[str, bytes]:
    source_root = repository_root / "payload-src"
    if source_root.is_symlink() or not source_root.is_dir():
        raise ReleaseVerificationError("Trusted plugin source root is unsafe")
    files: set[str] = set()
    directories: set[str] = set()
    for current_root, directory_names, file_names in os.walk(source_root, followlinks=False):
        current = Path(current_root)
        for name in sorted((*directory_names, *file_names)):
            entry = current / name
            relative = entry.relative_to(source_root).as_posix()
            mode = entry.lstat().st_mode
            if stat.S_ISLNK(mode):
                raise ReleaseVerificationError("Trusted plugin source contains a symlink")
            if stat.S_ISDIR(mode):
                directories.add(relative)
            elif stat.S_ISREG(mode):
                files.add(relative)
            else:
                raise ReleaseVerificationError("Trusted plugin source contains an unsafe entry")
    if files != _TRUSTED_SOURCE_FILES or directories != _TRUSTED_SOURCE_DIRECTORIES:
        raise ReleaseVerificationError("Trusted plugin source does not match its allowlist")
    return {
        relative: _read_limited(
            source_root / relative,
            _MAX_MEMBER_BYTES,
            "trusted plugin source file",
        )
        for relative in sorted(files)
    }


def _json_bytes_object(content: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReleaseVerificationError(f"Invalid trusted plugin source JSON: {label}") from error
    if not isinstance(value, dict):
        raise ReleaseVerificationError(f"Invalid trusted plugin source JSON: {label}")
    return value


def _expected_marketplace_bytes(
    source: dict[str, bytes],
    *,
    platform: str,
    mcp_url: str,
) -> dict[str, bytes]:
    mcp = _json_bytes_object(source["shared/.mcp.json"], "shared/.mcp.json")
    servers = mcp.get("mcpServers")
    if not isinstance(servers, dict) or set(servers) != {"sensai"}:
        raise ReleaseVerificationError("Trusted MCP source has an unexpected server set")
    sensai = servers["sensai"]
    if not isinstance(sensai, dict):
        raise ReleaseVerificationError("Trusted Sensai MCP source is invalid")
    sensai["url"] = mcp_url
    plugin_manifest_relative = f"{platform}/.{platform}-plugin/plugin.json"
    payload: dict[str, bytes] = {
        f".{platform}-plugin/plugin.json": source[plugin_manifest_relative],
        ".mcp.json": _document_json(mcp),
        "skills/sensai/SKILL.md": source["shared/skills/sensai/SKILL.md"],
    }
    payload["MANIFEST.sha256"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {relative}\n"
        for relative, content in sorted(payload.items())
    ).encode()
    result = {f"plugins/sensai/{relative}": content for relative, content in payload.items()}
    if platform == "codex":
        marketplace_path = ".agents/plugins/marketplace.json"
        marketplace: dict[str, Any] = {
            "name": _MARKETPLACE_NAME,
            "plugins": [
                {
                    "name": "sensai",
                    "policy": {"installation": "AVAILABLE"},
                    "source": {"path": "./plugins/sensai", "source": "local"},
                }
            ],
        }
    else:
        marketplace_path = ".claude-plugin/marketplace.json"
        marketplace = {
            "description": "Local immutable Sensai release marketplace.",
            "name": _MARKETPLACE_NAME,
            "owner": {"name": "Sensai"},
            "plugins": [
                {
                    "description": "Sensai guidance plugin.",
                    "name": "sensai",
                    "source": "./plugins/sensai",
                }
            ],
        }
    result[marketplace_path] = _document_json(marketplace)
    return dict(sorted(result.items()))


def _expected_files(value: object, platform: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ReleaseVerificationError(f"Missing extracted file manifest: {platform}")
    result: dict[str, str] = {}
    for raw_path, raw_digest in value.items():
        if not isinstance(raw_path, str):
            raise ReleaseVerificationError(f"Invalid extracted file path: {platform}")
        relative = _safe_member(raw_path)
        result[relative.as_posix()] = _sha256(raw_digest, f"{platform}.files.{raw_path}")
    return result


def _verify_marketplace(
    root: Path,
    *,
    platform: str,
    version: str,
    mcp_url: str,
) -> None:
    plugin_root = root / "plugins" / "sensai"
    plugin_manifest = _object(plugin_root / f".{platform}-plugin" / "plugin.json")
    if plugin_manifest.get("name") != "sensai" or plugin_manifest.get("version") != version:
        raise ReleaseVerificationError(f"Unexpected {platform} plugin identity or version")
    mcp = _object(plugin_root / ".mcp.json")
    servers = mcp.get("mcpServers")
    if not isinstance(servers, dict) or set(servers) != {"sensai"}:
        raise ReleaseVerificationError(f"Unexpected {platform} MCP server set")
    sensai = servers["sensai"]
    if not isinstance(sensai, dict) or sensai.get("url") != mcp_url:
        raise ReleaseVerificationError(f"Unexpected {platform} MCP URL")

    if platform == "codex":
        marketplace = _object(root / ".agents" / "plugins" / "marketplace.json")
        expected_source: object = {"path": "./plugins/sensai", "source": "local"}
    else:
        marketplace = _object(root / ".claude-plugin" / "marketplace.json")
        expected_source = "./plugins/sensai"
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or len(plugins) != 1:
        raise ReleaseVerificationError(f"Unexpected {platform} marketplace plugin set")
    plugin = plugins[0]
    if not isinstance(plugin, dict) or plugin.get("name") != "sensai":
        raise ReleaseVerificationError(f"Unexpected {platform} marketplace plugin")
    if plugin.get("source") != expected_source:
        raise ReleaseVerificationError(f"Unexpected {platform} marketplace source")


def verify_release(*, repository_root: Path, bundle: Path) -> dict[str, Any]:
    """Verify one bundle without importing or calling release builder code."""
    if bundle.is_symlink() or not bundle.is_dir():
        raise ReleaseVerificationError("Release bundle must be a regular directory")
    entries = tuple(islice(bundle.iterdir(), _MAX_BUNDLE_ENTRIES + 1))
    if len(entries) > _MAX_BUNDLE_ENTRIES:
        raise ReleaseVerificationError("Release bundle entry count exceeds limit")
    if any(not path.is_file() or path.is_symlink() for path in entries):
        raise ReleaseVerificationError("Bundle contains unexpected entries")
    if sum(path.stat().st_size for path in entries) > _MAX_BUNDLE_BYTES:
        raise ReleaseVerificationError("Release bundle exceeds size limit")
    metadata_path = bundle / "release.json"
    metadata = _object(metadata_path)
    if set(metadata) != _METADATA_FIELDS or metadata.get("format_version") != "1":
        raise ReleaseVerificationError("Unexpected release metadata format")
    version = _string(metadata.get("release_version"), "release_version")
    mcp_url = _string(metadata.get("mcp_url"), "mcp_url")
    _validate_mcp_url(mcp_url)
    contract_version = _string(metadata.get("mcp_contract_version"), "mcp_contract_version")
    schema_hash = _sha256(metadata.get("mcp_schema_sha256"), "mcp_schema_sha256")
    contract = _object(repository_root / "contracts" / "mcp-surface-v1.json")
    if hashlib.sha256(_canonical_json(contract)).hexdigest() != schema_hash:
        raise ReleaseVerificationError("MCP schema hash does not match the canonical contract")
    if contract_version != "1":
        raise ReleaseVerificationError("Unsupported MCP contract version")
    trusted_source = _trusted_source_bytes(repository_root)

    platforms = metadata.get("platforms")
    if not isinstance(platforms, dict) or set(platforms) != set(_PLATFORMS):
        raise ReleaseVerificationError("Release must contain exact Codex and Claude metadata")
    expected_bundle_files = {"release.json"}
    for platform in _PLATFORMS:
        platform_data = platforms[platform]
        if not isinstance(platform_data, dict) or set(platform_data) != _PLATFORM_FIELDS:
            raise ReleaseVerificationError(f"Unexpected platform metadata: {platform}")
        archive_name = _safe_relative(platform_data.get("archive"), f"{platform}.archive")
        expected_bundle_files.add(archive_name)
        archive_path = bundle / archive_name
        if not archive_path.is_file() or archive_path.is_symlink():
            raise ReleaseVerificationError(f"Missing regular archive: {archive_name}")
        if _digest(archive_path, _MAX_ARCHIVE_BYTES, f"{platform} archive") != _sha256(
            platform_data.get("archive_sha256"), f"{platform}.archive_sha256"
        ):
            raise ReleaseVerificationError(f"Archive SHA-256 mismatch: {platform}")
        if (
            platform_data.get("plugin_version") != version
            or platform_data.get("mcp_url") != mcp_url
        ):
            raise ReleaseVerificationError(f"Platform metadata disagrees with release: {platform}")
        expected = _expected_files(platform_data.get("files"), platform)
        extraction = Path(tempfile.mkdtemp(prefix=f"sensai-verify-{platform}-"))
        try:
            actual_bytes = _extract_archive(archive_path, extraction)
            actual = {
                relative: hashlib.sha256(content).hexdigest()
                for relative, content in actual_bytes.items()
            }
            if actual != expected:
                raise ReleaseVerificationError(f"Extracted file manifest mismatch: {platform}")
            trusted = _expected_marketplace_bytes(
                trusted_source,
                platform=platform,
                mcp_url=mcp_url,
            )
            if actual_bytes != trusted:
                raise ReleaseVerificationError(
                    f"Archive content differs from trusted plugin source: {platform}"
                )
            _verify_marketplace(
                extraction,
                platform=platform,
                version=version,
                mcp_url=mcp_url,
            )
        finally:
            shutil.rmtree(extraction)

    actual_bundle_files = {path.name for path in entries}
    if actual_bundle_files != expected_bundle_files:
        raise ReleaseVerificationError("Bundle contains unexpected entries")
    return {
        "mcp_contract_version": contract_version,
        "mcp_schema_sha256": schema_hash,
        "mcp_url": mcp_url,
        "platforms": list(_PLATFORMS),
        "release_version": version,
        "verified": True,
    }
