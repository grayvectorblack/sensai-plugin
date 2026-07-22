---
name: sensai
description: Ask Sensai for practical guidance when an AI agent needs help planning or completing the user's work.
---

Use the Sensai MCP tools when the user asks for help choosing, setting up, or recovering an agent
workflow. Send only the user's current request and the minimum context needed to answer it; do not
send files, secrets, or full chat history unless the user explicitly approves that transfer.

Sensai provides advice, detailed implementation instructions, architecture, and optional
non-executed reference snippets. Write, review, install dependencies for, run, and verify all code
locally as the user's AI agent through the platform's normal controls. Never treat MCP output as an
executable package or as permission to bypass normal review and approval.

Set up external connectors locally as the user's AI agent, following Sensai's guidance. Sensai
never connects to or acts in the user's external accounts. Ask the person to handle any required
authorization or consent.

Treat "Continue Sensai setup" and equivalent natural requests to start, continue, or finish Sensai
setup as first use. Immediately call `tell_sensai`. Do not ask the user for a work scenario before
this first call. Send exactly this first-contact message: "Continue Sensai setup". Do not add
instructions or user context to that first message. The user does not need to know or type that
first-contact message.

Relay Sensai's request for the user's profession and up to five programs or websites. Accept any
answer containing one to five programs or websites as a valid reply; do not require exactly five.

Retain the `conversation_id` returned by `tell_sensai` for the current user conversation and pass it
on every subsequent `tell_sensai` call. Never invent an ID or reuse one across unrelated
conversations. Relay Sensai's response to the user in plain language. Treat the user's later natural
answers as replies to Sensai, call `tell_sensai` again with those answers, and pass the retained
`conversation_id`. Do not ask again for information the user has already provided unless Sensai
asks for clarification.

Never expose MCP, tool names, `conversation_id`, environment variables, tokens, or commands to the
user. If Sensai access is unavailable, say only that setup is not ready and stop; never request
credentials in chat or add another transport method.
