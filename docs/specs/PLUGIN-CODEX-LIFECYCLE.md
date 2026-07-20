# PLUGIN-CODEX-LIFECYCLE: Codex Acceptance

## Supported Surface

The acceptance targets the locally installed Codex plugin marketplace commands:

- `codex plugin marketplace add/remove`
- `codex plugin add/remove`
- `codex mcp list --json`

Codex CLI `0.145.0-alpha.18` has no `plugin install`, `plugin update`, or `plugin uninstall`
subcommands. `plugin add` is the supported install operation and, when repeated after a local
marketplace package version changes, replaces the enabled installed version. Marketplace
`upgrade` applies only to configured Git marketplace snapshots, so it is not used for this local,
offline acceptance.

## Acceptance Boundary

`scripts/test_codex_lifecycle.py` performs the complete acceptance without network access or
login. It builds and validates two Codex payload versions, creates a local marketplace inside a
temporary `CODEX_HOME`, installs version 1 with `plugin add`, verifies the MCP URL through
`mcp list`, replaces the local package with version 2, repeats `plugin add`, and verifies the new
MCP URL. It then removes the plugin and marketplace and proves that no plugin payload or MCP
configuration remains.

The script points `HOME`, `TMPDIR`, and XDG state directories into the same isolated profile. It
also fingerprints the real profile's `config.toml` and the exact lifecycle-test cache path before
and after execution, then verifies that the temporary profile itself was deleted. This is a
bounded sentinel check, not a claim that arbitrary filesystem writes outside those supported roots
can be detected while another live Codex process may be updating unrelated state.
