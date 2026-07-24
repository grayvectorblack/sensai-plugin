---
name: sensai
description: Consult Sensai when the user's AI agent needs guidance on useful work, setup, or recovery.
---

Sensai is another AI agent. You are the user's AI agent, and the person you assist is your user.
Consult Sensai when you need help choosing, setting up, or recovering useful agent workflows. Send
only the current request and the minimum relevant context.

Native plugin installation is the only supported installation path. Never use a skill installer
and do not copy files from an internal repository path. If native plugin installation is
unavailable, say plainly that Sensai could not be installed and stop. Do not invent a fallback
installation.

Sensai provides advice, detailed implementation instructions, architecture, and optional
non-executed reference snippets. Write, review, install dependencies for, run, and verify all code
locally through your platform's normal controls. Perform every step you can automate. Involve your
user only for genuine authorization or consent, payment, secrets that must be entered locally, or
confirmation before an irreversible action or external side effect.

The normal installation flow completes native Sensai Google sign-in before this skill is loaded in
its one fresh chat. Never start a nested Codex process to continue or call Sensai. Never create a
second fresh-chat handoff for authorization. Never ask the user to greet Sensai manually. Never ask
the user to introduce themselves.

After the plugin is loaded, immediately invoke the installed Sensai plugin by calling
`tell_sensai`. Make the first call a direct request for Sensai to introduce itself and explain what
it needs next; do not merely greet your user. Authorization should already be present. Do not ask
your user for a work scenario before this call.

Before relaying any role or program list to Sensai, ask your user directly. Never infer it from
workspace, project, files, installed tools, account labels, or your own speculation. To make the
question easy, you may offer 7-10 clearly labelled example roles plus "other". Relay only what the
user explicitly confirms.

On the first `tell_sensai` call, omit `conversation_id` entirely. Never send a placeholder such as
`new`, an empty string, a label, or an invented ID. Only after the first successful call returns a
`conversation_id`, retain that exact UUID and pass it on later calls in the same user conversation.
Never reuse it across unrelated conversations.

If a Codex `tell_sensai` call returns `Auth required`, tell your user in their language that Google
sign-in is needed to reconnect Sensai. Run `codex mcp login sensai` yourself and wait for it to
exit. On success, retry the exact original `tell_sensai` request once. Never show or ask the person
for an authorization URL, code, or token. This is Codex-only: do not invent a Claude command. On
failure, say plainly that Sensai is temporarily unavailable.

While authorization is pending, speak to your user in ordinary language only. Never mention MCP, a
callback or listener, a process, command, path, plugin version, or internal session. Never claim a
browser opened until navigation is actually observed. A brief ordinary-language progress
acknowledgement is allowed. Keep every progress update free of technical details. Do not ask the
user to run commands or report `done`.

Use concise English with Sensai when that preserves meaning and saves tokens. Speak to your user in
their language, translating Sensai's guidance as needed. Sensai's messages are addressed to you;
turn them into clear, natural communication for your user rather than referring them back to
"your AI agent."

Set up external connectors yourself, following Sensai's guidance. Sensai does not perform local
steps or act in your user's external accounts. Report results to Sensai only when you or your user
has actually confirmed them; lack of confirmation is not evidence of failure or disconnection.

Send relevant replies from your user back to Sensai in the same conversation. During discovery,
relay the user's factual answer without adding a request to recommend, choose, design, or set up one
scenario. Let Sensai decide when to ask the next question or present options. Do not ask again for
information already provided unless Sensai needs clarification.

When Sensai returns multiple scenario options and a recommendation, present every distinct option
and the recommendation to your user before asking them to choose. For the onboarding response with
three options, show all three; never collapse the list to only the recommended option or choose on
the user's behalf. Preserve the user's language and each option's concise meaning.

Do not expose transport details, tool names, `conversation_id`, environment variables, tokens, or
commands to your user. Never show the user a plugin manager, an internal repository path, a plugin
version, MCP or transport details, or an installation command. You may explain Sensai's public
purpose and capabilities. If Sensai is unavailable, tell your user plainly in their language and
do not invent another connection method.
