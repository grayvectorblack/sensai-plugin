#!/usr/bin/env python3
"""Offline Codex plugin lifecycle acceptance using an isolated profile."""

# ruff: noqa: E402, I001

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from sensai_plugin.package_builder import build_packages


MARKETPLACE_NAME = "sensai-lifecycle-test"
PLUGIN_SELECTOR = f"sensai@{MARKETPLACE_NAME}"
V1_VERSION = "0.1.0"
V2_VERSION = "0.1.1"
V1_URL = "https://black-vector.com/sensai/mcp"
V2_URL = "https://black-vector.com/sensai/mcp?lifecycle=2"
CODEX_TIMEOUT_SECONDS = 30


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"Expected a JSON object in {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _validate_package(package_root: Path) -> None:
    manifest_path = package_root / "MANIFEST.sha256"
    entries: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        digest, separator, relative = line.partition("  ")
        if separator != "  " or len(digest) != 64:
            raise AssertionError(f"Malformed package manifest line: {line!r}")
        entries[relative] = digest

    actual = {
        path.relative_to(package_root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in package_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if entries != actual:
        raise AssertionError("Built Codex package does not match MANIFEST.sha256")


def _fingerprint(path: Path) -> tuple[tuple[str, str], ...]:
    if not path.exists():
        return ((".", "missing"),)
    if path.is_file():
        return ((".", hashlib.sha256(path.read_bytes()).hexdigest()),)

    result: list[tuple[str, str]] = []
    for entry in sorted(path.rglob("*")):
        relative = entry.relative_to(path).as_posix()
        if entry.is_symlink():
            result.append((relative, f"symlink:{os.readlink(entry)}"))
        elif entry.is_file():
            result.append((relative, hashlib.sha256(entry.read_bytes()).hexdigest()))
        elif entry.is_dir():
            result.append((relative, "directory"))
    return tuple(result)


def _run_json(codex: str, env: dict[str, str], *arguments: str) -> Any:
    command = [codex, *arguments]
    if arguments[:2] == ("plugin", "marketplace"):
        surface = "codex " + " ".join(arguments[:3])
    else:
        surface = "codex " + " ".join(arguments[:2])
    try:
        completed = subprocess.run(
            command,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=CODEX_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise AssertionError(f"Timed out after {CODEX_TIMEOUT_SECONDS}s: {surface}") from error
    if completed.returncode != 0:
        rendered = " ".join(command)
        raise AssertionError(
            f"Command failed ({completed.returncode}): {rendered}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(f"Command did not return JSON: {' '.join(command)}") from error


def _assert_mcp_url(mcp_entries: Any, expected_url: str) -> None:
    if not isinstance(mcp_entries, list):
        raise AssertionError("codex mcp list --json did not return a list")
    sensai = [entry for entry in mcp_entries if entry.get("name") == "sensai"]
    if len(sensai) != 1:
        raise AssertionError(f"Expected one discovered Sensai MCP server, got {len(sensai)}")
    transport = sensai[0].get("transport", {})
    if transport.get("type") != "streamable_http" or transport.get("url") != expected_url:
        raise AssertionError(f"Unexpected Sensai MCP transport: {transport!r}")


def _build_version(profile: Path, name: str, version: str, mcp_url: str) -> Path:
    source = profile / "work" / f"source-{name}"
    output = profile / "work" / f"build-{name}"
    shutil.copytree(REPOSITORY_ROOT / "payload-src", source)

    manifest_path = source / "codex" / ".codex-plugin" / "plugin.json"
    manifest = _json_file(manifest_path)
    manifest["version"] = version
    _write_json(manifest_path, manifest)

    mcp_path = source / "shared" / ".mcp.json"
    mcp = _json_file(mcp_path)
    mcp["mcpServers"]["sensai"]["url"] = mcp_url
    _write_json(mcp_path, mcp)

    package = build_packages(source_root=source, output_root=output).codex
    _validate_package(package)
    return package


def _write_marketplace(marketplace: Path, package: Path) -> None:
    plugin_root = marketplace / "plugins" / "sensai"
    if plugin_root.exists():
        shutil.rmtree(plugin_root)
    plugin_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, plugin_root)

    manifest_path = marketplace / ".agents" / "plugins" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        manifest_path,
        {
            "name": MARKETPLACE_NAME,
            "plugins": [
                {
                    "name": "sensai",
                    "source": {"source": "local", "path": "./plugins/sensai"},
                    "policy": {"installation": "AVAILABLE"},
                }
            ],
        },
    )


def _assert_installed(result: Any, profile: Path, version: str) -> None:
    if not isinstance(result, dict) or result.get("version") != version:
        raise AssertionError(f"Codex did not report installed version {version}: {result!r}")
    installed_path = Path(result.get("installedPath", "")).resolve()
    if not installed_path.is_relative_to(profile.resolve()):
        raise AssertionError(f"Codex installed outside the isolated profile: {installed_path}")


def _run_lifecycle(codex: str, profile: Path) -> None:
    for relative in ("home", "tmp", "xdg-cache", "xdg-config", "xdg-data"):
        (profile / relative).mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "CODEX_HOME": str(profile),
        "HOME": str(profile / "home"),
        "TMPDIR": str(profile / "tmp"),
        "XDG_CACHE_HOME": str(profile / "xdg-cache"),
        "XDG_CONFIG_HOME": str(profile / "xdg-config"),
        "XDG_DATA_HOME": str(profile / "xdg-data"),
    }

    v1 = _build_version(profile, "v1", V1_VERSION, V1_URL)
    v2 = _build_version(profile, "v2", V2_VERSION, V2_URL)
    marketplace = profile / "work" / "marketplace"
    _write_marketplace(marketplace, v1)

    added_marketplace = _run_json(
        codex, env, "plugin", "marketplace", "add", str(marketplace), "--json"
    )
    if added_marketplace.get("marketplaceName") != MARKETPLACE_NAME:
        raise AssertionError(f"Unexpected marketplace add result: {added_marketplace!r}")

    installed_v1 = _run_json(codex, env, "plugin", "add", PLUGIN_SELECTOR, "--json")
    _assert_installed(installed_v1, profile, V1_VERSION)
    mcp_v1 = _run_json(codex, env, "mcp", "list", "--json")
    _assert_mcp_url(mcp_v1, V1_URL)
    print(f"OBSERVED add-v1={json.dumps(installed_v1, sort_keys=True)}")
    print(f"OBSERVED mcp-v1={json.dumps(mcp_v1, sort_keys=True)}")

    _write_marketplace(marketplace, v2)
    installed_v2 = _run_json(codex, env, "plugin", "add", PLUGIN_SELECTOR, "--json")
    _assert_installed(installed_v2, profile, V2_VERSION)
    mcp_v2 = _run_json(codex, env, "mcp", "list", "--json")
    _assert_mcp_url(mcp_v2, V2_URL)
    print(f"OBSERVED add-v2={json.dumps(installed_v2, sort_keys=True)}")
    print(f"OBSERVED mcp-v2={json.dumps(mcp_v2, sort_keys=True)}")

    removed = _run_json(codex, env, "plugin", "remove", PLUGIN_SELECTOR, "--json")
    if removed.get("pluginId") != PLUGIN_SELECTOR:
        raise AssertionError(f"Unexpected plugin remove result: {removed!r}")
    print(f"OBSERVED remove={json.dumps(removed, sort_keys=True)}")
    if _run_json(codex, env, "mcp", "list", "--json") != []:
        raise AssertionError("Sensai MCP configuration remained after plugin removal")
    plugin_cache = profile / "plugins" / "cache" / MARKETPLACE_NAME / "sensai"
    if plugin_cache.exists() and any(plugin_cache.rglob("*")):
        raise AssertionError(f"Plugin payload remained after removal: {plugin_cache}")

    _run_json(codex, env, "plugin", "marketplace", "remove", MARKETPLACE_NAME, "--json")
    marketplace_result = _run_json(codex, env, "plugin", "marketplace", "list", "--json")
    marketplaces = marketplace_result.get("marketplaces", [])
    if any(item.get("name") == MARKETPLACE_NAME for item in marketplaces):
        raise AssertionError("Lifecycle marketplace remained configured after removal")


def main() -> int:
    codex = shutil.which("codex")
    if codex is None:
        raise SystemExit("codex is required on PATH")

    real_codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
    real_config = real_codex_home / "config.toml"
    real_cache = real_codex_home / "plugins" / "cache" / MARKETPLACE_NAME
    real_before = (_fingerprint(real_config), _fingerprint(real_cache))

    with tempfile.TemporaryDirectory(prefix="sensai-codex-lifecycle-") as temporary:
        profile = Path(temporary).resolve()
        if profile.is_relative_to(real_codex_home) or real_codex_home.is_relative_to(profile):
            raise AssertionError("Temporary CODEX_HOME overlaps the real user profile")
        _run_lifecycle(codex, profile)
    if Path(temporary).exists():
        raise AssertionError(f"Isolated profile was not removed: {temporary}")

    real_after = (_fingerprint(real_config), _fingerprint(real_cache))
    if real_after != real_before:
        raise AssertionError("Real Codex config or lifecycle cache changed during acceptance")

    try:
        version = subprocess.run(
            [codex, "--version"],
            text=True,
            capture_output=True,
            check=True,
            timeout=CODEX_TIMEOUT_SECONDS,
        ).stdout.strip()
    except subprocess.TimeoutExpired as error:
        raise AssertionError(
            f"Timed out after {CODEX_TIMEOUT_SECONDS}s: codex --version"
        ) from error
    print(f"PASS codex={version}")
    print(f"PASS install={V1_VERSION} mcp={V1_URL}")
    print(f"PASS update-via-plugin-add={V2_VERSION} mcp={V2_URL}")
    print("PASS remove=no-mcp-or-plugin-payload isolated-profile=deleted")
    print("PASS real-config-and-lifecycle-cache-sentinels=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
