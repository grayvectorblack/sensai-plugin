# FIRST-CONTACT-001: One-request Sensai installation

## User journey

The supported Codex Desktop journey starts with one natural user request:

> Установи Sensai <invitation URL>

That request authorizes the installing AI agent to install Sensai and continue through the first
Sensai contact. The agent must not ask the person to type a second setup phrase.

## Platform boundary

Codex makes newly installed plugin skills and MCP tools available only in a new chat. The current
installation chat therefore cannot call `tell_sensai` after installing the plugin. A full Codex
restart is not part of the normal flow.

After a successful install, the bootstrap prints an agent continuation contract. When Codex exposes
its supported new-thread capability, the installing agent must create a fresh chat with
`Continue Sensai setup` as its initial prompt and surface that chat to the user. The newly loaded
Sensai skill then immediately calls `tell_sensai` and relays Sensai's first response.

If the current host does not expose a supported new-thread capability, the agent must state the
actual limitation. It may ask the person to start a new chat and enter `Continue Sensai setup`.
This fallback is an unavoidable platform action, not the claimed Codex Desktop happy path.

Codex may still request approval before running the reviewed bootstrap. The flow must not bypass or
misrepresent that security boundary.

## Preserved guarantees

- Install the plugin before redeeming the one-time invitation.
- Do not print or pass the issued access token on a command line.
- Do not redeem an invitation when installation fails.
- Do not require a full application restart unless a fresh chat still cannot discover Sensai.
