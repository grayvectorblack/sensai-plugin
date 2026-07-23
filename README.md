# Sensai Plugin

Sensai is an AI agent that advises another AI agent. It helps the user's agent choose useful work
scenarios, implement them, set up connectors locally, and recover from setup problems. Sensai does
not connect to external accounts or run code on the user's computer.

Sensai may return advice, architecture, detailed implementation instructions, and non-executed
reference snippets. The user's own AI agent writes and reviews any resulting code, installs its
dependencies, runs it, and verifies it locally through the normal controls of Codex or Claude.
Connector setup also happens locally. The person completes any authorization or consent screen.

## Installation (human)

This is the person's only action:

```text
Install Sensai from https://github.com/grayvectorblack/sensai-plugin
```

## After installation (AI agent)

Without waiting for another human command, send a brief, natural greeting through the installed
Sensai MCP. This starts native sign-in if needed and returns the next instruction.

### Codex

Add `grayvectorblack/sensai-plugin` as a marketplace and install `sensai@sensai` using
`codex plugin marketplace add` and `codex plugin add`. Codex loads the installed plugin in a fresh
task. When the host supports task creation, create that task and start the first conversation with
Sensai. Otherwise, tell the person that opening one fresh task is the only remaining action; never
claim that the current task hot-loaded the plugin.

### Claude Code

Add `grayvectorblack/sensai-plugin` with `claude plugin marketplace add` and install
`sensai@sensai` at user scope with `claude plugin install`. If the current session does not expose
the installed plugin, start a fresh session when the host permits that. Otherwise, tell the person
that restarting Claude Code is the only remaining action; never claim that Sensai is already
loaded.

Both public marketplace layouts are generated from the same reviewed source under `payload-src/`:

- Codex: `.agents/plugins/marketplace.json`
- Claude Code: `.claude-plugin/marketplace.json`
- shared plugin payload: `plugins/sensai/`

## MCP authorization

The plugin configures one remote MCP server at `https://black-vector.com/sensai/mcp`. It contains
no credential or custom authorization helper.

The first unauthenticated connection lets the MCP client discover the standard OAuth metadata and
use its native sign-in flow. The user's agent starts that flow when needed; the person only
completes the browser login and consent screen. The client stores and refreshes its own credential.
If OAuth is unavailable, the request must fail clearly instead of asking the person to copy
credentials into chat or configuration.

After authorization, the user's agent continues the same greeting. Sensai introduces itself and
guides the agent through the next useful questions. The two agents may communicate in concise
English to save tokens; the user's agent speaks to the person in the person's language.

## Development

Regenerate and verify both public marketplace layouts after changing `payload-src/`:

```sh
uv run python scripts/sync_public_marketplace.py
uv run python scripts/sync_public_marketplace.py --check
```

Build and verify the immutable release artifacts:

```sh
uv run python scripts/build_release.py --output /path/to/release --mcp-url https://black-vector.com/sensai/mcp
uv run python scripts/verify_release.py --bundle /path/to/release
```

The repository also contains isolated lifecycle checks for the installed Codex and Claude CLIs.
They use temporary profiles and do not authenticate to the production MCP server.
