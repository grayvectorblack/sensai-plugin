# Sensai Plugin

Sensai connects Codex or Claude to a remote adviser that helps an AI agent understand the user's
work, compare useful automations, and prepare a practical first workflow. After the user selects a
vetted automation, the plugin may create its declared local files and run its generator plus an
independent verification through Codex's normal file and command approval. The first demo package
turns a sample marketing CSV into a verified weekly Markdown report. It does not connect to Gmail,
Google Sheets, or other external services on the user's behalf.

## Colleague demo setup: Windows and Codex Desktop

The project owner gives each colleague one private link shaped like
`https://black-vector.com/sensai/invite#...`. Send that link to Codex with one request: "Install
Sensai from this invitation." Codex reads the fixed invitation page and this repository, downloads
[`bootstrap/install-sensai.ps1`](bootstrap/install-sensai.ps1) together with
[`bootstrap/MANIFEST.sha256`](bootstrap/MANIFEST.sha256), verifies that the script's SHA-256
checksum matches the manifest, and runs the helper with the original invitation URL. The checksum
identifies the exact reviewed bootstrap file in this public repository.

The helper installs the public marketplace and plugin first. Only after installation succeeds does
it redeem the one-time code in a request body. The one-time code appears in the original request to
Codex by design; after successful redemption it cannot be used again. The longer-lived access value
is never displayed in chat, command output, or a command line. It is written only to the current
Windows user's persistent environment after all Codex installation child processes have finished.
This bootstrap currently supports Windows Codex Desktop only and relies on the current user's
Windows registry permissions to keep the stored value unavailable to other Windows accounts. Apps
running as the same Windows user can still read that user's environment.

Codex loads newly installed plugin instructions and tools only in a fresh session. After the
installation finishes, fully restart Codex Desktop and start a new chat. This restart and new chat
are unavoidable because the installation conversation cannot load a plugin that did not exist when
that conversation started. In the fresh chat, use a natural request such as:

> Let's get started with Sensai.

The agent contacts Sensai, relays its introduction, and asks what the colleague does for work and
which one to five programs or websites they use most often. The colleague does not need to enter
plugin commands, handle credentials, or describe an automation idea in this second chat.

If installation fails before Sensai starts, the agent may send one short error description to the
public `POST https://black-vector.com/sensai/install-help/search` endpoint. It must not include
credentials, files, or chat history.

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
