#!/usr/bin/env python3
"""Install one verified Sensai release through an isolated Claude marketplace."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from sensai_plugin.claude_acceptance import (  # noqa: E402
    ClaudeAcceptanceError,
    installed_claude_plugin,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        with installed_claude_plugin(arguments.bundle) as installed:
            selector = installed.selector
            version = installed.version
            mcp_url = installed.mcp_url
    except (ClaudeAcceptanceError, BaseExceptionGroup) as error:
        parser.exit(1, f"Claude lifecycle failed: {error}\n")

    print(f"PASS selector={selector}")
    print(f"PASS version={version}")
    print(f"PASS mcp={mcp_url}")
    print("PASS verified-release=independent exact-bytes=read-only")
    print("PASS isolated-profile=removed real-plugin-lifecycle-boundary=unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
