# FIRST-CONTACT-001: One-request Sensai installation

## User journey

The supported journey starts with exactly one natural request:

> Установи Sensai https://github.com/grayvectorblack/sensai-plugin

The installing agent reads the public README, detects Codex versus Claude Code, installs through the
platform's native plugin commands, loads the plugin in the required fresh context, and starts a
natural first conversation with Sensai. The person is not asked to type another setup phrase.

## Platform boundary

Codex loads a newly installed plugin in a fresh task. The installing agent creates that task and
greets Sensai naturally when its host exposes task creation. Claude Code reloads newly installed
plugins with `/reload-plugins` and can continue in the current session.

The platforms may still require the person to approve plugin installation and, once server OAuth is
available, authorize Sensai in a browser. Those are platform security boundaries, not additional
Sensai setup commands.

The user's agent performs every other automatable step. It may communicate with Sensai in concise
English, while communicating with the person in the person's language. Sensai addresses the user's
agent, not the person directly.

## Authorization boundary

The plugin contains no credential. Its MCP client contacts the configured HTTPS endpoint without a
static token. Native MCP OAuth is expected to begin from the resulting unauthenticated response.
Server OAuth is not deployed yet, so current first contact fails clearly instead of using a hidden
legacy credential path.
