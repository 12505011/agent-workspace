# Reusable workflows

Document repeatable workflows with prerequisites, commands, verification steps,
and rollback or safety notes.

## Associate a new agent session with a task branch

At the beginning of every new Codex or Claude Code session, ask the user:

> Does this work belong to an `agent-workspace` branch? If yes, which branch?

If the user provides a branch, verify it exists before using it. Read its task
notes and the relevant files in `shared/`. Update only verified context,
technical decisions, validation results, and concise handoff notes. Do not add
raw chat/session transcripts, credentials, private keys, access tokens, or
large data files.

If the user says there is no related branch, do not create or modify a task
branch or task notes. Continue work normally. Do not ask again in that session
unless the user changes to a different task or branch.
