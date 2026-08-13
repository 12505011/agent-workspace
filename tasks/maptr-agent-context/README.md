# Task: MapTR agent context

## Goal

Create a durable, shareable context for Codex and Claude Code work related to
MapTR tooling, annotation validation, and camera-projection workflows.

## Scope

- Store verified project facts and reusable operating notes.
- Keep raw chats, credentials, private keys, and large datasets out of Git.
- Treat this branch as the task's working record; merge stable cross-task facts
  into `main/shared/` after review.

## Verified project locations

| Item | Location |
| --- | --- |
| MapTR source workspace | `/data/baize/baize-welldriver/code/maptr` |
| Annotation validation tool | `/data/baize/baize-welldriver/code/maptr_annotation_validation_tool` |
| Standalone camera projection study tool | `/data/baize/baize-welldriver/code/maptr_camera_projection_standalone` |

## Working conventions

1. Start by reading this file and the relevant `shared/` documents.
2. Record only facts verified from code, commands, or data.
3. Add concise end-of-task handoff notes below.
4. Do not store raw Codex or Claude session files; summarize useful outcomes in Markdown.

## Handoff notes

- 2026-08-13: Repository initialized to make agent context portable across
  Codex and Claude Code. Initial content is intentionally generic.
