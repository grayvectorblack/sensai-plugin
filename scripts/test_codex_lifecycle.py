#!/usr/bin/env python3
"""Install one verified Codex release through an isolated local marketplace."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from sensai_plugin.codex_acceptance import (  # noqa: E402
    CodexAcceptanceError,
    installed_codex_plugin,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        with installed_codex_plugin(arguments.bundle) as installed:
            selector = installed.selector
            version = installed.version
            mcp_url = installed.mcp_url
    except (CodexAcceptanceError, BaseExceptionGroup) as error:
        parser.exit(1, f"codex lifecycle failed: {error}\n")

    print(f"PASS selector={selector}")
    print(f"PASS version={version}")
    print(f"PASS mcp={mcp_url}")
    print("PASS verified-release=independent exact-bytes=read-only")
    print("PASS isolated-profile=removed real-plugin-lifecycle-boundary=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
