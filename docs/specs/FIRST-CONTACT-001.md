# FIRST-CONTACT-001: One-request Sensai installation

## User journey

The supported journey starts with exactly one natural request:

> Open https://github.com/grayvectorblack/sensai-plugin, follow its installation instructions without technical details, complete Google sign-in, and continue automatically; only after sign-in, if a new chat is required, give me exactly this copyable sentence: Continue with Sensai and contact Sensai automatically.

The request first directs the installing agent to the transparent public README instead of choosing
an installer in advance. In the same sentence, it requires the agent to keep installation mechanics
private, complete Google sign-in, and continue automatically. Only after confirmed sign-in may it
offer the single fresh-chat continuation. The agent then detects Codex versus Claude Code and
completes these steps in strict order: native plugin installation, native Google sign-in in the
installer chat, exactly one fresh task, session, or reload boundary, and the first `tell_sensai`
call.

A brief ordinary-language acknowledgement is allowed while installation is in progress. It must
not expose commands, paths, versions, a plugin manager, MCP, transport, or other installation
mechanics.

## Deterministic native installation

The installing agent runs the exact command pair for its current host. It does not infer support
from a UI, prose, or memory.

Codex:

```bash
codex plugin marketplace add grayvectorblack/sensai-plugin
codex plugin add sensai@sensai
```

Claude Code:

```bash
claude plugin marketplace add grayvectorblack/sensai-plugin
claude plugin install sensai@sensai --scope user
```

A skill installer and manual file copying are forbidden. The agent may report that native
installation is unsupported only after an applicable installation command actually returns a
nonzero result. Commands, command results, marketplace mechanics, and plugin mechanics remain
private from the person.

## Platform boundary

Codex loads a newly installed plugin in a fresh task. Before creating or offering that task, the
installing agent completes Sensai's native Google sign-in while the installer chat is still active.
It keeps the real login operation alive, lets the person handle only Google's browser consent, and
waits for success. A timeout is real only when the host's login operation reports it.

After sign-in succeeds, Codex creates exactly one fresh task. Claude Code reloads plugins once in
the current session, or starts exactly one new session when reload is unavailable; it never does
both. Only when the platform requires the person to start that fresh context does the agent provide
the exact safe continuation sentence from the original request and no other setup request. The
loaded context starts with authorization already present and greets Sensai immediately. A second
nested Codex launch is forbidden. A second fresh-context handoff is forbidden in the normal path.
The continuation must never be emitted before Google sign-in has confirmed success. The agent never
asks the person to introduce themselves or greet Sensai manually.

The platforms may still require the person to approve plugin installation and, once server OAuth is
available, authorize Sensai in a browser. Those are platform security boundaries, not additional
Sensai setup commands.

The user's agent performs every other automatable step. It may communicate with Sensai in concise
English, while communicating with the person in the person's language. Sensai addresses the user's
agent, not the person directly.

## Authorization boundary

The plugin contains no credential. Its MCP client contacts the configured HTTPS endpoint and uses
the server's standard OAuth metadata. The installing agent starts its host's native MCP sign-in
after native plugin installation and before the fresh chat. Run `codex mcp login sensai` as one
long-running terminal operation. When the terminal tool yields a running session or handle,
preserve it and poll that same handle every 5-10 seconds until the command actually exits or reports
its native five-minute timeout. An empty poll or a poll with no new output still means the operation
is running; it is not completion. Never launch another login, close the process, end the turn, or
return a final response while that session is alive. Only a real process exit decides whether login
succeeded or reached its native timeout. Keep this entire terminal-wait mechanism private from the
person. If that window actually expires, the agent starts a fresh native login itself instead of
asking the person to run a command. The person completes only the browser login and consent.

If credentials are unexpectedly absent in the fresh chat, the loaded Sensai skill retains the same
native sign-in recovery. Recovery retries the greeting in the current chat and never starts a
nested agent or requests another fresh-chat handoff. If OAuth remains unavailable, first contact
fails clearly instead of requesting a copied credential.
