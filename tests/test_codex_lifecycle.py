from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from sensai_plugin.release_builder import build_release

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MCP_URL = "https://black-vector.com/sensai/mcp"


def _lifecycle_module() -> ModuleType:
    path = REPOSITORY_ROOT / "scripts" / "test_codex_lifecycle.py"
    specification = importlib.util.spec_from_file_location("sensai_codex_lifecycle", path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def release_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    bundle = tmp_path_factory.mktemp("codex-release") / "release"
    build_release(
        repository_root=REPOSITORY_ROOT,
        output=bundle,
        mcp_url=MCP_URL,
    )
    return bundle


def _run_lifecycle(
    *,
    bundle: Path,
    executable_directory: Path,
    real_profile: Path,
) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "CODEX_HOME": str(real_profile),
        "PATH": f"{executable_directory}{os.pathsep}{os.environ['PATH']}",
    }
    return subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "scripts" / "test_codex_lifecycle.py"),
            "--bundle",
            str(bundle),
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )


def test_codex_profile_fingerprint_covers_complete_tree_and_resolved_symlink(
    tmp_path: Path,
) -> None:
    module = _lifecycle_module()
    target = tmp_path / "profile-target"
    target.mkdir()
    configured = tmp_path / "configured-codex-home"
    configured.symlink_to(target, target_is_directory=True)
    before = module._real_codex_profile_fingerprint(configured)

    marketplace_state = target / ".tmp" / "marketplaces" / "global.json"
    marketplace_state.parent.mkdir(parents=True)
    marketplace_state.write_text('{"changed": true}\n', encoding="utf-8")

    assert module._real_codex_profile_fingerprint(configured) != before

    after_boundary_change = module._real_codex_profile_fingerprint(configured)
    unrelated = target / "sessions" / "unrelated.jsonl"
    unrelated.parent.mkdir()
    unrelated.write_text("unrelated runtime state\n", encoding="utf-8")

    assert module._real_codex_profile_fingerprint(configured) == after_boundary_change


def test_codex_profile_fingerprint_skips_unrelated_tmp_plugins_but_detects_sensai(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _lifecycle_module()
    profile = tmp_path / "codex-home"
    unrelated = profile / ".tmp" / "plugins" / "plugins" / "unrelated-backup"
    unrelated.mkdir(parents=True)
    for index in range(200):
        (unrelated / f"payload-{index}.bin").write_bytes(b"x" * 4096)
    original_sha256_file = module._sha256_file
    hashed: list[Path] = []

    def recording_sha256_file(path: Path) -> str:
        hashed.append(path)
        return cast(str, original_sha256_file(path))

    monkeypatch.setattr(module, "_sha256_file", recording_sha256_file)
    started = time.monotonic()
    before = module._real_codex_profile_fingerprint(profile)
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert all(not path.is_relative_to(unrelated) for path in hashed)
    (unrelated / "payload-0.bin").write_bytes(b"changed but unrelated")
    assert module._real_codex_profile_fingerprint(profile) == before

    sensai = profile / ".tmp" / "plugins" / "plugins" / "sensai" / "marker.json"
    sensai.parent.mkdir()
    sensai.write_text('{"sensai": true}\n', encoding="utf-8")

    assert module._real_codex_profile_fingerprint(profile) != before


def test_codex_lifecycle_rejects_tampering_before_invoking_codex(
    tmp_path: Path,
    release_bundle: Path,
) -> None:
    bundle = tmp_path / "release"
    shutil.copytree(release_bundle, bundle)
    archive = bundle / "sensai-0.1.0-codex-marketplace.zip"
    archive.write_bytes(archive.read_bytes() + b"tampered")

    marker = tmp_path / "codex-was-invoked"
    executable = tmp_path / "codex"
    executable.write_text(
        f"#!/bin/sh\nprintf invoked > {marker!s}\nprintf '{{}}\\n'\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    completed = _run_lifecycle(
        bundle=bundle,
        executable_directory=tmp_path,
        real_profile=tmp_path / "real-profile",
    )

    assert completed.returncode != 0
    assert "release verification failed" in completed.stderr
    assert not marker.exists()


def test_codex_lifecycle_uses_exact_read_only_marketplace_and_isolated_profile(
    tmp_path: Path,
    release_bundle: Path,
) -> None:
    log = tmp_path / "commands.jsonl"
    executable = tmp_path / "codex"
    fake_codex = """#!/usr/bin/env python3
import json
import os
import shutil
import stat
import sys
from pathlib import Path

arguments = sys.argv[1:]
codex_home = Path(os.environ["CODEX_HOME"])
home = Path(os.environ["HOME"])
with Path(__LOG__).open("a", encoding="utf-8") as output:
    entry = {"arguments": arguments, "codex_home": str(codex_home), "home": str(home)}
    output.write(json.dumps(entry) + "\\n")

if arguments[:3] == ["plugin", "marketplace", "add"]:
    marketplace = Path(arguments[3])
    assert marketplace.is_dir() and marketplace.suffix != ".zip"
    for path in marketplace.rglob("*"):
        if path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) == 0o444
        elif path.is_dir():
            assert stat.S_IMODE(path.stat().st_mode) == 0o555
    print(json.dumps({"marketplaceName": "sensai-local"}))
elif arguments[:2] == ["plugin", "add"]:
    assert arguments[2] == "sensai@sensai-local"
    marketplace = Path(json.loads(Path(__LOG__).read_text().splitlines()[0])["arguments"][3])
    installed = codex_home / "plugins" / "cache" / "sensai-local" / "sensai" / "0.1.0"
    installed.parent.mkdir(parents=True)
    shutil.copytree(marketplace / "plugins" / "sensai", installed)
    print(json.dumps({"version": "0.1.0", "installedPath": str(installed)}))
elif arguments == ["mcp", "list", "--json"]:
    transport = {"type": "streamable_http", "url": __URL__}
    print(json.dumps([{"name": "sensai", "transport": transport}]))
else:
    raise SystemExit("unexpected command: " + repr(arguments))
"""
    fake_codex = fake_codex.replace("__LOG__", repr(str(log))).replace("__URL__", repr(MCP_URL))
    executable.write_text(fake_codex, encoding="utf-8")
    executable.chmod(0o755)
    real_profile = tmp_path / "real-profile"
    real_profile.mkdir()
    sentinel = real_profile / "config.toml"
    sentinel.write_text("model = 'unchanged'\n", encoding="utf-8")
    bundle_before = {
        path.relative_to(release_bundle).as_posix(): path.read_bytes()
        for path in release_bundle.iterdir()
    }

    completed = _run_lifecycle(
        bundle=release_bundle,
        executable_directory=tmp_path,
        real_profile=real_profile,
    )

    assert completed.returncode == 0, completed.stderr
    assert "PASS selector=sensai@sensai-local" in completed.stdout
    assert "PASS version=0.1.0" in completed.stdout
    assert f"PASS mcp={MCP_URL}" in completed.stdout
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [entry["arguments"] for entry in entries] == [
        ["plugin", "marketplace", "add", entries[0]["arguments"][3], "--json"],
        ["plugin", "add", "sensai@sensai-local", "--json"],
        ["mcp", "list", "--json"],
    ]
    assert all(entry["codex_home"] != str(real_profile) for entry in entries)
    assert all(entry["home"] != str(Path.home()) for entry in entries)
    assert not Path(entries[0]["codex_home"]).parent.exists()
    assert sentinel.read_text(encoding="utf-8") == "model = 'unchanged'\n"
    assert bundle_before == {
        path.relative_to(release_bundle).as_posix(): path.read_bytes()
        for path in release_bundle.iterdir()
    }


@pytest.mark.codex_real_cli
def test_codex_lifecycle_with_installed_official_cli(release_bundle: Path) -> None:
    codex = shutil.which("codex")
    if codex is None:
        pytest.skip("official Codex CLI is not installed")
    completed = subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "scripts" / "test_codex_lifecycle.py"),
            "--bundle",
            str(release_bundle),
        ],
        cwd=REPOSITORY_ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
        timeout=900,
    )

    assert completed.returncode == 0, completed.stderr
    assert "PASS selector=sensai@sensai-local" in completed.stdout
    assert "PASS version=0.1.0" in completed.stdout
    assert f"PASS mcp={MCP_URL}" in completed.stdout
    assert (
        "PASS isolated-profile=removed real-plugin-lifecycle-boundary=unchanged" in completed.stdout
    )
