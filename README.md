# Sensai Plugin

Sensai is an AI agent that advises another AI agent. It helps the user's agent choose useful work
scenarios, implement them, set up connectors locally, and recover from setup problems. Sensai does
not connect to external accounts or run code on the user's computer.

Public source: <https://github.com/grayvectorblack/sensai-plugin>

> **Privacy:** Sensai receives only text that the user's AI agent explicitly sends to it.

Sensai may return advice, architecture, detailed implementation instructions, and non-executed
reference snippets. The user's own AI agent writes and reviews any resulting code, installs its
dependencies, runs it, and verifies it locally through the normal controls of Codex or Claude.
Connector setup also happens locally. The person completes any authorization or consent screen.

## Install

Give your AI agent exactly this request:

```text
Установи Sensai https://github.com/grayvectorblack/sensai-plugin
```

After this one request, the user's agent reads this README, identifies whether it is running in
Codex or Claude Code, and performs every remaining automatable step with that platform's native
plugin commands. The person may still need to approve installation and complete native OAuth, but
does not need to enter another Sensai command. No downloaded installer script is required.

### Codex

The agent adds `grayvectorblack/sensai-plugin` as a marketplace and installs `sensai@sensai` using
`codex plugin marketplace add` and `codex plugin add`. Codex loads the installed plugin in a fresh
task. When its host exposes task creation, the installing agent creates that task itself and starts
a natural first conversation with Sensai. Otherwise, it tells the person that opening one fresh
task is the only remaining action; it never claims the current task hot-loaded the plugin.

### Claude Code

The agent adds `grayvectorblack/sensai-plugin` with `claude plugin marketplace add` and installs
`sensai@sensai` at user scope with `claude plugin install`. If the running Claude Code session does
not expose the newly installed plugin, the agent starts a fresh session when its host permits that.
Otherwise, it tells the person that restarting Claude Code is the only remaining action; it never
claims that Sensai is already loaded.

Both public marketplace layouts are generated from the same reviewed source under `payload-src/`:

- Codex: `.agents/plugins/marketplace.json`
- Claude Code: `.claude-plugin/marketplace.json`
- shared plugin payload: `plugins/sensai/`

## MCP authorization

The plugin configures one remote MCP server at `https://black-vector.com/sensai/mcp`. It contains
no credential or custom authorization helper.

When the server-side OAuth switch is live, the first unauthenticated connection lets the MCP client
discover the standard OAuth metadata and use its native sign-in flow. The user's agent starts that
flow when needed; the person only completes the browser login and consent screen. The client stores
and refreshes its own credential. If OAuth is unavailable, the request must fail clearly instead of
asking the person to copy credentials into chat or configuration.

After OAuth is deployed and a newly installed plugin is loaded, the user's agent greets Sensai
naturally. Sensai introduces itself and guides the agent through the next useful questions. The two
agents may communicate in concise English to save tokens; the user's agent speaks to the person in
the person's language.

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
