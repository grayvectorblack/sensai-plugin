#!/usr/bin/env python3
"""Build one deterministic local Sensai plugin release bundle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from sensai_plugin.release_builder import build_release  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mcp-url", required=True)
    arguments = parser.parse_args()
    build_release(
        repository_root=REPOSITORY_ROOT,
        output=arguments.output,
        mcp_url=arguments.mcp_url,
    )


if __name__ == "__main__":
    main()
