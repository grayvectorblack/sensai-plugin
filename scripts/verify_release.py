#!/usr/bin/env python3
"""Independently verify one local Sensai plugin release bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from sensai_plugin.release_verifier import (  # noqa: E402
    ReleaseVerificationError,
    verify_release,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        result = verify_release(repository_root=REPOSITORY_ROOT, bundle=arguments.bundle)
    except ReleaseVerificationError as error:
        parser.exit(1, f"release verification failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
