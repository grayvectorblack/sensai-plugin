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
