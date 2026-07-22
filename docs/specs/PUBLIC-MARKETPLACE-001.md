# PUBLIC-MARKETPLACE-001: Native GitHub marketplaces

## User journey

The person gives Codex or Claude Code one natural request containing only the public GitHub
repository. The agent reads the repository README, identifies its platform, and installs Sensai
through that platform's native marketplace and plugin commands. No bootstrap script, invitation URL,
one-time code, or manually stored bearer token is part of installation.

## Contract

- `.agents/plugins/marketplace.json` is the Codex marketplace root.
- `.claude-plugin/marketplace.json` is the Claude Code marketplace root.
- Both catalogs point only to `./plugins/sensai`.
- `plugins/sensai` combines the two platform manifests with one byte-identical shared MCP
  configuration and Sensai skill generated from the reviewed `payload-src` allowlist.
- The public MCP configuration contains only its HTTPS URL and transport type. Authentication is
  native MCP OAuth; no static authorization header or environment-token fallback is packaged.
- `scripts/sync_public_marketplace.py` regenerates all three public paths, and `--check` fails when
  committed output is missing or stale.

## Current server dependency

The plugin is prepared for native OAuth discovery, but it must not claim authorization works until
the MCP server publishes the required OAuth metadata and authorization endpoints. Until then, an
unauthenticated request fails clearly.

## Evidence

`tests/test_github_first_contract.py` covers the public installation and authorization boundary.
`tests/test_public_marketplace.py` independently rebuilds and compares the committed public bytes.
The package tests cover the exact source allowlist, secret rejection, path isolation, and hashes.
