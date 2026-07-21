# Sensai Plugin

Sensai connects Codex or Claude to a remote adviser that helps an AI agent understand the user's
work, compare useful automations, and plan a practical first workflow. The current demo advises the
agent; it does not connect to Gmail, Google Sheets, or other external services on the user's behalf.

## Colleague demo setup: Windows and Codex Desktop

The project owner gives each colleague a temporary invitation key. Do not paste that key into a
chat or save it in source code. Open PowerShell and store it as a User environment variable,
replacing the visible placeholder with the provided key:

```powershell
[Environment]::SetEnvironmentVariable("SENSAI_INVITE_TOKEN", "<invitation-key>", "User")
```

Fully quit Codex Desktop, including any remaining Codex windows, and reopen it so the application
inherits the new environment variable. In a terminal, add the public marketplace and install the
plugin:

```powershell
codex plugin marketplace add grayskripko/sensai-plugin
codex plugin add sensai@sensai
```

Start a new Codex chat and try this first prompt:

> I work in marketing. Help me choose one routine that would be useful to automate first.

Build and lifecycle contracts are documented under `docs/specs/`.

After changing `payload-src`, regenerate and verify the committed public marketplace with:

```sh
uv run python scripts/sync_public_marketplace.py
uv run python scripts/sync_public_marketplace.py --check
```

The repository is also an installable Python package. External E2E drivers can import its public
acceptance helpers from a fresh clone with `uv run python /path/to/driver.py`; they do not need to
manually add `src/` to `PYTHONPATH`.

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
