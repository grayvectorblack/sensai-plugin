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
