# Stage1 fusion OD-only epoch11: local deployment visual check

## User-confirmed result (2026-10-12)

The user inspected the deployed stage1 OD visualization and confirmed:
**OD visualization is normal; no phantom/unsupported detections were observed.**
This is qualitative acceptance of the inspected local playback, not a full
validation-set false-positive measurement. It does not establish acceptance
of a stage2 joint OD+MAP checkpoint or identify the cause of earlier joint
model false positives.

## Exact model identity and two-stage distinction

- Stage1 training job: `job-2a59bcfa9516ae5143160742`; 16 epochs,
  selected best **epoch11**; training validation mAP63.4181%, NDS67.3224%.
- Stage1 is **three-camera + LiDAR fusion, OD-only supervision**, not
  LiDAR-only. The camera/LiDAR encoders, fuser, BEV decoder and OD head train;
  no MAP head or MAP supervision is present.
- The earlier pure-LiDAR epoch8 initializes only the stage1 LiDAR backbone;
  it is not the checkpoint selected for this deployment.
- Stage2 starts from the complete stage1 fusion OD epoch11 weights, adds a
  newly initialized MAP head, and jointly trains OD+MAP. Its results must be
  evaluated separately from this accepted stage1 visualization.
- Selected checkpoint SHA256:
  `e05bf1e9b9271b066c3ef634405046d6fd484523e62c506e55f4a6d7227a5f85`.
- Local checkpoint/config directory:
  `/data/baize/baize-welldriver/code/maptr/work_dirs/checkpoints/qth_od_stage1_epoch11_20261012/`.
  Files: `epoch_11.pth`, `qth_od_stage1_actual.py`, provenance manifests.

## Deployment identity and checks

- Runtime and profile repositories both use the local branch
  `release-test-mapod-share-model-5.8-1012-odonly`.
- Container: `baize-welldriver-wviz-1`, local RTX3060, CUDA11.4/TRT8.5.2.2.
- Bundle:
  `/debug/code/maptr/work_dirs/onnx_engines/qth_od_stage1_epoch11_20261012/build_rtx3060_cuda114_trt8522_mixed`.
- Three physical cameras raw0/1/6: TOP_MID/MID_LEFT/MID_RIGHT, private slots0/1/2.
  Input256x704; voxel[.075,.075,.2]; Anchor3D11classes/22anchors.
- `enable_maptr:false`; no MAP plan/plugin loaded; LiDAR-only fallback disabled.
- Four dense TensorRT engines deserialize, execute and pass fixed-input
  PyTorch numerical comparison. Camera/vtransform/OD are FP16-enabled;
  fuser computes FP32/noTF32; external bindings are FP16.
- Anchor XY decode is aligned to this checkpoint's x-major training grid:
  height=row=x, width=column=y. Native anchor/formula max XYdifference4.58e-6m.
- Source checks:12passed. C++ compilation/playback performed by the user,
  not the agent. No commit/push of deployment changes was performed.

## Playback evidence and recorded-output contamination warning

Inspected local log:
`/data/baize/baize-welldriver/runqfile/baize_player/log.log`.
At `2026-10-12T10:40:22Z` the runtime logs the above bundle,
`enable_maptr=0`, empty MAP head/plugin paths. All110 observed
`MAPOD_OUTPUT` frames have `map_instances=0`, with nonempty OD detections.

The user also saw lane lines. The same log proves the player starts a recorded
`src_maptr_pointcloud` qfile pipeline. `qbaize_play.yaml` has `all_publish=true`
and, at inspection, did not blacklist `maptr_pointcloud` or recorded
`qpilot/perception/obstacles`. Therefore those lane lines are recorded output,
not this OD-only checkpoint's prediction. Recorded OD output may also mix
with new predictions. Blacklist both topics in the player for an isolated
model-only comparison. This was recommended, but application and a new clean
replay were not verified when this note was recorded.

Preserve the user's positive visual observation, but do not call the original
run an isolated quantitative deployment accuracy benchmark.

## Next experiment decision (2026-10-12)

Stage2 `job-c10c5a340dbc16f0d816d15a` was stopped at the user's request;
CLI final status verified **CANCELED**. No outputs deleted or replacement job submitted.

Next requested strategy: load the accepted stage1 fusion OD epoch11, freeze
camera/LiDAR encoders, fuser, OD BEV decoder and OD head (including normalization
running statistics), train only the new MAP branch, and reduce main queries70→50.
The CY MAP neck is part of the new trainable MAP branch, not frozen stage1.

Old Orin-tested epoch11 MAP reads decoded middle512; current CY MAP reads
pre-decoder fused256 and adds a dilated MAP neck. Old has40main/0auxiliary
queries; current has70main/300one-to-many auxiliary queries with k6. Both have
6decoder layers,20points,7MAPclasses,34x90MAPfeature grid, ROI x[0,54]/y[-10,10],
image256x704,3cameras and LiDARvoxel[.075,.075,.2]. Old ODhas10classes;
current has11 includingQtractor and changed RTGC/QCanchor widths. Old PV
supervision is stride16, current stride8; old depthloss scale.04, current0.
Reducing main queries does not remove300training auxiliary queries. Auxiliary
queries are retained for this experiment; the user selected16GPUs and MAP-only
training. Existing16epoch length and MAP LR1e-4 are retained explicitly.

## Frozen MAP50 stage2 submission

- Old joint8GPU job `job-c10c5a340dbc16f0d816d15a` remains CANCELED;
  no artifacts deleted.
- New `job-5a6a8495ac4370ff9c4c4669`:2workers×8GPU, ray-ddp/ray_train,
  normal/retry0, same MapTR digest3ea27c82... and complete parent OD epoch11.
- Input locked QTH release: MAP2916train/729val; OD2106validation only.
  No OD training loader, noCBGS, noaccumulation;16epochs×183MAPsteps.
- Camera/LiDAR/fuser/ODdecoder/ODhead fully frozen including running buffers
  and eval mode; only newCYMAPneck/head train. Main50/aux300/k6,6layers/20points.
- Three new policy/freeze tests and six existing stage2 tests passed. Actual
  CPU model validated581parent state keys;9,608,318trainable MAP parameters.
  Per-epoch frozen-state audit and complete transfer hook enabled in runtime.
- Source snapshot SHA256 `f8c78828dea2c8de817b8a8e33fbe1ade253620b1548b746cae5f6f82135964e`.
- Output `/mnt/storage/me/runs/work_dirs/job-5a6a8495ac4370ff9c4c4669/qth_od11_frozen_map50_16e_16gpu_20261012/`.
- At19:40CST submission status PROVISIONING, no business steps observed yet;
  submission success is not GPU training/validation acceptance. NoGitpush.
