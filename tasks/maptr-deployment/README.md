# Task: MapTR deployment

## Goal

Inspect and document the MapTR deployment implementation under:

`/data/baize/baize-welldriver/src/perception_q/src/dl_runtime/dl_bevfusion_maptr`

## Scope

- Establish the runtime entry points, model/profile configuration contract, and
  TensorRT engine/plugin requirements.
- Record only verified findings from source, build files, runtime profiles, and
  reproducible checks.
- Do not modify deployment code or runtime profiles unless separately requested.

## Relevant workspaces

| Item | Location |
| --- | --- |
| MapTR source and tools | `/data/baize/baize-welldriver/code/maptr` |
| Perception runtime integration | `/data/baize/baize-welldriver/src/perception_q/src/dl_runtime/dl_bevfusion_maptr` |

## Initial checklist

- [x] Locate build targets and runtime initialization entry points.
- [x] Identify profile fields that select MapTR engines and camera count.
- [x] Identify required TensorRT plans and plugin loading behavior.
- [x] Trace input preprocessing and output/publication path.
- [x] Record deployment risks and verification commands.

## Handoff notes

- 2026-08-13: Task branch created and source inspection completed. Verified
  findings are in `deployment-inspection.md`; no perception runtime code or
  profile was changed.
