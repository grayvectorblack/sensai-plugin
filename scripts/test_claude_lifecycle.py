#!/usr/bin/env python3
"""Claude Code plugin lifecycle acceptance using an isolated profile."""

# ruff: noqa: E402, I001

from __future__ import annotations

import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from sensai_plugin.package_builder import build_packages


MARKETPLACE_NAME = "sensai-lifecycle-test"
PLUGIN_SELECTOR = f"sensai@{MARKETPLACE_NAME}"
PLUGIN_MCP_NAME = "plugin:sensai:sensai"
V1_VERSION = "0.1.0"
V2_VERSION = "0.1.1"
V1_URL = "https://black-vector.com/sensai/mcp"
V2_URL = "https://black-vector.com/sensai/mcp?lifecycle=2"
CLAUDE_TIMEOUT_SECONDS = 30
CLAUDE_TERMINATION_GRACE_SECONDS = 2
EXPECTED_CLAUDE_VERSION = "2.1.193 (Claude Code)"
_PASSTHROUGH_ENVIRONMENT_NAMES = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)


def _emit(message: str) -> None:
    print(message, flush=True)


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
        raise AssertionError("Built Claude package does not match MANIFEST.sha256")


def _fingerprint(path: Path) -> tuple[tuple[str, str], ...]:
    if not path.exists() and not path.is_symlink():
        return ((".", "missing"),)
    if path.is_symlink():
        target = os.readlink(path)
        return ((".", f"symlink:{target}"),)
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


def _real_state_paths() -> tuple[Path, ...]:
    home = Path.home()
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude"))
    plugin_cache = Path(os.environ.get("CLAUDE_CODE_PLUGIN_CACHE_DIR", config / "plugins"))
    xdg_cache = Path(os.environ.get("XDG_CACHE_HOME", home / ".cache"))
    xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    resolved_config = config.resolve(strict=False)
    candidates: list[Path] = [
        home / ".claude",
        config,
        resolved_config / "settings.json",
        resolved_config / ".claude.json",
        resolved_config / "backups",
        home / ".claude.json",
        plugin_cache.resolve(strict=False),
        xdg_cache / "claude",
        xdg_cache / "claude-cli-nodejs",
        xdg_config / "claude",
        xdg_data / "claude",
        xdg_data / "claude-code",
        REPOSITORY_ROOT / ".claude",
    ]
    return tuple(dict.fromkeys(path.absolute() for path in candidates))


def _fingerprint_real_state(paths: tuple[Path, ...]) -> dict[Path, tuple[tuple[str, str], ...]]:
    return {path: _fingerprint(path) for path in paths}


def _surface(arguments: tuple[str, ...]) -> str:
    if arguments[:2] == ("plugin", "marketplace"):
        return "claude " + " ".join(arguments[:3])
    if arguments[:1] == ("plugin",):
        return "claude " + " ".join(arguments[:2])
    if arguments[:1] == ("mcp",):
        return "claude " + " ".join(arguments[:2])
    return "claude " + " ".join(arguments[:1])


def _run(
    claude: str,
    env: dict[str, str],
    cwd: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = [claude, *arguments]
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
        raise AssertionError(
            f"Timed out after {CLAUDE_TIMEOUT_SECONDS}s: {_surface(arguments)}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        ) from error
    completed = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check and completed.returncode != 0:
        raise AssertionError(
            f"Command failed ({completed.returncode}): {_surface(arguments)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return completed


def _run_json(claude: str, env: dict[str, str], cwd: Path, *arguments: str) -> Any:
    completed = _run(claude, env, cwd, *arguments)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(f"Command did not return JSON: {_surface(arguments)}") from error


def _build_version(profile: Path, name: str, version: str, mcp_url: str) -> Path:
    source = profile / "work" / f"source-{name}"
    output = profile / "work" / f"build-{name}"
    shutil.copytree(REPOSITORY_ROOT / "payload-src", source)

    manifest_path = source / "claude" / ".claude-plugin" / "plugin.json"
    manifest = _json_file(manifest_path)
    manifest["version"] = version
    _write_json(manifest_path, manifest)

    mcp_path = source / "shared" / ".mcp.json"
    mcp = _json_file(mcp_path)
    mcp["mcpServers"]["sensai"]["url"] = mcp_url
    _write_json(mcp_path, mcp)

    package = build_packages(source_root=source, output_root=output).claude
    _validate_package(package)
    return package


def _write_marketplace(marketplace: Path, package: Path) -> None:
    plugin_root = marketplace / "plugins" / "sensai"
    if plugin_root.exists():
        shutil.rmtree(plugin_root)
    plugin_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, plugin_root)

    manifest_path = marketplace / ".claude-plugin" / "marketplace.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(
        manifest_path,
        {
            "name": MARKETPLACE_NAME,
            "description": "Isolated Sensai plugin lifecycle acceptance marketplace.",
            "owner": {"name": "Sensai lifecycle acceptance"},
            "plugins": [
                {
                    "name": "sensai",
                    "source": "./plugins/sensai",
                    "description": "Lifecycle acceptance package.",
                }
            ],
        },
    )


def _assert_validation_passed(completed: subprocess.CompletedProcess[str], label: str) -> None:
    output = completed.stdout + completed.stderr
    if "Validation passed" not in output:
        raise AssertionError(f"Claude did not confirm strict validation for {label}: {output!r}")


def _assert_marketplace_list(result: Any, marketplace: Path) -> None:
    if not isinstance(result, list) or len(result) != 1:
        raise AssertionError(f"Expected one isolated marketplace, got {result!r}")
    entry = result[0]
    if entry.get("name") != MARKETPLACE_NAME or entry.get("source") != "directory":
        raise AssertionError(f"Unexpected marketplace entry: {entry!r}")
    for field in ("path", "installLocation"):
        if Path(entry.get(field, "")).resolve() != marketplace.resolve():
            raise AssertionError(f"Marketplace {field} escaped the isolated profile: {entry!r}")


def _installed_plugin(result: Any) -> dict[str, Any]:
    if not isinstance(result, list):
        raise AssertionError(f"claude plugin list --json did not return a list: {result!r}")
    matches = [entry for entry in result if entry.get("id") == PLUGIN_SELECTOR]
    if len(matches) != 1:
        raise AssertionError(f"Expected one installed Sensai plugin, got {len(matches)}")
    entry = matches[0]
    if not isinstance(entry, dict):
        raise AssertionError(f"Unexpected installed plugin entry: {entry!r}")
    return entry


def _assert_installed(
    result: Any,
    profile: Path,
    version: str,
    expected_url: str,
) -> dict[str, Any]:
    entry = _installed_plugin(result)
    expected_fields = {"version": version, "scope": "user", "enabled": True}
    for field, expected in expected_fields.items():
        if entry.get(field) != expected:
            raise AssertionError(f"Unexpected installed plugin {field}: {entry!r}")

    install_path = Path(entry.get("installPath", "")).resolve()
    if not install_path.is_relative_to((profile / "plugin-cache").resolve()):
        raise AssertionError(f"Claude installed outside the isolated plugin cache: {install_path}")
    if install_path.name != version:
        raise AssertionError(f"Claude active cache path does not identify version {version}")
    _validate_package(install_path)

    mcp_servers = entry.get("mcpServers")
    expected_mcp = {"sensai": {"type": "http", "url": expected_url}}
    if mcp_servers != expected_mcp:
        raise AssertionError(f"Unexpected plugin MCP configuration: {mcp_servers!r}")
    return entry


def _assert_mcp_discovered(completed: subprocess.CompletedProcess[str], expected_url: str) -> None:
    output = completed.stdout + completed.stderr
    required = (
        f"{PLUGIN_MCP_NAME}:",
        "Scope: Dynamic config (from command line)",
        "Type: http",
        f"URL: {expected_url}",
    )
    missing = [line for line in required if line not in output]
    if missing:
        raise AssertionError(f"Claude MCP discovery omitted {missing!r}: {output!r}")


def _isolated_environment(profile: Path) -> dict[str, str]:
    isolated_temp = profile / "tmp"
    roots = {
        "CLAUDE_CONFIG_DIR": profile / "config",
        "CLAUDE_CODE_PLUGIN_CACHE_DIR": profile / "plugin-cache",
        "CLAUDE_SECURESTORAGE_CONFIG_DIR": profile / "secure-storage",
        "HOME": profile / "home",
        "TMPDIR": isolated_temp,
        "TMP": isolated_temp,
        "TEMP": isolated_temp,
        "XDG_CACHE_HOME": profile / "xdg-cache",
        "XDG_CONFIG_HOME": profile / "xdg-config",
        "XDG_DATA_HOME": profile / "xdg-data",
    }
    for path in roots.values():
        path.mkdir(parents=True, exist_ok=True)

    env = {name: os.environ[name] for name in _PASSTHROUGH_ENVIRONMENT_NAMES if name in os.environ}
    env.update({key: str(value) for key, value in roots.items()})
    env["DISABLE_AUTOUPDATER"] = "1"
    return env


def _run_lifecycle(claude: str, profile: Path) -> str:
    env = _isolated_environment(profile)
    work = profile / "work"
    work.mkdir()
    version = _run(claude, env, work, "--version").stdout.strip()
    if version != EXPECTED_CLAUDE_VERSION:
        raise AssertionError(
            f"Lifecycle parser requires {EXPECTED_CLAUDE_VERSION!r}, observed {version!r}"
        )
    v1 = _build_version(profile, "v1", V1_VERSION, V1_URL)
    v2 = _build_version(profile, "v2", V2_VERSION, V2_URL)
    marketplace = work / "marketplace"
    _write_marketplace(marketplace, v1)

    _assert_validation_passed(
        _run(claude, env, work, "plugin", "validate", "--strict", str(v1)), "v1 plugin"
    )
    _assert_validation_passed(
        _run(
            claude,
            env,
            work,
            "plugin",
            "validate",
            "--strict",
            str(marketplace),
        ),
        "v1 marketplace",
    )

    _run(claude, env, work, "plugin", "marketplace", "add", str(marketplace))
    _assert_marketplace_list(
        _run_json(claude, env, work, "plugin", "marketplace", "list", "--json"),
        marketplace,
    )

    _run(claude, env, work, "plugin", "install", PLUGIN_SELECTOR, "--scope", "user")
    installed_v1 = _assert_installed(
        _run_json(claude, env, work, "plugin", "list", "--json"),
        profile,
        V1_VERSION,
        V1_URL,
    )
    mcp_v1 = _run(claude, env, work, "mcp", "get", PLUGIN_MCP_NAME)
    _assert_mcp_discovered(mcp_v1, V1_URL)
    _emit(f"OBSERVED install-v1={json.dumps(installed_v1, sort_keys=True)}")
    _emit(f"OBSERVED mcp-v1={mcp_v1.stdout.strip()!r}")

    _write_marketplace(marketplace, v2)
    _assert_validation_passed(
        _run(claude, env, work, "plugin", "validate", "--strict", str(v2)), "v2 plugin"
    )
    _assert_validation_passed(
        _run(
            claude,
            env,
            work,
            "plugin",
            "validate",
            "--strict",
            str(marketplace),
        ),
        "v2 marketplace",
    )
    _run(claude, env, work, "plugin", "marketplace", "update", MARKETPLACE_NAME)
    _run(
        claude,
        env,
        work,
        "plugin",
        "update",
        PLUGIN_SELECTOR,
        "--scope",
        "user",
    )
    installed_v2 = _assert_installed(
        _run_json(claude, env, work, "plugin", "list", "--json"),
        profile,
        V2_VERSION,
        V2_URL,
    )
    mcp_v2 = _run(claude, env, work, "mcp", "get", PLUGIN_MCP_NAME)
    _assert_mcp_discovered(mcp_v2, V2_URL)
    _emit(f"OBSERVED update-v2={json.dumps(installed_v2, sort_keys=True)}")
    _emit(f"OBSERVED mcp-v2={mcp_v2.stdout.strip()!r}")

    _run(
        claude,
        env,
        work,
        "plugin",
        "uninstall",
        PLUGIN_SELECTOR,
        "--scope",
        "user",
    )
    if _run_json(claude, env, work, "plugin", "list", "--json") != []:
        raise AssertionError("Installed plugin registry was not empty after uninstall")
    missing_mcp = _run(claude, env, work, "mcp", "get", PLUGIN_MCP_NAME, check=False)
    missing_output = missing_mcp.stdout + missing_mcp.stderr
    if missing_mcp.returncode == 0 or "No MCP server named" not in missing_output:
        raise AssertionError(
            f"Plugin MCP remained discoverable after uninstall: {missing_output!r}"
        )

    orphan_markers = sorted((profile / "plugin-cache").rglob(".orphaned_at"))
    _emit(f"OBSERVED uninstall-cache-orphan-markers={len(orphan_markers)}")

    _run(
        claude,
        env,
        work,
        "plugin",
        "marketplace",
        "remove",
        MARKETPLACE_NAME,
        "--scope",
        "user",
    )
    if _run_json(claude, env, work, "plugin", "marketplace", "list", "--json") != []:
        raise AssertionError("Marketplace remained configured after removal")
    return version


def main() -> int:
    claude = shutil.which("claude")
    if claude is None:
        raise SystemExit("claude is required on PATH")

    real_paths = _real_state_paths()
    _emit(f"START real-state-fingerprint-before paths={len(real_paths)}")
    real_before = _fingerprint_real_state(real_paths)
    _emit("OBSERVED real-state-fingerprint-before=complete")

    with tempfile.TemporaryDirectory(prefix="sensai-claude-lifecycle-") as temporary:
        profile = Path(temporary).resolve()
        real_config = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")).resolve(
            strict=False
        )
        if profile.is_relative_to(real_config) or real_config.is_relative_to(profile):
            raise AssertionError("Temporary CLAUDE_CONFIG_DIR overlaps the real user profile")
        _emit(f"START isolated-lifecycle claude={EXPECTED_CLAUDE_VERSION}")
        version = _run_lifecycle(claude, profile)
    if Path(temporary).exists():
        raise AssertionError(f"Isolated Claude profile was not removed: {temporary}")

    _emit("START real-state-fingerprint-after")
    real_after = _fingerprint_real_state(real_paths)
    changed = [str(path) for path in real_paths if real_before[path] != real_after[path]]
    if changed:
        raise AssertionError(f"Real Claude state changed during acceptance: {changed!r}")

    _emit(f"PASS claude={version}")
    _emit(f"PASS install={V1_VERSION} mcp-discovered={V1_URL}")
    _emit(f"PASS native-update={V2_VERSION} mcp-discovered={V2_URL}")
    _emit("PASS uninstall=no-installed-plugin-or-discovered-mcp")
    _emit("PASS marketplace=removed isolated-profile=deleted")
    for path in real_paths:
        _emit(f"PASS unchanged-state-sentinel={path} resolved={path.resolve(strict=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
