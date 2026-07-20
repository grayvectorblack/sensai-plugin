# PLUGIN-CLAUDE-LOCAL-INSTALL: Isolated Claude Code Installation

## Purpose

Prove that one exact release bundle built by the current release builder can be independently
verified, installed through Claude Code's local marketplace flow, and discovered as an
MCP-providing plugin without changing the user's real Claude profile.

## Acceptance

`scripts/test_claude_lifecycle.py --bundle <release-directory>` uses the locally installed Claude
Code 2.1.193 and performs one bounded lifecycle:

1. Copy the regular bundle files once into a private read-only snapshot, then invoke
   `scripts/verify_release.py` against that snapshot in a separate process. Reject any snapshot
   change before metadata parsing, during extraction, or after verification.
2. Extract the exact attested Claude marketplace archive once, rejecting unsafe or duplicate
   paths, size limit violations, non-regular entries, and any mismatch with release metadata.
3. Verify every plugin byte against `MANIFEST.sha256`, including the exact MCP attestation, then
   make every extracted file and directory read-only under a writable temporary parent.
4. Create a completely isolated temporary Claude profile, home, plugin cache, secure storage,
   temporary directory, and XDG roots.
5. Run the official commands `claude plugin marketplace add`,
   `claude plugin install sensai@sensai-local --scope user`, `claude plugin list --json`, and
   `claude mcp get plugin:sensai:sensai`.
6. Require the exact selector, release version, user scope, isolated install path, MCP namespace,
   transport, and release MCP URL. Require the extracted marketplace fingerprint to remain exact.
7. Delete the temporary profile and prove the real profile is unchanged. The sentinels cover the
   config root entries and top-level config files, complete plugin cache and backup trees, resolved
   targets, optional secure storage, Claude-specific XDG locations, repository-local `.claude`,
   and home-level `.claude.json`. Unrelated history, projects, and sessions are not traversed.

The lifecycle never rebuilds a release, installs an archive directly, modifies extracted release
files, or uses the user's Claude profile. A tampered bundle fails before the extraction directory
is created.

## Claim Boundary

This proves local marketplace installation and MCP configuration discovery. `claude mcp get` may
report endpoint health, but this acceptance does not claim authentication, model behavior, or a
successful MCP tool call.

Run from the plugin repository after building a bundle once:

```sh
uv run python scripts/test_claude_lifecycle.py --bundle /path/to/release
```

The durable automated real-CLI acceptance is:

```sh
uv run pytest -s -q tests/test_claude_release_lifecycle.py -k real_claude_cli
```
