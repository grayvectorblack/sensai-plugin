---
name: sensai
description: Ask Sensai for practical guidance when an AI agent needs help planning or completing the user's work.
---

Use the Sensai MCP tools when the user asks for help choosing, setting up, or recovering an
agent workflow. Explain what will be sent before the first request. Send only the user's current
request and the minimum context needed to answer it; do not send files, secrets, or full chat
history unless the user explicitly approves that specific transfer.

Before the first call, the MCP connection needs the user's private Sensai invitation key in the
`SENSAI_INVITE_TOKEN` environment variable. Ask the user for that key only when it is absent; do
not put it in messages, source files, Git, or tool arguments.
