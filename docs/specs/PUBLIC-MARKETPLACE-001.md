# PUBLIC-MARKETPLACE-001: Direct Codex Marketplace

## Colleague scenario

A colleague gives Codex the public repository `grayskripko/sensai-plugin`. Codex can add that
repository as a marketplace without building source code or reading private server files. The
marketplace exposes one ready `sensai` plugin configured for the public HTTPS MCP endpoint. The
repository contains no invitation or access key. A colleague gives her agent one fixed invitation
page URL with a one-time code in its fragment. The Windows bootstrap redeems the code and writes the
issued access value directly to the user environment without displaying it.

## Contract

- `.agents/plugins/marketplace.json` is the marketplace root and points only to
  `./plugins/sensai`.
- `plugins/sensai` is byte-identical to the Codex payload generated from the reviewed
  `payload-src` allowlist.
- `scripts/sync_public_marketplace.py` regenerates both paths, and `--check` fails when committed
  output is missing or stale.
- The public payload contains only the plugin manifest, MCP configuration, Sensai skill, and their
  SHA-256 manifest. It never contains an invitation key.

## Evidence

`tests/test_public_marketplace.py` rebuilds the Codex payload independently and compares every
committed byte. The existing package tests cover the source allowlist, secret rejection, path
isolation, and deterministic hashes.
