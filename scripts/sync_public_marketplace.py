#!/usr/bin/env python3
"""Synchronize the repository's directly installable Codex marketplace."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from sensai_plugin.package_builder import build_packages  # noqa: E402

MARKETPLACE_PATH = REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json"
PLUGIN_PATH = REPOSITORY_ROOT / "plugins" / "sensai"


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


def synchronize(*, check: bool) -> bool:
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
    arguments = parser.parse_args()
    if not synchronize(check=arguments.check):
        parser.exit(1, "public Codex marketplace is out of date\n")


if __name__ == "__main__":
    main()
