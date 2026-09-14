# Task: Shared-BEV OD + Map multitask deployment

## Goal

Deploy the trained Shared-BEV multitask model as one runtime model with one
shared feature path and two task outputs: 3D object detection and vector map.

Deployment implementation belongs in the `perception_q` branch
`release-test-mapod-share-model-5.7`. The existing agent-workspace task
`task/maptr-deployment` and the `perception_q` branch
`release-test-maptralone-5.6` are reference material only; do not implement the
new task on those branches.

## Repositories and fixed paths

| Item | Path / branch | Role |
| --- | --- | --- |
| Training/export repository | `/data/baize/baize-welldriver/code/maptr` | Source checkpoint, executable config, ONNX export and validation |
| Training code branch | `bev_3dod_maptr_shared_bev_mmdet3d` | Shared-BEV OD + Map PyTorch implementation |
| Runtime repository | `/data/baize/baize-welldriver/src/perception_q` | Deployment implementation |
| Runtime target branch | `release-test-mapod-share-model-5.7` | Only branch to receive this task's runtime code |
| Runtime reference branch | `release-test-maptralone-5.6` | Read-only implementation reference |
| OD runtime reference | `src/dl_runtime/dl_bevfusion` | LiDAR/camera BEV, fusion, OD head and postprocess reference |
| Map runtime reference | `src/dl_runtime/dl_bevfusion_maptr` | Camera preprocessing, Map decoder/plugin and output reference |
| Runtime profile | `/data/baize/baize-welldriver/src/profile_project/project/cnwxijk/qthd/perception_q/79-perception.yaml` | Deployment configuration contract |

The user referred to the Map reference as `dl_maptr`; the verified directory
name on `release-test-maptralone-5.6` is `dl_bevfusion_maptr`.

## Selected model inputs

Local model directory:

`/data/baize/baize-welldriver/code/maptr/work_dirs/shared_bev/westwell/mxg128_reference_one_stage/one_stage_exp_g_decoder_gn_od5cam_map3cam_od16_map1_group_lr_w1_0p12_0p04_24e_bs4_w4`

| Artifact | Size | MD5 | Status |
| --- | ---: | --- | --- |
| `epoch_12.pth` | 503,454,341 bytes | `c5d0f80ca8228f91ee754813cc058237` | Copied from 4090 and verified |
| `bevfusion_maptr_shared_bev_mxg128_reference_one_stage_exp_g_decoder_gn_24e.py` | 153,233 bytes | `ac747192ade3d96cb591413542f32ed4` | Copied and verified; MMCV work-dir dump, not the export config |

The executable source config to use for export is:

`configs/maptrv2/westwell/bevfusion_maptr_shared_bev_mxg128_reference_one_stage_exp_g_decoder_gn_24e.py`

The selected checkpoint is a one-stage Shared-BEV OD + Map model. Its verified
training contract includes OD:Map update frequency 16:1, OD 5 cameras, Map 3
cameras, seven map classes including `stop_line`, and GroupNorm in the shared
decoder SECOND/SECONDFPN blocks. Export and runtime must verify the actual
checkpoint/config shapes instead of copying geometry from an older engine.

## Current status

- [x] Checkpoint and config snapshot copied locally and MD5 verified.
- [x] Target and reference runtime branches verified.
- [x] Existing `task/maptr-deployment` notes inspected as deployment reference.
- [x] Existing Shared-BEV ONNX exporter entry points located.
- [x] Export the selected checkpoint to six ONNX graphs and record their
  interfaces/hashes in `export_manifest.json`.
- [ ] Validate ONNX outputs against PyTorch on fixed samples.
- [x] Build an FP16 TensorRT smoke-test bundle on the local RTX3060 with
  TensorRT 8.5.2.2/CUDA 11.4.
- [ ] Rebuild the validated ONNX graphs in the final target GPU/TensorRT
  environment.
- [ ] Validate TensorRT outputs against ONNX/PyTorch.
- [x] Implement the shared runtime and both postprocessing/output paths as the
  independent `dl_bevfusion_mapod` module on
  `release-test-mapod-share-model-5.7`.
- [x] Add a non-default `dl_bevfusion_mapod` profile and pipeline to
  `79-perception.yaml`; YAML structure and fixed model dimensions validated.
- [ ] Build, replay, and verify both OD and Map outputs together.

## Verified export contract (2026-09-10)

Export directory (generated artifact, not tracked in Git):

`work_dirs/onnx_engines/shared_bev_multitask_decoder_gn_epoch12_4cam/onnx`

The model uses a shared decoded BEV tensor shaped `[1, 512, 180, 180]`. The OD
head consumes that tensor directly. The Map head crops it to
`[1, 512, 34, 90]`, applies its learned 512-to-256 projection and returns
classification `[4, 1, 40, 7]`, bbox `[4, 1, 40, 4]`, and point
`[4, 1, 40, 15, 2]` outputs. The OD head outputs tensors shaped
`[1, 180, 180, 200]`, `[1, 180, 180, 140]`, and `[1, 180, 180, 40]`.

Six exported graphs and their MD5 values:

| Graph | MD5 | Interface summary |
| --- | --- | --- |
| `camera.backbone.onnx` | `9fad262c47d56248f3aa37b036ebed4e` | image/depth for four cameras to image/depth features |
| `camera.vtransform.onnx` | `f8c040594e5a3487d724481913e8f87c` | `[1,80,360,360]` to `[1,80,180,180]` |
| `lidar.backbone.xyz.onnx` | `787d9b91ac50447adadc7fd571c165ca` | custom sparse graph to `[1,256,180,180]` |
| `fuser.onnx` | `f0cdd3b6842142f1d241684781d95a5a` | camera 80ch + LiDAR 256ch to shared 512ch BEV |
| `anchorhead.bbox.onnx` | `45d47e21a922bf6058db32122de02c7c` | shared BEV to three OD outputs |
| `maptr_decoder_head.onnx` | `3b7fcd4f9b5d117ebf27357d61d72a89` | shared BEV to three Map outputs |

`inspect_shared_bev_onnx.py` passed every declared input/output name and static
shape. Stock ONNX checker passed all standard graphs and the Map graph. The
LiDAR graph intentionally uses the existing custom sparse operators in the
default ONNX domain and therefore requires the runtime sparse parser rather
than stock ONNX Runtime/checker.

The directory name says `od5cam`, but both the executable config and saved
training config prove that each task actually saw three cameras:

- OD: `CAM_FRONT_MID`, `CAM_FRONT_MID_LEFT`, `CAM_FRONT_MID_RIGHT`
- Map: `CAM_FRONT_TOP_MID`, `CAM_FRONT_MID_LEFT`, `CAM_FRONT_MID_RIGHT`

Their union is four physical cameras. The first unified export therefore uses
four cameras as an explicit deployment candidate. This is not yet considered
final: replay must compare the unified four-camera route with task-specific
three-camera behavior before the profile contract is frozen.

## Local TensorRT smoke-test result (2026-09-10)

Build directory:

`work_dirs/onnx_engines/shared_bev_multitask_decoder_gn_epoch12_4cam/build_rtx3060_cuda114_trt8522_fp16`

The dedicated `build_shared_bev_multitask_engine.sh` produced and executed all
five FP16 plans on the local RTX3060:

| Plan | MD5 | Smoke inference |
| --- | --- | --- |
| `camera.backbone.plan` | `ffcdd87de69bfc812422970931b17c8b` | Passed |
| `camera.vtransform.plan` | `ca9a2effd39d1b163a156a85c54e5c69` | Passed |
| `fuser.plan` | `7160c600192e9ba3b668a78ba2798b41` | Passed |
| `anchorhead.bbox.plan` | `d9a2269df51073858d668df96708e3e0` | Passed |
| `maptr_decoder_head.plan` | `954a677a890e9447843670b58b24b4ab` | Passed with `libmaptr_plugins.so` loaded |

The sparse LiDAR ONNX remains a runtime-parsed component and is bundled beside
the plans. Local build dependencies were TensorRT 8.5.2.2, CUDA 11.4 and cuDNN
8.2.4. TensorRT logged that it was linked against cuDNN 8.6.0 but both engine
build and smoke execution passed. These RTX3060 plans are validation artifacts,
not portable Orin deliverables.

## Epoch-16 deployment candidate (2026-09-13)

The Map-best epoch-16 checkpoint was re-synced from 4090_8 because the file at
the original local work-dir path was truncated: it was only 129,499,136 bytes
and `torch.load` failed with `failed finding central directory`. The damaged
file was preserved. The verified server copy is stored independently at:

`work_dirs/checkpoints/shared_bev_multitask_decoder_gn_epoch16_20260913/best_map_NuscMap_chamfer_mAP_epoch_16.pth`

It is 503,454,405 bytes with MD5
`6a06245320f1f92a6f643db280222eea`; checkpoint metadata reports epoch 16 and
iteration 98,400. Tensor shapes confirm four Map decoder layers, 40 instance
queries, 15 points per vector, and a 34x90 Map positional grid.

The current nuScenes branch resolves the same Westwell source config to six
decoder layers, so it is not valid for this historical checkpoint. Export was
therefore isolated at training/deployment commit `f72fb84`, whose executable
config resolves to the saved training contract: four decoder layers, Map/OD
three-camera routes with a four-physical-camera union, 0.6 m Map voxel size,
40 vectors and 15 points. No current nuScenes source changes were modified.

Epoch-16 ONNX directory:

`work_dirs/onnx_engines/shared_bev_multitask_decoder_gn_epoch16_4cam/onnx`

| Graph | MD5 | Bytes |
| --- | --- | ---: |
| `camera.backbone.onnx` | `608dcc5b03f29970b6860b8d70ce2475` | 108,342,888 |
| `camera.vtransform.onnx` | `67b1dfb24c76e51e0edd31081cfa8263` | 692,848 |
| `lidar.backbone.xyz.onnx` | `24a55406000f7fafa497b9e18bbd1656` | 5,393,868 |
| `fuser.onnx` | `dfdd480f89f372642adc3cea988454fb` | 21,419,101 |
| `anchorhead.bbox.onnx` | `5a89363f5c7426ff527e824f300c25cf` | 780,815 |
| `maptr_decoder_head.onnx` | `3eb79508183eff8a17276859820e9b53` | 23,414,819 |

All standard graphs passed ONNX checker; the sparse LiDAR graph retains the
intentional runtime custom parser contract. Map-head export matched the patched
PyTorch forward exactly for classification and bbox outputs, with maximum point
error `4.547e-11`. The Map outputs remain `[4,1,40,7]`, `[4,1,40,4]`, and
`[4,1,40,15,2]`.

RTX3060 FP16 bundle:

`work_dirs/onnx_engines/shared_bev_multitask_decoder_gn_epoch16_4cam/build_rtx3060_cuda114_trt8522_fp16`

| Runtime artifact | MD5 |
| --- | --- |
| `camera.backbone.plan` | `155f7ff2ebe9f0b58488e43120ac3346` |
| `camera.vtransform.plan` | `21f79aaa585684c24e98cfd85790dfdb` |
| `fuser.plan` | `11a6421191e259b8183c925403d753e3` |
| `anchorhead.bbox.plan` | `4736e6e87fca208b37710f9ad8776ae4` |
| `maptr_decoder_head.plan` | `bdc99687e379a0a689d2fa78be5d8c4c` |
| `lidar.backbone.xyz.onnx` | `24a55406000f7fafa497b9e18bbd1656` |
| `libmaptr_plugins.so` | `7849f28546bf6a8f633e96e652a4e4cb` |

All five dense engines built and completed one TensorRT smoke inference in the
fixed local RTX3060 container (TensorRT 8.5.2.2/CUDA 11.4). Bundle files were
returned to `westwell:westwell`. This validates export/build/load mechanics,
not numerical parity on recorded data; these plans must not be copied to Orin
or another TensorRT/GPU target as final engines.

## Deployment plan

### 1. Freeze and inspect the model contract

1. Load the executable source config and `epoch_12.pth` together.
2. Record the exact camera inputs and order for each task, image preprocessing,
   depth bins, point-cloud range, voxel/BEV dimensions, feature channels,
   decoder layers, OD classes/anchors/NMS, and Map classes/query/point limits.
3. Confirm how the training model shares camera/LiDAR/BEV features and where it
   branches into the OD and Map heads.
4. Decide the ONNX graph boundaries from that real forward path. Preserve one
   shared computation path; do not accidentally deploy two independent models.

### 2. Export ONNX first

Start from the existing Shared-BEV exporters under
`deployment/export/shared_bev/`:

- `export_bev_encoder_onnx.py`
- `export_fuser_decoder_obj_onnx.py`
- `export_maptr_head_onnx.py`

Also inspect the existing camera and LiDAR exporters before deciding whether
they can be reused unchanged. The current scripts are candidate tooling, not a
validated export of this checkpoint.

For every exported graph:

1. Save input/output names, dtypes and static shapes in a manifest.
2. Run ONNX checker and shape inspection.
3. Compare ONNX Runtime/plugin-capable execution with PyTorch on fixed samples.
4. Compare intermediate shared BEV tensors as well as final OD and Map outputs.
5. Reject an export if it silently drops the decoder GroupNorm behavior,
   `stop_line`, task-specific camera routing, or either task head.

### 3. Convert validated ONNX to TensorRT engines

1. Confirm the target GPU, CUDA and TensorRT versions before building; TensorRT
   plans are target-environment specific even though ONNX is portable.
2. Build required custom plugins before parsing graphs that contain
   `mmdeploy::bev_pool` or `mmdeploy::ms_deform_attn`.
3. Build FP16 engines first. Treat INT8 as a later, independently calibrated
   optimization rather than part of the initial correctness path.
4. Capture engine binding names/shapes and build logs in a machine-readable
   manifest.
5. Compare engine outputs against ONNX/PyTorch with numerical tolerances and
   then compare decoded OD boxes and Map vectors.

### 4. Integrate into `perception_q` 5.7

1. Implement the deployment as the independent module
   `src/dl_runtime/dl_bevfusion_mapod`; do not add the Map head inside the
   existing `dl_bevfusion` module and do not call the standalone
   `dl_bevfusion_maptr` module.
2. Use the 5.6 `dl_bevfusion` and `dl_bevfusion_maptr` implementations only as
   read-only references. The new module owns its runtime namespace, TensorRT
   wrapper, camera/LiDAR/fusion path, both heads, algorithm class and output.
3. Initialize plugins before deserializing dependent engines.
4. Run camera/LiDAR preprocessing and shared BEV computation once, then route
   the shared result to both task heads.
5. Preserve OD postprocessing and publish Map raw vector instances with label,
   score, frame-local `instance_id`, and ordered `point_index`; keep dense Map
   visualization optional and separate from algorithm output.
6. Add explicit initialization failures for missing engines/plugins and binding
   or geometry mismatches.

### 5. Profile and end-to-end validation

Update `79-perception.yaml` only after the engine manifest is fixed. The profile
must match engine camera order/count, preprocessing, depth bins, BEV geometry,
class counts and thresholds exactly.

Acceptance checks:

- runtime initializes every engine and required plugin without fallback;
- one input trigger produces both OD and Map outputs from the same frame;
- camera ordering/calibration and LiDAR timestamp/frame id are correct;
- no binding, geometry, CUDA, TensorRT, queue-overrun or memory errors;
- replay outputs are numerically/semantically consistent with offline inference;
- latency and GPU-memory measurements are captured with both heads enabled.

## Reusable reference from `task/maptr-deployment`

- TensorRT plugins must be loaded with global symbol visibility before parsing
  dependent decoder engines.
- Engine geometry, preprocessing and camera order are strict runtime contracts,
  not adjustable presentation settings.
- TensorRT plans cannot be copied across incompatible GPU/CUDA/TensorRT targets.
- Raw Map output should retain original ordered decoder points and instance
  membership; visualization resampling belongs on an optional topic.
- The older 5.6 profile values describe a standalone three-camera MapTR model
  and must not be copied blindly into the new shared multitask profile.

## Safety and handoff rules

- Do not modify `release-test-maptralone-5.6`; it is reference-only.
- Preserve unrelated local changes in all repositories.
- Do not commit checkpoints, ONNX files, TensorRT plans, raw logs, recordings,
  credentials or other large/private artifacts to `agent-workspace`.
- Record hashes, contracts, commands and concise validation results here as each
  milestone is completed.

## Runtime replay findings and export corrections (2026-09-14)

Recorded-data initialization established the following MapOD input contract:

- `dl_bevfusion_mapod` reads only its own profile section and is independent
  from the legacy `dl_bevfusion` camera remap;
- the four physical cameras are raw IDs `0, 1, 6, 7`, mapped to MapOD union
  slots `3, 1, 2, 0` respectively;
- OD uses union slots `[0, 1, 2]`, while Map uses `[3, 1, 2]`;
- Player supplies undistorted `1400x1000` images; MapOD crops ROI
  `(220,116,960,768)`, then preprocesses the `960x768` images to the network
  input size `704x256`.

The runtime still contains an older calibration conversion which reports and
computes `1920x1536 -> 960x540`: it halves `fx/fy/cx` and applies
`cy = cy / 2 - 110`. This disagrees with the current `960x768` preprocessor
input and remains an open projection-correctness issue. It did not cause the
initialization aborts described below.

### Initialization failures resolved or isolated

1. Two stale playback `loader_exe` processes were found consuming about
   2.63 GiB of GPU memory each. After they were stopped, the earlier
   `fuser.plan` deserialization failure no longer reproduced. Always verify
   that only one playback loader is active before attributing initialization
   failures to an engine.
2. The sparse LiDAR parser unconditionally accessed `node.input(2)` as bias.
   The epoch-16 ONNX contains bias-free sparse convolutions with only
   `[feature, weight]`, causing a protobuf bounds abort in
   `get_initializer_data`. The independent MapOD parser now supplies an
   explicit FP16 zero bias of shape `[out_channels]`; the legacy
   `dl_bevfusion` parser was not changed.
3. After the bias fix, initialization advanced to
   `spconv::EngineBuilderImpl::build` and aborted. Inspection proved the
   deployed epoch-16 LiDAR ONNX was topologically disconnected: examples were
   `conv0: 0 -> 1`, followed by `relu0: 2 -> 2`. The custom exporter did not
   serialize BatchNorm, and its inplace-ReLU hook overwrote the input tensor
   graph ID.
4. The export command initially ran on the nuScenes branch, where the shared
   config resolves to six Map decoder layers. The historical Westwell
   checkpoint contains four layers, so strict checkpoint loading correctly
   rejected it. Do not use non-strict loading to hide this mismatch.

### Code corrections

Training/export repository, branch `bev_3dod_maptr_shared_bev_mmdet3d`:

- `deployment/scripts/3dod_maptr/export_scn.py` now folds LiDAR BatchNorm into
  sparse convolutions and fuses the following ReLU before custom ONNX tracing;
- `deployment/export/lean/exptool.py` preserves the incoming graph ID before
  registering an inplace ReLU output;
- `deployment/scripts/3dod_maptr/inspect_shared_bev_onnx.py` now validates
  sparse-graph topological connectivity instead of skipping all structural
  validation for custom operators.

Runtime repository, branch `release-test-mapod-share-model-5.7`:

- the independent MapOD sparse parser accepts bias-free SparseConvolution
  nodes by creating zero bias;
- missing SparseConvolution/ReLU upstream tensors now produce an explicit
  parser error and return failure instead of reaching spconv with a null
  tensor.

The training/export repository was switched back from
`bev_3dod_maptr_shared_bev_nuscenes` to
`bev_3dod_maptr_shared_bev_mmdet3d`. Uncommitted nuScenes work was preserved in
the named stash `wip: preserve nuscenes changes before returning to westwell`.
The Westwell source config resolves to four decoder layers and matches the
epoch-16 checkpoint.

### Superseded artifact and next handoff

The epoch-16 `lidar.backbone.xyz.onnx` with MD5
`24a55406000f7fafa497b9e18bbd1656` is invalid for runtime use despite its
previous interface-only inspection. It must be replaced and its manifest/hash
updated after re-export. Existing dense TensorRT plans are not evidence that
the runtime-parsed sparse ONNX is valid.

Next steps:

1. Re-export only `lidar.backbone.xyz.onnx` from the four-layer Westwell config
   and epoch-16 checkpoint using the corrected `export_scn.py`.
2. Confirm the sparse graph has no unavailable node inputs and record the new
   MD5.
3. Replace the bad sparse ONNX in the container, rebuild/install the updated
   independent MapOD runtime, and replay with exactly one loader process.
4. Once initialization and both outputs work, correct the remaining
   `960x540` calibration conversion against the verified `960x768` input and
   validate projection behavior.

## Successful MapOD playback milestone (2026-09-14)

The corrected four-layer Westwell epoch-16 bundle now initializes and runs in
recorded-data playback. This closes the engine-loading and sparse-LiDAR graph
blockers above. The replacement `lidar.backbone.xyz.onnx` has MD5
`05598ea2927401765e294aff95bb4dcd`; the superseded invalid artifact must not be
restored.

Changes were committed and pushed independently so ownership remains clear:

- MapTR/export branch `bev_3dod_maptr_shared_bev_mmdet3d`, commit `5c87b52`:
  folds sparse-backbone BN/ReLU before export, preserves inplace-ReLU graph
  input IDs, and validates sparse ONNX topology;
- perception_q branch `release-test-mapod-share-model-5.7`, commit `1f941844`:
  fixes independent MapOD initialization and sparse parsing, adds the Player
  crop/input diagnostics, preserves the existing OD output path, and publishes
  Map vectors on `maptr_pointcloud`;
- profile_project branch `release-test-mapod-share-model-5.7`, commit
  `a06088b9f`: enables the independent MapOD pipeline, adds the private
  four-camera remap and the `1400x1000 -> 960x768 -> 704x256` input contract.
  The legacy `dl_bevfusion` and `dl_bevfusion_maptr` configuration blocks and
  pipeline remain present and independent.

OD and Map confidence filtering are independently configurable in the MapOD
profile:

- `dl_bevfusion_mapod.params.postprocess.score_thresh` controls OD anchor-box
  decoding and is currently `0.3`;
- `dl_bevfusion_mapod.params.map_score_threshold` controls MapTR vector
  decoding and is currently `0.4`.

Changing one does not change the other. OD also passes through the existing
downstream object filters, so class-specific `score_threshes` later in the
pipeline may further remove OD results; those filters do not affect MapTR.

Remaining acceptance work is output-quality validation rather than startup:
resolve the legacy calibration conversion that still reports
`1920x1536 -> 960x540`, verify projection against the actual `960x768` crop,
then compare OD boxes and Map vectors numerically with offline inference.

## Runtime implementation status (2026-09-11)

The runtime target branch now contains the independent module
`dl_bevfusion_mapod`. Its core loads the six exported model components from a
single MapOD model directory, loads `libmaptr_plugins.so` before deserializing
the Map engine, runs the four-camera backbone once, then gathers and pools the
task-specific three-camera routes before applying the shared fuser/decoder
weights. It publishes the original ordered Map decoder points through
`maptr_pointcloud` while preserving the existing OD object path.

The existing `src/dl_runtime/dl_bevfusion` and all of its files remain
unchanged. To avoid header and dynamic-symbol collisions when both old and new
libraries are linked into `lidar_obj_det`, the new copy uses the dedicated
namespaces `bevfusion_mapod`, `mapod_nv`, `mapod_nvtype`, and
`MapODTensorRT`, plus MapOD-specific header guards/macros.

The follow-up fixes align runtime preprocessing, image augmentation matrices,
OD anchors/decoding, class-wise multiclass NMS, engine binding validation and
failure propagation with the selected training contract. OD sorting uses a
persistent CUB workspace rather than allocating temporary storage per frame.
The engine build script now verifies source provenance before reusing a plan.

Code/build checks completed before the user requested no further testing:

- `git diff --check` passes in the runtime and profile repositories;
- the Map head and complete MapOD core pass `g++ -std=c++17 -Wall -Werror
  -fsyntax-only` against CUDA/TensorRT headers;
- a translation unit including both old and new `bevfusion.hpp` headers passes
  with `-Werror`, confirming the public core headers do not collide;
- `79-perception.yaml` parses successfully and validates four cameras, seven
  Map classes and twenty OD anchors for ten OD classes.

- container build of `bevfusion_mapod_core` and the final `lidar_obj_det`
  target completed successfully.

At that earlier milestone, data replay and numerical output validation were
deferred. Recorded-data startup was subsequently validated in the successful
playback milestone above; numerical parity remains open.

## Review correction (2026-09-11)

The follow-up [code review](REVIEW_2026-09-11.md) found an upper-level
compilation failure, mismatched image/projection transforms and OD anchors,
unsafe OD output allocation/counting, and different NMS semantics. Those code
findings were resolved in runtime commit `0d7a31041`, profile commit
`8c3b21a5d`, and export/build commit `f72fb84`. This is implementation
completion, not deployment acceptance: numerical parity and replay remain
explicitly deferred.
