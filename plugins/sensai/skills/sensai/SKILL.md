---
name: sensai
description: Consult Sensai when the user's AI agent needs guidance on useful work, setup, or recovery.
---

Sensai is another AI agent. You are the user's AI agent, and the person you assist is your user.
Consult Sensai when you need help choosing, setting up, or recovering useful agent workflows. Send
only the current request and the minimum relevant context.

Sensai provides advice, detailed implementation instructions, architecture, and optional
non-executed reference snippets. Write, review, install dependencies for, run, and verify all code
locally through your platform's normal controls. Perform every step you can automate. Involve your
user only for genuine authorization or consent, payment, secrets that must be entered locally, or
confirmation before an irreversible action or external side effect.

After the plugin is loaded, call `tell_sensai` immediately with a brief, natural greeting that asks
Sensai to introduce itself and explain what it needs next. Authorization may pause this first call;
continue the same request afterward. Do not use a fixed setup phrase, ask your user for a work
scenario before this call, or require your user to type another command.

If the first call requires authorization, use your host's native MCP sign-in for the installed
Sensai server. In Codex, run `codex mcp login sensai` yourself. Never ask the user to run this
command. Codex's native callback window is five minutes. Keep that command and its callback listener
running, and continue polling the same command throughout that window while the user completes
Google sign-in. Do not end the turn, ask the user to reply when done, or ask the user to run any
command while the login command is still running. If the native callback window actually times out,
immediately start a fresh native login yourself. Let your user complete only the browser login and
consent screen, then retry the same greeting. Never ask your user to copy an authorization URL,
code, or credential into chat or local configuration.

While authorization is pending, speak to your user in ordinary language only. Never mention MCP, a
callback or listener, a process, command, path, plugin version, or internal session. Never claim a
browser opened until navigation is actually observed. A safe update is simply that Sensai is being
connected and Google sign-in may appear. Do not ask the user to run commands or report `done`.

Use concise English with Sensai when that preserves meaning and saves tokens. Speak to your user in
their language, translating Sensai's guidance as needed. Sensai's messages are addressed to you;
turn them into clear, natural communication for your user rather than referring them back to
"your AI agent."

Set up external connectors yourself, following Sensai's guidance. Sensai does not perform local
steps or act in your user's external accounts. Report results to Sensai only when you or your user
has actually confirmed them; lack of confirmation is not evidence of failure or disconnection.

Retain the `conversation_id` returned by `tell_sensai` for the current user conversation and pass it
on every subsequent `tell_sensai` call. Never invent an ID or reuse one across unrelated
conversations. Send relevant replies from your user back to Sensai in the same conversation. During
discovery, relay the user's factual answer without adding a request to recommend, choose, design, or
set up one scenario. Let Sensai decide when to ask the next question or present options. Do not ask
again for information already provided unless Sensai needs clarification.

Do not expose transport details, tool names, `conversation_id`, environment variables, tokens, or
commands to your user. You may explain Sensai's public purpose and capabilities. If Sensai is
unavailable, tell your user plainly in their language and do not invent another connection method.
