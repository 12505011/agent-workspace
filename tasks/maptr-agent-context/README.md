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

### 2026-08-26: dataset is the trigger — pure-OD control differs by data source

- Built two pure LiDAR-only object-detection configs (no MapTR head, no
  camera, no fuser; `heads=dict(vectormap=None)`, `camera=None`, `fuser=None`)
  to isolate the spconv `N=0` / `c_x`/`c_z` swap from the task heads:
  `configs/maptrv2/westwell/bevfusion_maptr_shared_bev_od_only_lidar_mxg128.py`
  and `..._nuscenes.py`. Both align to the validated BEVFusion 54 m baseline
  (`load_dim` 4, range [-54,-54,-1,54,54,7], voxel 0.075, sparse
  [1440,1440,41], max_voxels [120000,160000], `samples_per_gpu=8`,
  `seed=0`, `cudnn_benchmark=False`, BEVFusion augmentation).
- Result matrix:
  - pure OD + Westwell **mxg128** OD data (`data/nuscenes_od` ->
    `/storage/disks/d0/QP_NuScene/labeled/mxvlkica128/`): **8-GPU ran
    normally**, reached `Epoch[1][50/526]`, no swap, no `N=0`.
  - pure OD + official **nuScenes** data
    (`data/nuscenes/westwell_nusc_x0_54_yneg10_10_map_infos_temporal_*.pkl`,
    `load_dim=5, use_dim=[0,1,2,3]`): **still swaps** — `voxelize_out`
    shows `coor_min=[...,0]`/`coor_max=[39,1439,1439]` on many ranks, i.e.
    the same whole-column `c_x`/`c_z` swap. This run failed downstream in
    `batch_norm` (`Expected more than 1 value per channel`, `torch.Size([1,32])`)
    rather than `N=0`, a different symptom of the same swap.
- This **rules out** two prior hypotheses at once:
  - the MapTR head / camera / fuser layer is NOT the trigger (pure OD still
    swaps on nuScenes);
  - the sm_86-compat-binary-on-sm_89 execution hypothesis is NOT sufficient
    (the same sm_86 binaries do NOT swap on mxg128).
- Remaining suspect is the **data itself**. Top candidate difference: the
  mxg128 bins are 4-column (`load_dim=4`) while nuScenes bins are 5-column
  (`load_dim=5`, ring dropped via `use_dim=[0,1,2,3]`); this changes the
  `LoadPointsFromFile` reshape/memory layout path. Next: verify the actual
  column count of the mxg128 bins and then bisect whether it is the column
  count or the point-cloud value distribution that triggers the swap.
- Note: the "Westwell" data for this control is the mxg128 port dataset under
  `data/nuscenes_od`; its original BEVFusion stable runs (`lidar_0709/0722/
  0724/0815`) used the same source but the `/temp_data` mount referenced by
  those older PKLs is gone; the current `pkl_shared_bev_od_x0_54` PKL uses
  absolute `/storage/disks/d0/QP_NuScene/labeled/mxvlkica128/...` paths.
- Neither paired config applies beam/global point downsampling: both set
  `reduce_beams=32`, while the loader only reduces when that value is `<32`.
  Both do apply the same post-augmentation range filter and the hard
  voxelizer's shared 10-points-per-voxel / max-voxel caps. Differences in
  surviving point count and occupied-voxel distribution therefore remain a
  data-dependent trigger candidate.

### 2026-08-26: point-count controlled follow-up is implemented

- MapTR commit `384f6a3` adds
  `tools/3dod_maptr/collect_lidar_voxel_stats.py`. It builds the configured
  training dataset/pipeline, then reports per-frame post-filter `n_points`,
  xyz range, hard-voxel count, per-voxel occupancy, and max-voxel saturation
  to a JSON file. This establishes the mxg128 median point-count cap without
  modifying either dataset.
- The same commit adds
  `bevfusion_maptr_shared_bev_od_only_lidar_nuscenes_pointcap.py`. It requires
  an explicit `MAPTR_POINT_CAP` and inserts only `PointSample` immediately
  after `PointsRangeFilter` in the official-nuScenes pure-OD training path.
  All geometry, model, batch, augmentation, and voxel parameters inherit from
  the paired parity config.

### 2026-08-26: no-sweeps 8-GPU control still reproduces sparse `N=0`

- The Stage-1 control config was changed at runtime to set
  `LoadPointsFromMultiSweeps.sweeps_num=0` in both train and test pipelines.
  The transform remains visible in a dumped config by design, but with zero
  selections it retains only the keyframe and reads no historical sweep.
- The subsequent 8-GPU smoke still reproduced spconv's `N > 0` / `N=0`
  failure. This rules out historical-sweep concatenation and sweep extrinsic
  transforms as the trigger. This control uses official nuScenes keyframe
  point clouds (the `westwell_nusc` filename is a project naming convention,
  not a Westwell point-cloud source), so a Westwell point-cloud binary/layout
  mismatch is ruled out for this reproduction. The previously observed
  whole-column `c_x`/`c_z` swap occurs after hard voxelization and is not
  explained by a normal malformed input sample.
- The failure remains before either object or MapTR loss/head execution. The
  next isolation should hold the runtime fixed and align the remaining
  BEVFusion input-contract deltas one at a time. Commits `9d7e3ca` and
  `ccea0e4` made the first alignment safely: Stage-1 retains the official
  nuScenes raw record width (`load_dim=5`) but selects four features
  (`use_dim=4`, `x,y,z,intensity`), keeps its no-sweep setting, and explicitly
  overrides the inherited `SparseEncoder.in_channels` from 5 to 4. Using
  `load_dim=4` on native nuScenes `.bin` would mis-reshape its 5-float records
  and is invalid. The range, voxel grid,
  augmentations, and task heads are deliberately unchanged. Run the 8-GPU
  smoke with this commit before changing z range/point range.

### 2026-08-26: CUDA 11.8 runtime dependency validation and MMCV blocker

- On 4090_8, `maptr_new` now has PyTorch 2.0.1 + CUDA 11.8 and rebuilt
  custom extensions, plus `mmcv-full 1.7.2`, `mmdet 2.28.2`, and the required
  offline runtime packages (including OpenCV, SciPy, Matplotlib, PyYAML,
  pycocotools, YAPF, and their direct dependencies). From the MapTR source
  directory, `import torch, mmcv, mmdet, mmdet3d` and
  `from mmdet3d.apis import train_model` succeeded.
- The actual training CLI still fails before parsing arguments with
  `KeyError: 'SparseConv2d is already registered in conv layer'`. The conflict
  is reproducible on the ordinary `maptr_train_torchrun.py --help` import path,
  not merely a synthetic extension-import order. MMCV 1.7.2 already registers
  sparse convolution layers, while the repository's legacy
  `mmdet3d/ops/spconv/conv.py` decorates its own `SparseConv2d` and
  `SparseConv3d` with `@CONV_LAYERS.register_module()`.
- Therefore the CUDA 11.8 8-GPU sparse-voxelization comparison has not run
  yet. Do not interpret this as evidence for or against the old CUDA 11.3
  runtime hypothesis. Resolve the MMCV/custom-spconv registry compatibility
  first, with a focused regression test on the real training import path.

### 2026-08-26: Reference BEVFusion comparison

- `/root/yihan/bevfusion` is trained through the running `bevfusion` Docker
  container, with `/root/yihan/bevfusion -> /bevfusion`. The documented 8-GPU
  entry point is `tools/dist_train.sh <config.yaml> 8`, which uses
  `torch.distributed.launch` and `tools/westwell_train.py` with NCCL.
- Inside that container the runtime is also Python 3.8, PyTorch 1.10.1+cu113,
  MMCV 1.4.0, MMDetection 2.20.0, and RTX 4090 capability `(8,9)`.
  `mmdet3d/ops/voxel/src/voxelization_cuda.cu` and
  `mmdet3d/ops/spconv/{conv.py,ops.py}` have byte-identical source hashes to
  the MapTR branch. This rules out the *base* CUDA 11.3/PyTorch 1.10 stack and
  divergent voxel/spconv source as sufficient explanations for the MapTR-only
  8-GPU failure; historical compiled binary differences remain untested.
- The training inputs are materially different: the BEVFusion Westwell
  LiDAR-only config uses one current sweep, four point features, z range
  `[-1,7]`, and default batch 8 per GPU. MapTR Stage 1 uses current + four
  historical sweeps, five features, z range `[-5,3]`, and batch 1 per GPU.
  Both use xy range `[-54,54]`, 0.075/0.075/0.2 voxel size, sparse shape
  `[1440,1440,41]`, and `max_voxels=[120000,160000]`.
- Next discriminating experiment: keep the MapTR code/runtime fixed and make
  a one-epoch 8-GPU Stage-1 smoke use BEVFusion's LiDAR input contract one
  difference at a time (first remove multi-sweeps, then use four features,
  then align z range). This will determine whether a data-pipeline property
  triggers the coordinate corruption.

### 2026-08-26: PyTorch 2 / CUDA 11.8 custom-op source compatibility

- A clean 4090_8 `maptr_new` Conda environment now reports Python 3.8,
  PyTorch 2.0.1, PyTorch CUDA 11.8, CUDA Toolkit 11.8 (`nvcc 11.8.89`), and
  RTX 4090 capability `(8, 9)`. The former environment was a CUDA 11.3 clone
  and did not test this hypothesis.
- Full custom-op rebuild first stopped at `ball_query.cpp` because PyTorch 2
  removed `<THC/THC.h>` and `THCState`. Source commit `74ff687` (pushed on
  `bev_3dod_maptr_shared_bev_mmdet3d`) ports the six affected PointNet wrapper
  files to `ATen/cuda/CUDAContext.h`, removes unused THC state, modernizes the
  BallQuery CUDA check, and replaces one deprecated `Tensor.data<T>()` call.
  It intentionally does not change any CUDA kernel or Python API.
- Added `tests/test_torch2_cuda_extension_compat.py`; the test was observed
  failing before the port and passing after it. `git diff --check` passed.
- On 4090_8, after pulling `74ff687`, a complete `python setup.py build_ext
  --inplace --force` succeeded in `maptr_new`; it copied the voxel, sparse
  convolution, and all affected PointNet extension `.so` files. Full training
  validation remains pending because the fresh environment has neither MMCV
  nor MMDet installed. Do not claim the CUDA 11.8 hypothesis proven until the
  exact 8-GPU Stage-1 smoke reaches and survives sparse voxelization.

### 2026-08-26: seed hypothesis ruled out on old CUDA 11.3 environment

- Goal: test whether the 8-GPU `N=0` is caused by multi-rank random-state
  divergence. BEVFusion's stable 8-GPU `lidar_0813` run (see below) trains with
  `seed = 0`; the MapTR stage-1 configs never define `seed`, so
  `maptr_train_torchrun.py` falls back to `cfg.setdefault("seed", None)` and
  skips seeding entirely.
- Reproduction baseline: on 4090_8, remote checked out to detached HEAD
  `edb8024` (pre-torch2 code). Old env `maptr` (torch 1.10.1 + cudatoolkit
  11.3 runtime-only, no `bin/nvcc`) recompiled all extensions with system
  `/usr/local/cuda-11.8` nvcc and the setup.py gencode fallback
  `70/75/80/86` (no sm_89) — byte-identical to the original failing build.
  Baseline 8-GPU smoke re-reproduced `N=0` in the first iteration on
  `SparseEncoder.encoder_layer -> spconv get_indice_pairs()`.
- A/B result: `--cfg-options seed=0` entered the config (`'seed': 0`,
  `Set random seed to 0`) yet rank 3 still failed with the identical
  `N > 0 assert failed, N=0`. **Seed / multi-rank random state is therefore
  ruled out as the root cause.**
- The old-env experiment is faithful: the old env never had its own nvcc
  (conda `cudatoolkit-11.3.1` is runtime-only, 88 files, no `bin/nvcc`), so
  the original `.so` were always compiled with the system CUDA 11.8 nvcc but
  hard-coded to gencode `70/75/80/86` (no sm_89). Runtime CUDA 11.3 + compile
  CUDA 11.8 + sm_86-only cubins running on sm_89 remains the sole unruled-out
  hypothesis.

### 2026-08-26: BEVFusion trunk 8-GPU training is genuinely stable

- `/root/yihan/bevfusion` is the CUDA 11.3 BEVFusion deployment/training repo
  (`docker/Dockerfile`: `nvidia/cuda:11.3.1-devel`, `torch==1.10.1`,
  `mmcv-full==1.4.0`, `mmdet==2.20.0`). Its `setup.py` hard-codes the same
  gencode `70/75/80/86` (no sm_89), and it already has compiled `.so`.
- Its operator sources are byte-identical to the MapTR repo for the
  pre-task-head LiDAR path: all 7 spconv sources (`all/indice/reordering/
  maxpool` `.cc`+`.cu`) and all 6 voxel sources (`voxelization`/`scatter_points`
  `.cpp`/`.cu`/`.h`) `diff` empty. The only MapTR deltas in `sparse_encoder.py`
  and `bevfusion.py` are env-gated debug probes; the computation path is
  unchanged. This confirms the failure is not caused by adding the MapTR head.
- Its stable 8-GPU runs live under `/storage/disks/d0/run_dir/lidar_0813/`
  (`20260813_072737.log`, `20260813_162126.log`): two complete 20-epoch runs,
  `epoch_20.pth` saved, validation evaluated, and zero `N=0` / spconv /
  `get_indice_pairs` / CUDA errors in the full logs. `seed = 0`,
  `deterministic = False`, `cudnn_benchmark = False`.
- Notable config difference vs MapTR stage-1: BEVFusion `voxel_size`
  `[0.125,0.125,0.2]` or `[0.1,0.1,0.2]`, `point_cloud_range`
  `[-80,-80,-1,80,80,7]`; MapTR uses `[0.075,0.075,0.2]` and
  `[-54,-54,-5,54,54,3]`. Both use `sparse_shape [1440,1440,41]`. BEVFusion
  launches via `tools/dist_train.sh` (`torch.distributed.launch` + mmcv
  `init_dist`) or torchpack/MPI; MapTR uses `torchrun` +
  `init_process_group` (see `maptr_train_torchrun.py`).

### 2026-08-26: voxelize c_x/c_z swap root-cause isolation

- Source branch: `bev_3dod_maptr_shared_bev_mmdet3d`, commits up to `0830826`.
  The 8-GPU stage-1 smoke still fails in the first iteration with `N=0` in
  spconv `get_indice_pairs()`, while a one-GPU full epoch passes.
- Per-stage sparse probes (`debug_sparse_max_calls`), pipeline probes
  (`DebugPointsRange`), and voxelize in/out probes (`MAPTR_DEBUG_POINTS`) were
  added (all env-gated, default off). They localize the failure to
  `hard_voxelize`: its output coors have `c_x` (col 0) and `c_z` (col 2)
  randomly swapped on some ranks, so the z dimension (extent 41) receives
  x-values up to ~1437 and the first stride sparse conv empties out. `c_y` is
  never affected.
- Exhaustively ruled out, each with a deterministic experiment:
  - data — single-GPU replay of 5 dumped swapped samples: 20/20 stable at
    `c_z_max=39`;
  - build cache — clean `rm -rf build/` rebuild (`.so` 12:25);
  - GPU hardware/concurrency — 8-GPU serial AND concurrent probes stable;
  - augmentation — GlobalRotScaleTrans/RandomFlip3D disabled, still swaps;
  - input format — type/dtype/device/contiguous identical to the stable probe;
  - num_features — `[N,3]` and `[N,5]` both stable;
  - kernel race — `compute-sanitizer --tool racecheck` → 0 hazards;
  - async race — `CUDA_LAUNCH_BLOCKING=1` still swaps;
  - NCCL init and DDP broadcast — probes with `init_process_group` and a
    DDP-wrapped forward all stable;
  - memory source — a `res.clone()` at the voxelize entry (env-gated
    `MAPTR_VOXELIZE_CLONE`) still swaps;
  - decorator chain — `fp16=None` so `@auto_fp16`/`@force_fp32` pass through
    (and float rounding cannot swap integer coors columns).
- Working hypothesis (not proven): a CUDA-driver/hardware-level
  non-determinism specific to this multi-GPU training stack (PyTorch 1.10.1 +
  CUDA 11.3 + custom spconv), rather than a code-logic bug. Every code-layer
  variable above is exhausted, and the whole-column `c_x`/`c_z` swap looks like
  a memory/execution-level effect rather than an algorithmic one. The
  `.clone()` workaround was tested and did not help. Next most likely fixes,
  in order: (1) move to a newer PyTorch/CUDA combo and rebuild the extensions,
  (2) Nsight Compute to diff the kernel across ranks, (3) fall back to
  single-GPU training.
- Diagnostic tools committed (all env-gated, default off):
  `sparse_encoder.py` per-stage probe, `DebugPointsRange`, voxelize in/out
  probe + swap dump, and
  `tools/3dod_maptr/check_voxel_{order,order_real,nccl,replay}.py`.

### 2026-08-26: Shared-BEV stage-1 sparse-coordinate diagnosis

- Source branch: `bev_3dod_maptr_shared_bev_mmdet3d`, commit `e87829d`
  (pushed). A direct comparison against the known-good Westwell BEVFusion
  source showed that prior MapTR-only coordinate-order auto-detection,
  coordinate swapping, zero-voxel insertion, and sparse debug instrumentation
  had diverged from the established LiDAR path.
- `mmdet3d/models/backbones/sparse_encoder.py` now has the same computation
  as BEVFusion: coordinates are passed in the upstream `(batch,z,y,x)`
  contract, sparse shape is `[1440,1440,41]`, and dense conversion produces
  `(B,C*D,H,W)`. `BEVFusion.voxelize()` likewise again directly consumes the
  hard-voxelizer output and pads its batch column, with no coordinate rewrite.
- The shared config removes the added coordinate-order/debug options and uses
  the normal hard-voxelizer default (`deterministic=True`). Python compilation
  and whitespace checks passed locally. The 8-GPU smoke at commit `e87829d`
  still failed on rank 5 during the first training iteration, inside an
  `encoder_layer` call to spconv `get_indice_pairs()` with `N=0`. There was no
  OOM, illegal-memory-access, or primary NCCL error. Raw sweep xyz diagnostics
  occur before `PointsRangeFilter` and therefore do not show that the filtered
  sparse input is invalid. A per-stage active-count probe on the exact failing
  batch is required before another implementation change.
- The rebuilt extension was present on 4090_8 at `2026-08-26 11:15:16`
  (16,601,840 bytes). The subsequent `debug8` run did not exercise it: its
  command-line override reintroduced the removed
  `model.encoders.lidar.backbone.debug_sparse_max_calls=2` option, so all ranks
  stopped during model construction with an unexpected-keyword `TypeError`.
- A corrected rerun later overwrote `debug8/train.log` and did exercise the
  rebuilt extension. It reproduced the same first-iteration failure in
  `SparseEncoder.encoder_layer -> spconv get_indice_pairs()`; rank 1 was the
  first observed failure and rank 3 also emitted `N=0`. Recompiling
  `sparse_conv_ext.so` therefore did not change the symptom and rules out a
  stale binary as the immediate cause.

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

### 2026-08-20: Long-range training crop selection

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `a1012d6` (pushed).
- The 55 m Westwell entry config
  `bevfusion_maptr_camera_only_nuscenes2_long_range.py` now enables
  `enable_front_top_mid_full_fov_stretch=True` for training. The center camera
  is stretched to the common `256x704` input without losing vertical FOV.
- The two side cameras retain the BEVFusion-style isotropic resize/crop path,
  including its padded right-side black region. BEV range, PKLs, decoder
  contract, and all other training settings are unchanged.
- Per user direction, this config was committed and pushed without local
  training or validation; execution is performed on 4090_8.

### 2026-08-20: Long-range 24-epoch schedule

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `c835356` (pushed).
- The 55 m long-range config explicitly overrides the inherited 16-epoch
  schedule with `total_epochs=24` and an `EpochBasedRunner` with
  `max_epochs=24`.
- Its `GridMask.max_epoch` is also set to 24 so the image augmentation
  schedule spans the full training run. No optimizer, LR policy, data PKL,
  model, or decoder setting changed. Per user direction, training is run on
  4090_8 rather than locally.

### 2026-08-20: PV auxiliary-label crop alignment

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `48f89e4` (pushed).
- Training initially failed in `VectorizedLocalMap.gen_vectorized_samples`:
  the Pillow image path supplied `pad_shape=(960, 768)`, while the legacy PV
  mask code expected a list of per-camera shapes and attempted to subscript
  the integer `pad_shape[0]`.
- The PV mask generator now derives camera count and H/W from the final image
  tensor (`N,C,H,W`), matching the actual `256x704` augmented input. It also
  projects to raw pixels, applies `img_aug_matrix` after perspective division,
  then scales by the configured `feat_down_sample=16`; the old fixed `/32`
  raw-projection path was geometrically inconsistent with cropped inputs.
- A regression unittest covers nonzero crop translation. Per user convention,
  code was committed and pushed locally without local execution; validate on
  4090_8 after pull before restarting distributed training.

### 2026-08-20: ImageAug3D final-shape metadata

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `7a94342` (pushed).
- After the PV-label fix allowed the first batch to reach the model, training
  failed in `LSSTransform.create_frustum`: `img_shape` still contained the
  Pillow loader's raw `(960,768)` tuple, while the encoder expected a list of
  per-camera final shapes.
- `ImageAug3D` now preserves raw `ori_shape` but updates `img_shape` and
  `pad_shape` to one `(H,W,C)` entry per augmented view. For the active
  long-range config this is three copies of `(256,704,3)`, yielding the
  expected `/16` LSS feature geometry `16x44`.
- A regression unittest covers the multiview metadata contract. Per user
  convention, validation is performed on 4090_8 after pull.

### 2026-08-20: Depth-frustum input-shape compatibility

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `7477b4b` (pushed).
- `LSSTransform` now accepts both the current flat augmented image metadata
  `(H, W, C)` and legacy per-camera shape lists when creating its frustum.
  It no longer assumes the shape is always nested and therefore no longer
  indexes the height integer as a sequence.
- The active 55 m pipeline contract is input `256x704`, LSS feature stride
  `16`, feature geometry `16x44`, and 118 depth bins for `[1,60)` at 0.5 m.
  A unit test verifies that exact frustum shape.

### 2026-08-20: Raw-camera depth-supervision cache

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `1507c2e` (pushed).
- Historical depth cache `gt_depth_nuscenes2_x0_55_3cam_640x352_uint16mm`
  was for the former fixed 640x352 pipeline and must not be reused with the
  current random 256x704 ImageAug3D pipeline.
- The active 55 m config instead uses
  `depth_cache_nuscenes2_front3_raw_v1/`. `precompute_gt_depth.py` stores
  uint16-millimetre sparse maps in raw 3x768x960 camera coordinates before
  ImageAug3D. Training loads that cache before ImageAug3D; the transform uses
  the same sampled resize/crop/flip/rotation on the image and depth map.
  Training therefore no longer reads PCD or projects LiDAR for depth targets.
- The generated cache can be reused across train/val/test runs that retain
  the same source images, camera selection/order, calibration, and depth
  range. It is intentionally not tied to one random augmentation draw.

### 2026-08-20: Live-depth default and evaluation contract

- Source branch: `bev_3dod_maptr_decoder_opt`, commits `558694c` and
  `45be7c1` (pushed).
- The active 55 m config exposes `use_depth_cache`, currently `False`; this
  uses `LoadPointsFromFile -> ImageAug3D -> CustomPointToMultiViewDepth` for
  per-batch, geometrically aligned live sparse-depth supervision. Set it true
  only after creating the raw-camera cache.
- Validation is explicitly aligned to the same Westwell camera names and
  test pipeline as training/inference. It runs every two epochs.
- Runtime cache generation exposed mixed-camera records in the current PKL:
  at least one frame has only `CAM_FRONT_TOP_MID` and
  `CAM_REAR_TOP_RIGHT`, while the model requires the three front cameras.
  This is independent of depth-supervision mode and must be filtered or
  modelled as a separate layout before a three-front-camera training run can
  complete.

### 2026-08-20: Dataset-level incomplete-camera filter

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `4b16abb` (pushed).
- `CustomNuScenesOfflineLocalMapDataset` now derives required cameras from
  its `FilterCameraViews` transform and filters `data_infos` at construction
  time using the same image-parent-directory naming rule. The filter applies
  uniformly to train, val, test, and raw-depth cache generation and logs its
  retained count. This prevents DataLoader workers from receiving incompatible
  mixed-layout records.

### 2026-08-20: 55 m nuscenes2 split and stop-line audit

- The existing 55 m cache is
  `pkl_nuscenes2_x0_55_yneg10_10_20260807_camera_remap/`, using
  `x=[0,55] m`, `y=[-10,10] m`, 13 run-token roots, and up to 10 sweeps.
  Eleven roots form train (4,212 frames); the two holdout roots
  `67d96d9d7072406981aa694c667c338f` (405 frames) and
  `8cc14b7ef6f742e183d7ee5aa4c551f3` (324 frames) are deliberately identical
  for val and test (729 frames each).
- Existing train/val/test annotations contain divider, boundary, centerline,
  and some ped_crossing instances, but no bar markings or stop_line instances.
  The raw `cnwxijk.json` map has two `stop_line` records per data copy; each
  record is a `line_token`, not a polygon token. The current converter routes
  stop_line through polygon extraction, so adding the seventh class requires a
  converter fix followed by a fresh merged cache and run-token split. Reusing
  the current PKLs would train the new class with zero positives.

### 2026-08-20: Westwell line-token stop-line conversion

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `8f93a42` (pushed).
- `westwell_joint_converter.py` now removes Westwell `line_token` stop-line
  records from the temporary NuScenes alias JSON before NuScenesMap builds its
  polygon shortcuts, restores them after map initialization, and vectorizes
  them as clipped line instances. This fixes the former
  `KeyError: 'polygon_token'` and preserves the stop-line geometry.
- The active 55 m config now has seven classes (adding `stop_line`) and points
  to the separate `pkl_nuscenes2_x0_55_yneg10_10_stopline/` cache, so the old
  six-class PKLs remain untouched.
- Regression tests cover JSON sanitization and line-token-to-vector output.
  A local real-map check loaded `cnwxijk.json` successfully and extracted two
  stop-line `LineString` instances in a containing patch. Config loading
  confirmed `num_map_classes=7`.

### 2026-08-20: Jinke/58 explicit camera-slot remap and stop-line PKL

- Jinke/58 raw NuScenes channels are `CAM_FRONT_TOP_MID`,
  `CAM_FRONT_MID_LEFT`, `CAM_FRONT_MID_RIGHT`, `CAM_REAR_TOP_LEFT`, and
  `CAM_REAR_TOP_RIGHT`. Do **not** rely on filename-substring inference:
  `CAM_FRONT_MID_LEFT` otherwise matches the shorter `CAM_FRONT_MID` alias,
  causing several streams to overwrite one canonical slot.
- The required explicit conversion mapping is:
  `CAM_FRONT_TOP_MID -> CAM_FRONT_MID`,
  `CAM_FRONT_MID_LEFT -> CAM_FRONT_LEFT`,
  `CAM_FRONT_MID_RIGHT -> CAM_FRONT_RIGHT`,
  `CAM_REAR_TOP_LEFT -> CAM_REAR_LEFT`, and
  `CAM_REAR_TOP_RIGHT -> CAM_REAR_RIGHT`.
- On 4090_8, the resulting non-overwriting cache is
  `/storage/disks/d0/lelin/data/jinke/58/pkl_nuscenes2_x0_55_yneg10_10_stopline_3cam/`.
  It has 4,212 train, 729 val, and 729 test frames; every frame contains the
  three required front canonical keys. It contains 684/61/61 stop-line vectors
  in train/val/test respectively, using the established 11-train/2-holdout
  run-token split.
- The cache was generated without changing source code. Selecting it for a
  future experiment is a separate, explicit configuration decision; the
  active 55 m config was intentionally left unchanged after generation.

### 2026-08-21: Raw-camera inference projection fix

- Source branch: `bev_3dod_maptr_decoder_opt`, commit `6b55a5b` (pushed).
- `maptr_visualize.py` previously applied `inverse(img_aug_matrix)` to the
  PKL `lidar2img` matrix for a raw-camera canvas. This is invalid: the PKL
  matrix is already calibrated for raw pixels, while `img_aug_matrix` maps raw
  pixels to the network resize/crop canvas only.
- Raw overlays now use `lidar2img` unchanged. Network-crop overlays retain the
  correct rule: perspective-project with raw calibration, then apply the
  image augmentation in dehomogenized pixel coordinates. A regression test
  verifies that a resize/crop matrix cannot alter the raw projection.

### 2026-08-24: Local MapTR Docker baseline reproduced from 4090_8

- Local verified image: `maptr:4090-cuda113`, image ID
  `sha256:5b18a7fd201cb8a8dd48f6d351b3c7859ef5dc300627e8ea514b98224d55c4c6`.
  It is built from the same 4090_8 base image
  `harbor.wellspiking.ai/model_evalution/bevfusion:dev_jqy_spiking`
  (Ubuntu 20.04, CUDA 11.3.1) and a packed copy of its `maptr` Conda runtime.
- Verified inside the local container with the current MapTR repository bind
  mounted: Python 3.8.20, PyTorch 1.10.1 with CUDA 11.3, MMCV 1.4.0, MMDet
  2.20.0, OpenCV 4.5.5, and `mmdet3d` import. CUDA was available on the local
  RTX 3060; the same image contract applies to the target 4090 hosts.
- Persistent build documentation is kept at `/home/westwell/maptr_docker_4090/`
  (`Dockerfile`, `README.md`, `.dockerignore`). Code and datasets are runtime
  bind mounts under `/workspace/maptr`, `/workspace/data`, and
  `/workspace/work_dirs`; host paths are therefore intentionally not baked
  into the image.
- Intermediate Conda archives, base-image archives, wheel downloads, build
  logs, and 4090 staging paths were moved to trash after validation. The local
  Docker image itself is the retained runnable artifact. If a portable archive
  is needed later, export this verified image with
  `docker image save maptr:4090-cuda113 | zstd -T0 -3 > maptr.tar.zst`.

### 2026-08-25: Shared-BEV LiDAR voxel-coordinate normalization

- Source branch: `bev_3dod_maptr_shared_bev_mmdet3d`, commit `1a6a35d`
  (pushed). The two-stage schedule remains 24 epochs for each stage; Stage 2
  still freezes the Stage-1 LiDAR encoder.
- Stage 1 previously failed in the first stride sparse convolution with
  `N > 0 assert failed ... got N=0`. A controlled 4090_8 probe requested
  distinct `(x,y,z)` voxel bins and verified that the installed voxelizer
  binary returns coordinates in `(z,y,x)` order. The branch's SparseEncoder,
  sparse shape `[1440,1440,41]`, final z-axis convolution, and dense-to-BEV
  conversion instead consistently use `(x,y,z)`.
- The shared-BEV LiDAR config now declares the two coordinate conventions
  explicitly. `BEVFusion.voxelize()` converts `zyx -> xyz` before adding the
  batch index. On the original failing sample, 36,658 input voxels then
  passed through the sparse backbone and produced the expected LiDAR BEV
  shape `(1,256,180,180)`.
- This is a runtime model/config correction only. It does not change the
  point-cloud range, voxel size, dataset split, PKL files, or training heads;
  PKLs do not need regeneration.

### 2026-08-25: Stage-1 shared-BEV DDP graph cleanup

- Source branch: `bev_3dod_maptr_shared_bev_mmdet3d`, commit `f537b60`
  (pushed).
- After voxel-coordinate normalization allowed Stage 1 to advance, DDP
  reported the same ten unused trainable parameters on every rank. They are
  exclusively from the original image-to-BEV MapTR path: learned BEV
  positional encoding, camera/feature-level embeddings, and the CAN-bus MLP.
  The Stage-1 `shared_bev` route decodes the LiDAR BEV directly and therefore
  cannot use these parameters.
- Stage 1 now freezes exactly those ten parameters. The LiDAR encoder, shared
  BEV decoder, object head, MapTR vector decoder, classification/regression
  branches, and BEV segmentation head remain trainable. DDP unused-parameter
  detection remains disabled so future accidental graph omissions still fail
  visibly instead of being masked.
- Commit `0196256` adds `RUN_STAGE2=0` to the restartable training script, so
  Stage 1 can train/recover for 24 epochs and stop before Stage 2.

### 2026-08-25: Stage-1 one-GPU full-epoch validation

- On 4090_8, commit `0196256` completed one full Stage-1 epoch on GPU 0:
  28,130 / 28,130 iterations, with `RUN_STAGE2=0`. The run used
  `work_dirs/shared_bev/nuscenes_two_stage/stage1_smoke_1gpu_1e_20260825`.
- Verified artifact: `epoch_1.pth` exists and is 157,447,339 bytes. The
  launcher logged both successful checkpoint save and the expected
  `Stage 1 completed; RUN_STAGE2=0, stopping before Stage 2` exit.
- Peak reported memory was 17,257 MiB. No `spconv N=0`, illegal CUDA memory
  access, or DDP unused-parameter failure appeared during the complete epoch.
  This validates the coordinate-order and Stage-1 graph fixes for one GPU;
  multi-GPU stability still requires a separate smoke test before a 24-epoch
  eight-GPU run.

### 2026-08-26: Eight-GPU direct smoke remains blocked before DDP reduction

- Direct 8-GPU Stage-1 smoke at commit `0196256` also failed after forcing
  NCCL to use socket transport (`NCCL_P2P_DISABLE=1`, `NCCL_SHM_DISABLE=1`,
  `NCCL_IB_DISABLE=1`). All eight ranks logged `NCCL ... Init COMPLETE` and
  entered parameter broadcast successfully.
- The first application failure is independent of NCCL: the sparse backbone
  fails in `spconv/ops.py:get_indice_pairs()` from
  `SparseEncoder.forward()` with `N > 0 assert failed ... got N=0`. Subsequent
  socket-connection and NCCL errors occur only after ranks terminate and are
  therefore secondary effects.
- This rules out NCCL transport as the immediate cause but does not yet prove
  why an intermediate sparse tensor becomes empty only under concurrent
  multi-GPU execution. Next investigation must log per-rank voxel count and
  coordinate range at every sparse-encoder stage, then compare against the
  completed one-GPU run; do not change sparse shapes or add dummy voxels first.

### 2026-08-26: Bounded per-rank sparse diagnostics added

- Source branch commit `27ff941` (pushed) adds
  `debug_sparse_max_calls` to `SparseEncoder`; it defaults to `0` and has no
  computation-path effect. For the configured number of calls, each rank logs
  active voxel count, sparse shape, and coordinate min/max at input, after
  `conv_input`, before/after each encoder stage, and around `conv_out`.
- The shared-BEV base config exposes the option at
  `model.encoders.lidar.backbone.debug_sparse_max_calls`. Set it to a small
  value (for example `2`) via `--cfg-options` for a short multi-GPU repro.

### 2026-08-26: Corrected shared-BEV voxelizer coordinate contract

- A direct controlled probe of the installed 4090 voxelizer on both GPU 0 and
  GPU 1 returned coordinates in `(x,y,z)` order. This supersedes the earlier
  `zyx` assumption.
- The prior shared-BEV config performed an incorrect `zyx -> xyz` swap on
  already-`xyz` coordinates. During two-GPU diagnostics, the failing rank
  consequently carried values up to 1429 in the third sparse dimension whose
  configured extent is only 41, then hit `spconv N=0`.
- Source commit `a160171` (pushed) changes the shared-BEV contract to
  `voxel_coordinate_order='xyz'` and
  `sparse_coordinate_order='xyz'`, eliminating the swap. The earlier single
  GPU Stage-1 smoke only showed non-crashing execution; it must not be used as
  a geometrically valid checkpoint because it used the incorrect contract.

### 2026-08-26: Temporal-sweep source diagnostics

- Training-mode `LoadPointsFromMultiSweeps` uses `np.random.choice()` whenever
  more historical sweeps are available than requested. A one-GPU full epoch
  and a DDP epoch can therefore use different sweep combinations for the same
  keyframe; this explains why the one-GPU run cannot fully clear PKL sweep
  metadata.
- Source commit `175e7cd` (pushed) adds the opt-in environment switch
  `MAPTR_DEBUG_SWEEPS=1`. It logs rank, keyframe path, selected sweep index and
  path, plus the transformed xyz range. Use it only for a short failing repro
  to determine whether an invalid raw file or a bad sweep transform is the
  source of the out-of-range z values.
