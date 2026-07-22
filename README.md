# Sensai Plugin

Sensai advises the user's Codex or Claude agent, provides installation and problem-solving
instructions, and may provide transparent reference material. Sensai does not connect external
services or act in user accounts.

Public source: <https://github.com/grayvectorblack/sensai-plugin>

> **Privacy:** Sensai receives only the text that your AI agent deliberately sends to Sensai;
> nothing is collected secretly. The opening questions ask about your profession and commonly used
> programs so Sensai can give relevant guidance.

External connectors are set up locally by the user's AI agent following Sensai's guidance. Sensai
never connects to or acts in the user's external accounts, and the person handles every required
authorization or consent step.

After the user selects a vetted scenario, their AI agent may apply a reviewed package through
Codex's normal file and command approval. The first demo package turns a sample marketing CSV into
a verified, self-contained weekly HTML report.

## Colleague demo setup: Windows and Codex Desktop

The project owner gives each colleague one private link shaped like
`https://black-vector.com/sensai/invite#...`. Send that link to Codex with one request:

> Установи Sensai https://black-vector.com/sensai/invite#...

This single request authorizes the installing agent to install Sensai and continue to Sensai's
first response. Codex reads the fixed invitation page and this repository, downloads
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

Codex loads newly installed plugin instructions and tools only in a fresh chat. The installation
conversation cannot load a plugin that did not exist when that conversation started. After the
bootstrap succeeds, it returns an explicit continuation contract to the installing agent. On Codex
Desktop, when the agent has the supported ability to create a new task, it creates one with
`Continue Sensai setup` as the initial prompt and surfaces it to the colleague. The colleague does
not type a second setup phrase. In that fresh chat the plugin immediately contacts Sensai, relays
its introduction, and asks what the colleague does for work and which one to five programs or
websites they use most often.

If a particular Codex host does not expose a supported way for an agent to create a new chat, the
agent explains that platform limitation and asks the colleague to start one and enter
`Continue Sensai setup`. A full application restart is not part of the normal flow; use it only if
Sensai is still unavailable in a fresh chat. Codex may also require the person to approve running
the reviewed bootstrap. The plugin does not bypass that security boundary.

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
