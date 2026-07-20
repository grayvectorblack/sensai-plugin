# PLUGIN-CODEX-LOCAL-INSTALL: Codex Local Acceptance

## Supported CLI

Acceptance targets the installed official Codex CLI and these supported commands:

- `codex plugin marketplace add <local-directory> --json`
- `codex plugin add <plugin>@<marketplace> --json`
- `codex mcp list --json`

The accepted CLI evidence is `codex-cli 0.145.0-alpha.18`. That version has no separate
`plugin install` command; `plugin add` is its install operation.

## Input And Trust Boundary

`scripts/test_codex_lifecycle.py` accepts one already-built release through `--bundle`. It never
rebuilds a package, edits an archive, or installs an archive directly. Before invoking `codex`, it
runs `scripts/verify_release.py` as an independent process and requires its positive JSON result.
Any verifier failure stops the lifecycle before the first Codex command.

The lifecycle then selects the exact Codex archive named by `release.json`, checks that neither
metadata nor archive bytes changed after verification, and extracts that archive exactly once into
a temporary local marketplace. Extraction rejects path traversal, links, non-regular members,
duplicates, oversized input, non-read-only archive entries, and byte hashes that differ from
release metadata. It independently checks the plugin `MANIFEST.sha256` and
`sensai-mcp-attestation.json`, then makes every extracted file and directory read-only.

## Isolated Lifecycle

The lifecycle creates a temporary profile with separate `CODEX_HOME`, `HOME`, `TMPDIR`, `TMP`,
`TEMP`, and XDG directories. It passes through only the executable path, locale, timezone, and TLS
certificate locations. The local marketplace directory, not the ZIP archive, is given to Codex.

Acceptance proves all of the following:

- the marketplace name and `plugin@marketplace` selector come from verified extracted bytes;
- the installed version equals `release.json` and the platform manifest;
- the installed payload bytes equal the read-only marketplace payload;
- `codex mcp list --json` exposes exactly one Sensai server at the release MCP URL;
- the source release bytes remain unchanged;
- the temporary profile is removed;
- the complete real-profile boundary mutable by this lifecycle has an identical exact byte
  fingerprint before and after: `config.toml` and its temporary variants, Codex global-state files,
  `.tmp/marketplaces`, Sensai-owned entries under the shared `.tmp/plugins` checkout, and the
  `sensai-local` plugin cache;
- if `CODEX_HOME` is a symlink, both the configured link and its resolved target are bound into the
  fingerprint.

The shared `.tmp/plugins` directory is Codex's large catalog checkout. The local Sensai lifecycle
does not own its Git data or other vendors' `plugins/<name>` trees, so those bytes are not traversed.
Only Sensai-named entries at its root, `plugins/`, and `.agents/plugins/` are fingerprinted, along
with the existence and type of those parent directories. Large unrelated desktop state such as
sessions, logs, memories, binaries, and caches for other plugins is likewise outside the mutable
surface of these exact commands. The lifecycle separately isolates `CODEX_HOME`, `HOME`, every XDG
root, and every temporary-directory variable, so the official CLI has no configured path back to
any part of the real profile.

## Executable Evidence

`tests/test_codex_lifecycle.py` first proves that archive tampering is rejected before a fake
Codex executable can run. Its green path then proves the exact three-command sequence, directory
installation rather than direct ZIP installation, read-only extracted marketplace, isolated
profile, exact selector/version/URL, bundle immutability, and cleanup. The final acceptance runs
the same script once against the installed official Codex CLI and one release produced by the
current builder.
