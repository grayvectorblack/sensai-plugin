# Sensai Plugin

Sensai advises a user's AI agent. It helps the agent choose useful work scenarios, understand how
to implement them, install connectors locally, and recover from setup problems. Sensai does not
connect to external accounts or run code on the user's computer.

Public source: <https://github.com/grayvectorblack/sensai-plugin>

> **Privacy:** Sensai receives only text that the user's AI agent deliberately sends through the
> Sensai MCP server. Nothing is collected from local files, accounts, or chat history implicitly.
> Sensai's opening questions ask about the person's profession and commonly used programs so its
> advice can be relevant.

Sensai may return advice, architecture, detailed implementation instructions, and non-executed
reference snippets. The user's own AI agent writes and reviews any resulting code, installs its
dependencies, runs it, and verifies it locally through the normal controls of Codex or Claude.
Connector setup also happens locally. The person completes any authorization or consent screen.

## Install

Give your AI agent exactly this request:

```text
Установи Sensai https://github.com/grayvectorblack/sensai-plugin
```

The agent must read this README, identify whether it is running in Codex or Claude Code, and use
that platform's native plugin commands. No downloaded installer script is required.

### Codex

The agent adds this GitHub repository as a marketplace and installs `sensai@sensai` using
`codex plugin marketplace add` and `codex plugin add`. Codex loads a newly installed plugin in a
fresh task. The installing agent should create that task itself with `Continue Sensai setup` as its
initial message when the host exposes task creation. A plugin cannot hot-load itself into the task
that installed it. If the host does not let the installing agent create a task, it must state that
one fresh-task action remains instead of claiming that setup continued automatically.

### Claude Code

The agent adds this GitHub repository with `claude plugin marketplace add`, installs
`sensai@sensai` at user scope with `claude plugin install`, and reloads plugins through Claude's
native mechanism. If that mechanism is not exposed to the installing agent, it must state the one
remaining reload action instead of claiming that Sensai is already available.

Both public marketplace layouts are generated from the same reviewed source under `payload-src/`:

- Codex: `.agents/plugins/marketplace.json`
- Claude Code: `.claude-plugin/marketplace.json`
- shared plugin payload: `plugins/sensai/`

## MCP authorization status

The plugin configures one remote MCP server at `https://black-vector.com/sensai/mcp`. It contains
no static access token, invitation code, authorization header, or environment-token fallback.

The intended authorization flow is native MCP OAuth. The first unauthenticated connection causes
the MCP client to discover the server's OAuth metadata, open the authorization page, and store and
refresh its own credential. **That server-side OAuth flow is not deployed yet.** Until it is
deployed, the first Sensai MCP request must fail clearly as unavailable; the plugin must not claim
that authorization succeeded and must not fall back to a manually stored token.

After OAuth is deployed and a newly installed plugin is loaded, the skill calls `tell_sensai`,
relays Sensai's introduction, and asks what the person does for work and which one to five programs
or websites they use most often.

## Development

Regenerate and verify both public marketplace layouts after changing `payload-src/`:

```sh
uv run python scripts/sync_public_marketplace.py
uv run python scripts/sync_public_marketplace.py --check
```

Build and verify the immutable release artifacts:

```sh
uv run python scripts/build_release.py --output /path/to/release
uv run python scripts/verify_release.py --bundle /path/to/release
```

The repository also contains isolated lifecycle checks for the installed Codex and Claude CLIs.
They use temporary profiles and do not authenticate to the production MCP server.
