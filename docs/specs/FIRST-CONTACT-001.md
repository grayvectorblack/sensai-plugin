# FIRST-CONTACT-001: One-request Sensai installation

## User journey

The supported journey starts with exactly one natural request:

> Open https://github.com/grayvectorblack/sensai-plugin, follow its installation instructions without technical details, and continue automatically; if a new chat is required, give me exactly this copyable sentence: Continue with Sensai and contact Sensai automatically.

The request first directs the installing agent to the transparent public README instead of choosing
an installer in advance. In the same sentence, it requires the agent to keep installation mechanics
private, continue automatically after installation, and provide the exact safe handoff already
embedded in the request only when the platform requires the person to start a fresh chat. The agent
then detects Codex versus Claude Code, installs through the platform's native plugin commands, loads
the plugin in the required fresh context, and starts a natural first conversation with Sensai.

A brief ordinary-language acknowledgement is allowed while installation is in progress. It must
not expose commands, paths, versions, a plugin manager, MCP, transport, or other installation
mechanics.

## Platform boundary

Codex loads a newly installed plugin in a fresh task. The installing agent creates that task and
greets Sensai naturally when its host exposes task creation. If the running Claude Code session
does not expose the newly installed plugin, the agent starts a fresh session when its host permits
that. Only when the platform requires the person to start the fresh context does the agent provide
the exact safe continuation sentence from the request and no other setup request. It never asks the
person to introduce themselves or greet Sensai manually.

The platforms may still require the person to approve plugin installation and, once server OAuth is
available, authorize Sensai in a browser. Those are platform security boundaries, not additional
Sensai setup commands.

The user's agent performs every other automatable step. It may communicate with Sensai in concise
English, while communicating with the person in the person's language. Sensai addresses the user's
agent, not the person directly.

## Authorization boundary

The plugin contains no credential. Its MCP client contacts the configured HTTPS endpoint and uses
the server's standard OAuth metadata. The user's agent starts its host's native MCP sign-in when
needed and keeps the native callback listener alive until the login command succeeds or exits. A
yielded long-running terminal operation is polled throughout Codex's native five-minute callback
window rather than abandoned. If that window actually expires, the agent starts a fresh native
login itself instead of asking the person to run a command. The person completes the browser login,
and the agent retries the original natural greeting. If OAuth is unavailable, first contact fails
clearly instead of requesting a copied credential.
