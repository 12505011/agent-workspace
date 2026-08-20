# Task: MapTR agent context

## Goal

Create a durable, shareable context for Codex and Claude Code work related to
MapTR models, training, tooling, annotation validation, and camera-projection
workflows.

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

### 2026-08-20: Shared-BEV model experiment

- Source branch: `bev_3dod_maptr_multiscale_bev` at commit `a070a83`.
- Experiment branch: `bev_3dod_maptr_shared_bev` at commit `d14f81b`
  (`feat(maptr): share one BEV trunk across tasks`).
- The source branch is genuinely multi-scale in BEV space, not image space:
  `DualScaleDepthLSSTransform` runs one DepthNet/context pass and two BEV
  pooling operations. Its object grid covers `[-54, 54]^2` at 0.6 m, while
  its MapTR grid covers `x=[-15, 15], y=[-10, 30]` at 0.3 m.
- The experiment branch uses `DepthLSSTransform` and one fused, decoded BEV.
  The object head consumes the full tensor; MapTR crops its local region from
  the same tensor. A `180x180` `[X,Y]` BEV yields a native 0.6 m `67x50`
  `[Y,X]` MapTR crop with 512 channels. The private MapTR LSS encoder is
  disabled, so there is no second BEV pooling or resize to `133x100`.
- Joint shared-BEV configs disable 3D rotation, scale, translation, and flips
  because current vector-map ground truth remains in the unaugmented LiDAR
  frame. The LiDAR-only stage-1 config retains its original augmentation.
- Shared-BEV configs live under
  `projects/configs/maptrv2/bevfusion_maptr_shared_bev_*.py`; outputs use
  `work_dirs/shared_bev/` to avoid collisions with multi-scale experiments.
- Validation passed for Python compilation, all config loads, architecture
  contracts, tensor crop shape/axis order, and full model construction after
  temporarily disabling ResNet pretrained loading. A normal local build and
  one-batch training test remain blocked by missing local dependencies,
  including `ckpts/resnet50-19c8e357.pth`, training PKLs, and the stage-1
  checkpoint.
