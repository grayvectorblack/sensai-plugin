#!/usr/bin/env python3
"""Synchronize the repository's directly installable Codex marketplace."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from sensai_plugin.package_builder import build_packages  # noqa: E402
from sensai_plugin.package_runner import (  # noqa: E402
    TRUSTED_PACKAGE_DIGESTS,
    canonical_package_digest,
)

MARKETPLACE_PATH = REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGIN_PATH = REPOSITORY_ROOT / "plugins" / "sensai"
RUNNER_SOURCE_PATH = REPOSITORY_ROOT / "src" / "sensai_plugin" / "package_runner.py"
RUNNER_PAYLOAD_PATH = (
    REPOSITORY_ROOT
    / "payload-src"
    / "shared"
    / "skills"
    / "sensai"
    / "scripts"
    / "package_runner.py"
)
DEFAULT_SERVER_ROOT = REPOSITORY_ROOT.parent / "server"
TRUST_RECORD_PATTERN = re.compile(
    r"TRUSTED_PACKAGE_DIGESTS = \{\n"
    r'    "marketing-csv-weekly-report": \(\n'
    r'        "[^"]+"\n'
    r"    \),\n"
    r"\}"
)


def _server_package_payload(server_root: Path) -> dict[str, object]:
    package_root = server_root / "src" / "sensai" / "workflows" / "marketing_csv_weekly_report"
    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    records: list[dict[str, object]] = []
    for name in manifest["files"]:
        content = (package_root / name).read_text(encoding="utf-8")
        encoded = content.encode("utf-8")
        records.append(
            {
                "name": name,
                "content": content,
                "byte_length": len(encoded),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    return {
        "package": {
            "id": manifest["id"],
            "manifest": manifest,
            "files": records,
        }
    }


def _synchronize_trust_record(*, check: bool, server_root: Path) -> bool:
    payload = _server_package_payload(server_root)
    package = payload["package"]
    assert isinstance(package, dict)
    package_id = package["id"]
    assert isinstance(package_id, str)
    digest = canonical_package_digest(payload)
    expected = {package_id: digest}
    if check:
        return expected == TRUSTED_PACKAGE_DIGESTS

    source = RUNNER_SOURCE_PATH.read_text(encoding="utf-8")
    replacement = (
        f'TRUSTED_PACKAGE_DIGESTS = {{\n    "{package_id}": (\n        "{digest}"\n    ),\n}}'
    )
    updated, count = TRUST_RECORD_PATTERN.subn(replacement, source)
    if count != 1:
        raise RuntimeError("could not locate the generated package trust record")
    RUNNER_SOURCE_PATH.write_text(updated, encoding="utf-8", newline="\n")
    return True


def _marketplace_bytes() -> bytes:
    marketplace = {
        "name": "sensai",
        "interface": {"displayName": "Sensai"},
        "plugins": [
            {
                "name": "sensai",
                "source": {"source": "local", "path": "./plugins/sensai"},
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": "Productivity",
            }
        ],
    }
    return (json.dumps(marketplace, indent=2, ensure_ascii=False) + "\n").encode()


def _regular_files(root: Path) -> dict[str, bytes]:
    if not root.is_dir() or root.is_symlink():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
    }


def synchronize(*, check: bool, server_root: Path = DEFAULT_SERVER_ROOT) -> bool:
    if not _synchronize_trust_record(check=check, server_root=server_root):
        return False
    runner_bytes = RUNNER_SOURCE_PATH.read_bytes()
    if check:
        if not RUNNER_PAYLOAD_PATH.is_file() or RUNNER_PAYLOAD_PATH.read_bytes() != runner_bytes:
            return False
    else:
        RUNNER_PAYLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
        RUNNER_PAYLOAD_PATH.write_bytes(runner_bytes)

    with tempfile.TemporaryDirectory(prefix="sensai-public-marketplace-") as temporary:
        built = build_packages(
            source_root=REPOSITORY_ROOT / "payload-src",
            output_root=Path(temporary) / "packages",
        )
        expected_plugin = _regular_files(built.codex)
        expected_marketplace = _marketplace_bytes()

        if check:
            return (
                _regular_files(PLUGIN_PATH) == expected_plugin
                and MARKETPLACE_PATH.is_file()
                and MARKETPLACE_PATH.read_bytes() == expected_marketplace
            )

        if PLUGIN_PATH.is_symlink():
            raise RuntimeError("public plugin path must not be a symlink")
        if PLUGIN_PATH.exists():
            shutil.rmtree(PLUGIN_PATH)
        PLUGIN_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(built.codex, PLUGIN_PATH)
        MARKETPLACE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MARKETPLACE_PATH.write_bytes(expected_marketplace)
        return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--server-root", type=Path, default=DEFAULT_SERVER_ROOT)
    arguments = parser.parse_args()
    if not synchronize(check=arguments.check, server_root=arguments.server_root):
        parser.exit(1, "public Codex marketplace is out of date\n")


if __name__ == "__main__":
    main()
