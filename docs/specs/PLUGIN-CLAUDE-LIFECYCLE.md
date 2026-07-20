# PLUGIN-CLAUDE-LIFECYCLE: Isolated Claude Code Installation

## Purpose

Prove the public Claude payload can be validated, installed from a local marketplace, updated to
a second version, discovered as an MCP-providing plugin, uninstalled, and removed using the real
Claude Code CLI without changing the user's Claude profile.

## Acceptance

`scripts/test_claude_lifecycle.py` exercises commands supported by the locally installed Claude
Code 2.1.193. The script requires that exact version before parsing any lifecycle output:

1. Build two deterministic Claude payloads and verify each `MANIFEST.sha256`.
2. Run `claude plugin validate --strict` against the plugin and marketplace.
3. Add the local marketplace at user scope and prove its isolated path through
   `claude plugin marketplace list --json`.
4. Install version `0.1.0` and prove through `claude plugin list --json` that it is enabled at user
   scope, resides in the isolated plugin cache, and exposes the expected HTTP MCP configuration.
5. Run `claude mcp get plugin:sensai:sensai` and require Claude's namespaced dynamic MCP entry,
   transport, and URL.
6. Replace the local marketplace payload, run the native marketplace and plugin update commands,
   and repeat the structured plugin and MCP assertions for version `0.1.1`.
7. Uninstall the plugin and prove both the installed-plugin list and MCP discovery no longer contain
   Sensai. Any `.orphaned_at` cache markers are reported as an observation, not required as a
   supported uninstall behavior or misreported as immediate cache deletion.
8. Remove the marketplace, exit the temporary-directory boundary, and prove the entire isolated
   profile was deleted.

## Isolation Boundary

Every lifecycle command receives temporary `CLAUDE_CONFIG_DIR`,
`CLAUDE_SECURESTORAGE_CONFIG_DIR`, `CLAUDE_CODE_PLUGIN_CACHE_DIR`, `HOME`, `TMP`, `TEMP`,
`TMPDIR`, `XDG_CACHE_HOME`, `XDG_CONFIG_HOME`, and `XDG_DATA_HOME` values. The updater is disabled.
Claude credential environment variables and plugin seed injection are removed from the command
environment, and commands run from the temporary work directory. Subprocesses receive a minimal
allowlist containing only `PATH`, locale, timezone, and optional TLS certificate locations before
the isolated roots are added; arbitrary parent variables are never inherited.

Each Claude command starts in a new process session. A timeout terminates the complete process
group, waits two seconds, and then kills the complete group if necessary, preserving captured
stdout and stderr in the failure evidence.

Before and after the lifecycle, the acceptance fingerprints an explicit allowlist of
mutation-sensitive paths observed for these commands: the `~/.claude` symlink and its target string,
resolved `settings.json`, resolved config-local `.claude.json`, the complete resolved `backups` and
`plugins` trees, home-level `.claude.json`, known Claude XDG cache/config/data roots, and the
repository's `.claude` directory. It prints every logical and resolved sentinel and fails if any
allowlisted content changes. It does not fingerprint the resolved configuration directory as a
whole or claim to monitor arbitrary files elsewhere in that tree.

## Claim Boundary

The acceptance proves CLI validation, lifecycle state, and MCP configuration discovery. The
`mcp get` command may attempt an endpoint health check and may report either a connected or failed
status; connectivity, authentication, tool invocation, and model behavior are deliberately not
claimed here. Cache payloads can remain orphan-marked after the supported uninstall command, but
they are removed when the isolated profile is deleted.

Run from the plugin repository:

```sh
./scripts/test_claude_lifecycle.py
```
