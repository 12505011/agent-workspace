# agent-workspace

Private, versioned shared workspace for Codex and Claude Code.

It stores durable task context, verified technical decisions, reusable workflows,
and handoff notes. It deliberately does not store raw conversation transcripts,
credentials, tokens, private keys, or large data files.

## Workflow

1. Keep reusable cross-project information in `shared/`.
2. Start each task from `main` using `task/<short-name>`.
3. Keep task-specific notes in `tasks/<short-name>/`.
4. Record verified conclusions, commands, and handoff notes before merging.
5. Review `git diff` before every commit.

## Branches

- `main`: stable shared knowledge, templates, and completed-task summaries.
- `task/<short-name>`: one active task and its working notes.

## Agent entry points

When this repository is attached to a project, both Codex and Claude Code should
be directed to the relevant task directory and `shared/` before work begins.
