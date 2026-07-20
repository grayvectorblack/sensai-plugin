from __future__ import annotations

import hashlib
import json
import shutil
import stat
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from sensai_plugin.release_builder import build_release

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

import test_claude_lifecycle as lifecycle  # noqa: E402

MCP_URL = "http://127.0.0.1:8765/mcp"


@pytest.fixture(scope="session")
def built_release_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    bundle = tmp_path_factory.mktemp("claude-release") / "release"
    build_release(
        repository_root=REPOSITORY_ROOT,
        output=bundle,
        mcp_url=MCP_URL,
    )
    return bundle


@pytest.fixture
def release_bundle(built_release_bundle: Path, tmp_path: Path) -> Path:
    bundle = tmp_path / "release"
    shutil.copytree(built_release_bundle, bundle)
    return bundle


@pytest.fixture
def claude_workspace() -> Iterator[Path]:
    workspace = Path(tempfile.mkdtemp(prefix="sensai-claude-unit-", dir="/tmp"))
    try:
        yield workspace
    finally:
        lifecycle.remove_readonly_tree(workspace)


def test_prepare_verified_marketplace_extracts_exact_read_only_claude_release(
    release_bundle: Path,
    claude_workspace: Path,
) -> None:
    destination = claude_workspace / "marketplace"

    release = lifecycle.prepare_verified_marketplace(release_bundle, destination)

    metadata = json.loads((release_bundle / "release.json").read_text(encoding="utf-8"))
    expected_files = metadata["platforms"]["claude"]["files"]
    actual_files = {
        path.relative_to(destination).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in destination.rglob("*")
        if path.is_file()
    }
    assert actual_files == expected_files
    assert release.marketplace == destination
    assert release.selector == "sensai@sensai-local"
    assert release.version == metadata["release_version"]
    assert release.mcp_url == MCP_URL
    assert release.mcp_attestation == {
        "format_version": "1",
        "mcp_contract_version": metadata["mcp_contract_version"],
        "mcp_schema_sha256": metadata["mcp_schema_sha256"],
        "mcp_url": MCP_URL,
    }
    for path in (destination, *destination.rglob("*")):
        mode = path.stat().st_mode
        assert mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) == 0
    assert destination.parent.stat().st_mode & stat.S_IWUSR

    lifecycle.remove_readonly_tree(destination)
    assert not destination.exists()
    assert destination.parent.exists()


def test_prepare_verified_marketplace_fails_before_extracting_tampered_release(
    release_bundle: Path,
    claude_workspace: Path,
) -> None:
    metadata = json.loads((release_bundle / "release.json").read_text(encoding="utf-8"))
    archive = release_bundle / metadata["platforms"]["claude"]["archive"]
    archive.write_bytes(archive.read_bytes() + b"tampered")
    destination = claude_workspace / "marketplace"

    with pytest.raises(lifecycle.LifecycleError, match="release verification failed"):
        lifecycle.prepare_verified_marketplace(release_bundle, destination)

    assert not destination.exists()


def test_prepare_uses_verified_snapshot_when_source_changes_after_verification(
    release_bundle: Path,
    claude_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_verify = lifecycle._verify_release_independently

    def verify_then_replace_source(snapshot: Path) -> dict[str, object]:
        result = original_verify(snapshot)
        metadata = json.loads((release_bundle / "release.json").read_text(encoding="utf-8"))
        metadata["mcp_url"] = "https://attacker.invalid/mcp"
        (release_bundle / "release.json").write_text(json.dumps(metadata), encoding="utf-8")
        return result

    monkeypatch.setattr(lifecycle, "_verify_release_independently", verify_then_replace_source)
    destination = claude_workspace / "marketplace"

    release = lifecycle.prepare_verified_marketplace(release_bundle, destination)

    assert release.mcp_url == MCP_URL
    lifecycle.remove_readonly_tree(destination)


def test_prepare_rejects_snapshot_mutation_after_verification(
    release_bundle: Path,
    claude_workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_verify = lifecycle._verify_release_independently

    def verify_then_mutate_snapshot(snapshot: Path) -> dict[str, object]:
        result = original_verify(snapshot)
        metadata_path = snapshot / "release.json"
        metadata_path.chmod(0o644)
        metadata_path.write_bytes(metadata_path.read_bytes() + b" ")
        return result

    monkeypatch.setattr(lifecycle, "_verify_release_independently", verify_then_mutate_snapshot)

    with pytest.raises(lifecycle.LifecycleError, match="snapshot changed after verification"):
        lifecycle.prepare_verified_marketplace(release_bundle, claude_workspace / "marketplace")


def test_real_profile_paths_cover_all_relevant_claude_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    config = tmp_path / "custom-config"
    plugin_cache = tmp_path / "custom-cache"
    secure_storage = tmp_path / "custom-secure-storage"
    xdg_cache = tmp_path / "cache"
    xdg_config = tmp_path / "config"
    xdg_data = tmp_path / "data"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config))
    monkeypatch.setenv("CLAUDE_CODE_PLUGIN_CACHE_DIR", str(plugin_cache))
    monkeypatch.setenv("CLAUDE_SECURESTORAGE_CONFIG_DIR", str(secure_storage))
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))

    paths = set(lifecycle._real_profile_paths())

    expected = {
        config / "plugins",
        config / "backups",
        plugin_cache,
        secure_storage,
        home / ".claude.json",
        xdg_cache / "claude",
        xdg_cache / "claude-cli-nodejs",
        xdg_config / "claude",
        xdg_data / "claude",
        xdg_data / "claude-code",
        lifecycle.REPOSITORY_ROOT / ".claude",
    }
    assert expected <= paths
    assert {path.resolve(strict=False) for path in expected} <= paths
    roots = set(lifecycle._real_config_roots())
    assert config in roots
    assert config.resolve(strict=False) in roots
    assert config / "file-history" not in paths


@pytest.mark.claude_real_cli
def test_real_claude_cli_installs_exact_verified_release(release_bundle: Path) -> None:
    claude = shutil.which("claude")
    assert claude is not None
    temporary_root = lifecycle._temporary_root()
    before = set(temporary_root.glob("sensai-claude-profile-*"))

    lifecycle.run_lifecycle(release_bundle, claude)

    assert set(temporary_root.glob("sensai-claude-profile-*")) == before
