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
- Experiment branch: `bev_3dod_maptr_shared_bev` at commit `8d65bd8`.
  The initial shared-trunk implementation is `d14f81b`; Westwell dataset,
  decoder-opt, and BEVFusion image-pipeline alignment is `8d65bd8`.
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
- The Westwell entry point is
  `projects/configs/maptrv2/westwell/bevfusion_maptr_shared_bev_nuscenes2_long_range.py`.
  It uses source camera names `CAM_FRONT_TOP_MID`, `CAM_FRONT_MID_LEFT`, and
  `CAM_FRONT_MID_RIGHT`, the decoder-opt 55 m PKLs, six map classes, and the
  Westwell BEVFusion object classes/name mapping.
- The decoder-opt branch has no MapTR decoder source-code delta from the
  shared ancestor. Its relevant contract is configuration-level: 40 vectors,
  15 points per vector, four decoder layers, no one-to-many queries, and a
  `17x46` long-range BEV. The shared-BEV config now uses the same contract.
- Camera-bearing shared-BEV configs now use the Westwell BEVFusion 2D image
  pipeline: Pillow/RGB loading, `ImageAug3D` to `256x704`, train resize
  `[0.38,0.55]`, test resize `0.48`, train rotation `[-5.4,5.4]`, optional
  horizontal flip, and ImageNet normalization. The former fixed MapTR
  resize/pad path is removed from these configs.
- For the multi-task trunk, image feature extraction is already common to
  both baselines (`ResNet-50 + GeneralizedLSSFPN`). The shared model follows
  BEVFusion after that point: `DepthLSSTransform`, LiDAR `SparseEncoder`,
  `ConvFuser`, then one `SECOND + SECONDFPN` BEV trunk. Detection consumes the
  full 512-channel BEV; MapTR crops the forward region and uses a lightweight
  512-to-256 adapter plus only its vector decoder. It does not retain MapTR's
  private LSS encoder.
- Validation passed for Python compilation, all config loads, architecture
  contracts, tensor crop shape/axis order, and full model construction after
  temporarily disabling ResNet pretrained loading. A normal local build and
  one-batch training test remain blocked by missing local dependencies,
  including `ckpts/resnet50-19c8e357.pth`, training PKLs, and the stage-1
  checkpoint.
