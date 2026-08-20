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

### 2026-08-20: Decoder-opt image augmentation alignment

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `8562680` (pushed to
  `origin/bev_3dod_maptr_decoder_opt`). Only this active branch was changed.
- The active Westwell base, CNWXIJK, 30 m, and 55 m decoder-opt configs now
  use the BEVFusion image contract: Pillow/RGB loading, `ImageAug3D` to
  `256x704`, train resize `[0.38, 0.55]`, test resize `0.48`, train rotation
  `[-5.4, 5.4]`, optional horizontal flip, and ImageNet normalization.
- `LoadMultiViewImageFromFiles` gained an opt-in `backend="pillow"` path;
  the legacy default remains the existing mmcv/NumPy path.
- Fixed `640x352` sparse-depth caches are incompatible with the new geometric
  image augmentation. The 30 m and 55 m configs therefore create `gt_depth`
  by current-keyframe LiDAR projection after `ImageAug3D`; this remains a
  training target only, not a model input. The historical checkpoint-compat
  config was deliberately left unchanged.
- Per user direction, no training/config validation was run after this edit;
  only `git diff --check` was completed before commit.

### 2026-08-20: Per-camera full-FOV switch

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `2923b0b` (pushed).
- `ImageAug3D` accepts optional `camera_aug_overrides`. Its opt-in
  `resize_mode="stretch"` resizes a named camera directly to the shared final
  dimensions with independent x/y scales and records those scales in
  `img_aug_matrix`; raw intrinsic and extrinsic calibration remains unchanged.
- The 30 m and 55 m Westwell configs expose
  `enable_front_top_mid_full_fov_stretch` (default `False`). Set it to `True`
  for the `CAM_FRONT_TOP_MID` layout to preserve its full raw vertical FOV;
  left/right cameras retain the BEVFusion augmentation path. Full-FOV mode
  deliberately disables rotation and flip for that camera, since either would
  discard image edges.
- Python syntax checks and `git diff --check` passed; no training was run.

### 2026-08-20: Cropped-camera GT projection visualizer

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `7e683a0` (pushed).
- Added `tools/3dod_maptr/visualize_maptr_cropped_camera_gt.py`. It reads a
  config plus infos PKL, applies that config's test-time `ImageAug3D` to the
  three original camera images, and draws the PKL map GT after composing the
  raw `lidar2img` projection with the resulting `img_aug_matrix`.
- Output is one cropped `256x704` image per configured camera and one
  three-camera strip. It supports
  `--enable-front-top-mid-full-fov-stretch` to preview the center-camera
  option without editing a config.
- `conda run -n maptr ... --help`, Python compilation, and `git diff --check`
  passed. No real dataset render was run in this workspace.

### 2026-08-20: nuscenes2 cropped-camera render verification

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `83e37f6` (pushed).
- nuscenes2 PKLs use standard calibration record keys while preserving source
  camera layout names in each image path. For Jinke/58 sample index 0:
  `CAM_FRONT_TOP_MID <- CAM_FRONT_MID`,
  `CAM_FRONT_MID_LEFT <- CAM_FRONT_LEFT`, and
  `CAM_FRONT_MID_RIGHT <- CAM_FRONT_RIGHT`. The cropped-camera visualizer now
  resolves this mapping from image-directory names, matching
  `FilterCameraViews`.
- On 4090_8, the 55 m validation PKL index 0 rendered successfully with
  `--enable-front-top-mid-full-fov-stretch`. It produced three per-camera
  images and one `256x704`-per-view strip beneath
  `work_dirs/cropped_camera_gt/58_val_000000_stretch/` in the remote MapTR
  workspace. The script logged its composed geometry contract:
  raw `lidar2img -> img_aug_matrix -> cropped pixels`.

### 2026-08-20: Cropped-overlay source-FOV correction

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `703fecc` (pushed).
- The cropped-camera GT visualizer now rejects a sampled map point that is
  outside the original camera image before applying its image augmentation.
  This prevents off-image geometry from being drawn after a resize/crop maps
  its mathematical projection into the output canvas.
- The change is limited to the offline inspection renderer; it does not alter
  PKLs, camera calibration, image augmentation, or the model training path.
- Python compilation and whitespace validation passed. A remote re-render is
  still required after the user pulls commit `703fecc`.

### 2026-08-20: Perspective-correct cropped projection

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `c9938b7` (pushed).
- Root cause: the visualization code treated `img_aug_matrix` as directly
  composable with a 4x4 LiDAR-to-image projection. Its crop translation is a
  pixel-space offset and must be applied after dividing projected coordinates
  by depth. Direct composition incorrectly divides that translation by depth.
- This explains the asymmetric symptom: the center full-FOV stretch has no
  crop translation and appeared correct; the standard left/right views use
  `v' = 0.48v - 112` and were displaced.
- The renderer now projects to raw pixels, applies the 2D image affine to
  dehomogenized pixels, and clips against the raw source FOV. A unittest was
  added for the nonzero-depth pixel-translation case. Per user instruction,
  no local validation was run.
- 2026-08-20: User validated commit `c9938b7` on 4090_8 and confirmed the
  repaired cropped-camera projection is correct. This projection rule must be
  retained by future camera-overlay tools: apply resize/crop/flip/rotation in
  dehomogenized pixel space, never by directly left-multiplying a 4x4 camera
  projection matrix with a pixel-space translation transform.
