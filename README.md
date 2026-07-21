# Sensai Plugin

Public plugin packaging for connecting Codex and Claude to the Sensai MCP server.

Build and lifecycle contracts are documented under `docs/specs/`.

Run the offline Codex package lifecycle acceptance with:

```sh
./scripts/test_codex_lifecycle.py
```

The command requires `codex` on `PATH`; it redirects `CODEX_HOME`, `HOME`, `TMPDIR`, and XDG roots
to a temporary profile and does not read credentials or contact the MCP server. It checks that the
real config and exact lifecycle-test cache sentinel remain unchanged.

Run the isolated Claude Code package lifecycle acceptance with an already-built release:

```sh
uv run python scripts/test_claude_lifecycle.py --bundle /path/to/release
```

The command requires `claude` on `PATH`. It uses temporary Claude, secure-storage, home,
plugin-cache, temp, and XDG roots; validates local marketplace registration, user-scope installation,
plugin listing, and exact MCP discovery. It verifies the installed plugin payload byte-for-byte against
the reviewed read-only marketplace payload, then removes the temporary profile and fails if the real
Claude profile boundary changes. It does not test CLI updates, uninstall, marketplace removal, endpoint
connectivity, or model behavior.
