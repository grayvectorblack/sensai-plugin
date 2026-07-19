"""Boundary for deterministic Sensai plugin package generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class SourceTreeError(ValueError):
    """Base error for an incomplete, unexpected, or unsafe payload source tree."""


class UnexpectedSourceFileError(SourceTreeError):
    """Raised when payload source contains a file outside the explicit allowlist."""


class MissingRequiredSourceFileError(SourceTreeError):
    """Raised when an allowlisted payload source file is absent."""


class UnsafeSourceError(SourceTreeError):
    """Raised when source material could escape or expose private data."""


@dataclass(frozen=True)
class BuiltPackages:
    """Roots of the independently installable platform payloads."""

    codex: Path
    claude: Path


def build_packages(*, source_root: Path, output_root: Path) -> BuiltPackages:
    """Build deterministic Codex and Claude payloads from allowlisted source files."""
    del source_root, output_root
    raise NotImplementedError("PLUGIN-PACKAGE-001")
