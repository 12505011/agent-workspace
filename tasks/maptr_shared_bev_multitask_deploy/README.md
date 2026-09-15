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

### Orin98 engine bundle (2026-09-14)

The complete epoch-16 ONNX set was re-exported after the sparse graph fix and
passed the shared contract checker. Commit `764c893` makes sparse-output
validation depend on the single output shape `[1,256,180,180]` instead of the
exporter's internal tensor ID, which legitimately changed from `45` to `40`
after BN/ReLU fusion.

All ONNX files and `export_manifest.json` were copied to
`nvidia@192.168.103.98` under:

`/data/code/all_ws/ws/ruicao/baize_ruicao/code/maptr/work_dirs/onnx_engines/shared_bev_multitask_decoder_gn_epoch16_4cam/onnx`

Source and destination MD5 values matched for all seven files. The MapTR
plugin was compiled natively inside `baize_ruicao-wviz-1` and verified as an
ARM aarch64 shared object. Five FP16 dense engines were then built with
TensorRT 8.5.2/CUDA 11.4 and every engine passed a `trtexec --loadEngine`
smoke test. The deployable bundle is:

`/data/code/all_ws/ws/ruicao/baize_ruicao/code/maptr/work_dirs/onnx_engines/shared_bev_multitask_decoder_gn_epoch16_4cam/build_orin_cuda114_trt8522_fp16`

Bundle checksums are recorded in its `engine_checksums.md5`. It contains
`camera.backbone.plan`, `camera.vtransform.plan`, `fuser.plan`,
`anchorhead.bbox.plan`, `maptr_decoder_head.plan`, the corrected sparse
`lidar.backbone.xyz.onnx`, the aarch64 `libmaptr_plugins.so`, and the export
manifest.

The first transfer exposed a full `/data` partition. Only the recoverable
package cache files directly inside `/data/tmp/apt/archives` were removed;
project, recording and model data were not touched. Do not deploy the bundle
into the active resource directory until its exact Orin profile/install target
is confirmed.

The Orin runtime target was subsequently confirmed and the nine-file bundle
(the five plans, sparse LiDAR ONNX, aarch64 plugin, manifest and checksum file)
was installed inside `baize_ruicao-wviz-1` at
`/opt/qomolo/qpilot-resource/perception/model/dl_bevfusion_mapod`. The target
directory did not previously exist, so no older bundle was overwritten. A
post-copy `md5sum -c engine_checksums.md5` passed for every runtime artifact.

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

## Orin latency diagnosis and final architecture direction (2026-09-15)

### What the deployed epoch-16 model actually computes

The historical checkpoint was trained with two different three-camera routes:

- OD route: union camera slots `[0, 1, 2]`;
- Map route: union camera slots `[3, 1, 2]`.

The runtime already shares LiDAR staging/SCN and the four-camera camera
backbone, but accurate inference must gather/pool the two camera subsets and
run VTransform plus the shared fuser/BEV encoder twice. Merely sharing weights
does not make the two route tensors interchangeable.

Runtime/profile commits `a5800ae0` and `c15d7b581` added a default-off
`benchmark_single_bev` mode and stage timing. In this mode the Map head is fed
the OD-route BEV, so it removes the second gather/BEVPool/VTransform/fuser pass
and measures the desired deployment topology. It is timing-only: Map accuracy
and output correctness are invalid for this historical checkpoint.

The benchmark does not modify the playback launcher and does not require
rebuilding the engines. The startup log must show all of the following before
the result is interpreted as a single-BEV measurement:

- `mode=single_bev`;
- `configured_fusion_passes=1`;
- `union_cameras=4`.

### Verified timing evidence

On Orin, after excluding the first 30 frames, 69 single-BEV core records and
68 complete-process records gave:

| Measurement | Minimum | Median | Mean | P95 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Core wall time | 93.2 ms | 143.0 ms | 147.1 ms | 196.5 ms | 221.6 ms |
| Complete MapOD processing | 105.8 ms | 172.0 ms | 174.7 ms | 218.8 ms | 264.8 ms |

Representative frame 97 used one fusion pass and reported 129.9 ms core and
145.2 ms complete processing. Its principal stream intervals were 54.3 ms
LiDAR voxelization/SCN, 16.2 ms camera backbone, 21.1 ms combined
gather/BEVPool/VTransform/fuser, 2.7 ms OD head, 9.8 ms OD postprocess and
20.9 ms Map head.

For the same steady-state window, selected single-BEV stage distributions
were:

| Stage | Median | Mean | P95 | Observed range |
| --- | ---: | ---: | ---: | ---: |
| LiDAR voxelization/SCN | 51.5 ms | 55.0 ms | 84.4 ms | 39.8-117.1 ms |
| Camera backbone | 15.3 ms | 17.2 ms | 27.4 ms | 14.4-38.2 ms |
| OD fuser/BEV encoder | 17.6 ms | 19.4 ms | 31.1 ms | 17.5-42.4 ms |
| OD postprocess | 10.0 ms | 12.4 ms | 31.4 ms | 5.1-41.0 ms |
| Map head | 24.1 ms | 27.8 ms | 66.0 ms | 6.5-88.9 ms |

A clean dual-route frame showed about 21.8 ms of intrinsic extra Map-route
gather/BEVPool/VTransform/fuser work. Therefore the second route is real but
cannot explain the full 120-240 ms range. Long host submission intervals,
high CPU load and corresponding CUDA-stream idle intervals account for much
of the remaining tail. Image undistortion was disabled during the comparison,
so it is not the root cause of this latency distribution. GPU/CPU temperature
and the configured MAXN mode did not show thermal throttling; the available
evidence does not prove GPU compute contention.

Do not use `stdbuf ... | tee full.log | grep ...` for final timing. It forces
line-buffered production and writes the entire high-volume playback log before
filtering, which can perturb CPU scheduling and I/O. Filter timing tags first,
then tee only the filtered lines. The playback script itself must remain
unchanged.

`map_instances=0` was still observed. The measured Map decode/output cost is
therefore not yet a valid loaded-output latency, and the result is not an
end-to-end acceptance measurement.

### Selected optimal architecture

The user confirmed that the next model can use the same four physical cameras
for both OD and Map. The preferred solution is therefore to train a new model
from scratch with a genuinely shared inference path rather than force the
historical checkpoint into a topology it was not trained on:

1. Use the same four cameras in the same order for both tasks, with one shared
   preprocessing, calibration and image-augmentation contract.
2. Run the four-camera backbone once and construct one camera BEV/LSS output.
3. Run LiDAR SCN once and fuse the camera/LiDAR BEVs once.
4. Run the shared BEV encoder once, then branch only into the existing OD and
   Map heads.
5. Train and evaluate this exact topology; the deployment must not introduce
   task-specific camera routes that were absent during training.
6. Export one camera backbone, one VTransform, one fuser/BEV encoder and the
   two heads. Runtime `single_bev` then becomes the normal accuracy-valid path,
   not a benchmark override.

OD and Map annotations may remain in separate datasets. They do not need to
exist on the same frame to train this topology, but both dataloaders must emit
the identical four-camera input contract. Alternate or accumulate task batches
while passing both through the same trunk. Define the schedule by actual
per-task forward/backward/update counts rather than the ambiguous outer
"epoch": give Map at least the same number of supervised updates as its
Map-only 24-epoch baseline, prevent the much larger OD dataset from dominating
the shared trunk, and report raw OD loss, raw Map-head loss, depth loss and the
weighted optimization total separately. Start with equal normalized OD/Map
gradient contribution at each joint optimizer cycle; tune task weights only
after the shared-camera baseline is measured.

Normalization should be changed selectively. Keep a pretrained camera
backbone's frozen/stable BN where its statistics are not being updated, and use
GN in the task-sensitive shared BEV decoder/SECOND/SECONDFPN blocks where the
separate OD and Map data distributions previously corrupted shared BN
statistics. Converting every BN layer to GN is not the default plan.

This removes approximately 22 ms of duplicate route work while preserving a
meaningful accuracy contract. It does not by itself guarantee the historical
60-80 ms latency: the measured lower bound is currently about 93 ms core and
the steady-state median is about 143 ms. After correctness is established,
optimization priority is:

1. overlap LiDAR SCN and the camera branch on separate CUDA streams;
2. reduce SCN execution and long-tail variance;
3. investigate Map-head enqueue/stream stalls (normal engine work can be near
   6-7 ms, far below the observed P95);
4. reduce OD CPU NMS and pointcloud/polygon association synchronization;
5. consider asynchronous or lower-rate Map publication only as a product-level
   fallback, not as a substitute for the correct shared model.

### Acceptance gates for the retrained model

- Four-camera identities, ordering, `1400x1000 -> 960x768 -> 704x256`
  preprocessing and calibration matrices match training exactly.
- PyTorch, ONNX and Orin TensorRT shared-BEV and both-head outputs pass
  numerical comparison on fixed recorded frames.
- OD output remains compatible with the existing object pipeline and Map
  publishes nonzero, geometrically correct `maptr_pointcloud` instances.
- Latency is measured without verbose full-log capture, after warmup, with at
  least P50/P95/core/complete-process statistics.
- Accuracy and latency are both measured with the same production topology;
  timing-only `benchmark_single_bev` results are never reported as model
  accuracy.

### Confirmed runtime parallelism gaps and optimization order

Code inspection confirmed that the legacy `dl_bevfusion` does not overlap its
LiDAR and camera branches. It passes one CUDA stream through point staging,
LiDAR voxelization/SCN, image normalization, depth projection, camera backbone,
BEVPool, VTransform, fuser, head and postprocess in that order. Voxelization
also calls `cudaStreamSynchronize` to read the dynamic voxel count. The
`release-test-maptralone-parallel-5.6` branch does not change this BEVFusion
core; its parallelism comes from running the independent LiDAR-only OD and
camera-only MapTR modules concurrently.

The selected implementation order for the independent MapOD runtime is:

1. Preserve the planned accuracy-valid four-camera/single-Shared-BEV model.
2. Enqueue the camera frontend on a nonblocking camera stream before entering
   the LiDAR SCN call on a separate stream. Both wait on a point-input-ready
   event, and the fuser stream waits for camera-ready and LiDAR-ready events.
   Enqueue order matters because the current voxel-count synchronization blocks
   its CPU caller even though it need not block work already queued on another
   CUDA stream.
3. After Shared-BEV is ready, submit OD and Map heads on separate streams.
   Launch Map work before entering OD's synchronous D2H/CPU NMS so the CPU
   postprocess no longer leaves the GPU Map path idle. Preserve buffer lifetime:
   with the historical dual-route checkpoint, OD must finish consuming the
   reusable fuser output before the Map route overwrites it.

SCN optimization must start by splitting the current combined stage into
buffer clear, hash/voxelization, voxel-count D2H synchronization, reduce-mean,
spconv rulebook construction and sparse kernels. Safe runtime candidates are
stream-local/event synchronization, generation-tag or touched-voxel buffer
reset, persistent spconv workspace and pinned/double-buffered point staging.
Model-changing candidates are calibrated/QAT INT8 sparse convolution, coarser
XY voxels, a smaller useful Z range, lower active-voxel limits and a narrower
sparse backbone; all require numerical/accuracy validation and most require
retraining. The current epoch-16 sparse ONNX contains 21 SparseConvolution
nodes without INT8 precision attributes, so it follows the FP16 parser path;
INT8 cannot be enabled correctly by changing only a deployment profile flag.

After the frontend, the other high-value work is OD/Map head concurrency,
removing unnecessary synchronization around OD CPU NMS, reducing the
10-45 ms pointcloud/polygon association path, and using CUDA Graphs for fixed
dense subgraphs if profiling shows launch overhead. Cross-frame double
buffering primarily improves throughput and is not counted as a single-frame
latency reduction.

### Runtime implementation of optimization steps 2 and 3 (2026-09-15)

The independent `dl_bevfusion_mapod` runtime was changed; legacy
`dl_bevfusion`, standalone MapTR, profiles and playback scripts were not
modified.

- Four nonblocking CUDA streams now separate LiDAR SCN, camera frontend, OD
  head and Map head work. CUDA events express input readiness, the LiDAR/camera
  join, head input readiness and the historical dual-route fuser-buffer
  lifetime constraint.
- Camera normalization/depth/backbone is submitted before the blocking SCN
  host call. SCN runs on its own stream, and fusion waits for both branches.
- For the deployed Anchor3D path, the OD and Map TensorRT heads are submitted
  independently. In the dual-route compatibility path, Map route generation
  first waits until the OD engine has consumed the reusable fuser output. Map
  head execution is then overlapped with OD decode/D2H/CPU NMS.
- OD result count and bounded box output use pinned host buffers and
  stream-local asynchronous D2H followed by one OD-stream synchronization.
  This removes the previous blocking `cudaMemcpy` on implicit/default-stream
  semantics, which could serialize otherwise independent Map work.
- Benchmark documentation now treats the frontend and head regions as joined
  parallel critical paths. Caller-stream stage values are not per-branch
  kernel durations; `core_wall_ms` and outer process timing remain the primary
  A/B metrics.

Source-contract validation passes three checks covering the independent
frontend streams/event join, head submission order and pinned stream-local OD
D2H. `git diff --check` passes. Target-container compilation and real Orin
playback remain pending and must confirm both correctness and actual overlap;
no runtime performance gain is claimed before that validation.

### Follow-up after the parallel build (2026-09-15)

See [the latency follow-up](LATENCY_FOLLOWUP_2026-09-15.md) for verified Orin
installation/profile checks, competing CPU load, standalone per-engine and
per-layer timings, remaining host scheduling gaps, and the next optimization
sequence. Orin source and installed core contain `d39a0ecd1` parallel code;
the latest inspected generated profile disables detailed timing, so no new
per-stage parallel performance claim is made. The most concrete next runtime
change is a MapOD-private point-association path that returns only indices,
followed by static Map CUDA Graph evaluation and measured SCN optimization.

The follow-up also records the user-authorized stop of six failing Supervisor
programs in `qpilot-orin`: repeated missing-package startup failures accounted
for approximately six CPU cores. After the targeted stop, that container used
0.02-0.03% CPU and final host samples showed 0-2% per core, GPU 0%. Containers,
models, profiles and launchers were preserved; new playback measurements are
still pending.

## 2026-09-15 Orin single-BEV re-measurement (read-only re-read)

`/tmp/mapod_single_bev_timing.log` in `baize_ruicao-wviz-1` was overwritten by a
new playback run on 2026-09-15 02:05-02:09 UTC (10:05-10:09 CST), i.e. the run
announced as pending above has happened. Verified facts from that file:

- 1,024,937 lines / 142,410,357 bytes, one run, 1045 frames, all with
  `mode=single_bev complete=1 union_cameras=4 configured_fusion_passes=1`;
  the generated profile (02:05 UTC) has `benchmark_single_bev: true`,
  `enable_timer: true`, `precision: fp16`, `num_camera: 4`.
- Control environment at read time: `qpilot-orin` 0.03% CPU,
  `baize_ruicao-wviz-1` ~0% CPU, GR3D 0%, 0-2% per core.
- `core_wall_ms`: min 86.65 / p50 101.25 / mean 101.30 / p95 106.97 / max 184.53.
  `core_stream_ms` p50 100.89. `proc_total_ms`: min 99.14 / p50 114.65 /
  p95 120.92 / max 200.69. Proc decomposition: `points_prepare_ms` 3.35 +
  `core_call_wall_ms` 101.28 + `cloud_association_polygon_ms` 9.25 (p95 12.16) +
  `output_objects_cpu_ms` 0.41.
- Stage p50 `stream_ms`/`host_ms`: `parallel_lidar_camera_frontends`
  55.63/52.61; `od.fuser_bev_encoder` 17.67/1.45; `od.vtransform` 2.55/0.21;
  `od.bevpool` 1.16/0.03; `od.gather_d2d` 0.14/0.09;
  `od.head_postprocess_parallel_map_head` 21.99/45.19;
  `map.decode_sync_d2h_cpu` 0.07/0.29; `lidar_staging_h2d` 0.22/0.53.
- Reading (a description, not a proven cause): the two dominant host intervals
  52.61 + 45.19 = 97.80 ms are ~equal to `core_wall` 101.25 ms, while the
  matching stream intervals sum to 77.62 ms — in this configuration the frame is
  CPU-submission bound, not GPU bound.
- **Confounds — do not attribute the improvement to the parallel commit alone.**
  The previously recorded figures (min 93.2 / p50 143.0 / p95 196.5 / max 221.6
  over 69 frames) came from the pre-parallel library *and* with the
  `qpilot-orin` restart-loop load present. This run changes two variables at
  once (runtime `d39a0ecd`, competing load removed).
- `map_instances=0` for all 1045 frames (`od_boxes` 76-81). In `single_bev` mode
  the MAP head is fed the OD-route BEV, so zero instances is not surprising, but
  this is still not evidence that the MAP head can emit instances.
- Playback teardown ends with `auto abort` and a loader SIGABRT during deinit
  (`LidarObjDetNode::deinit` → `~dl_bevfusion_mapod` → `CoreImplement` →
  `MapTRHeadImplement` dispose → `MapODTensorRT::EngineImplement` →
  `nvinfer1::IExecutionContext` release; one counted-deleter frame resolves into
  the legacy `libperception_q_bevfusion_core.so`). It occurs after the last
  measured frame; recorded as an independent, unanalysed defect.

## 2026-09-15 instrumentation of the LiDAR/SCN path (runtime `b2e226e3`)

Runtime repo `perception_q`, branch `release-test-mapod-share-model-5.7`,
commit `b2e226e3` (`perf: instrument LiDAR/SCN sub-stages and per-section CPU
time`), pushed to origin; parent `d39a0ecd`.

- Adds `[MAPOD_SCN_STAGE]`: the LiDAR branch's own device timeline, recorded on
  the LiDAR stream (`begin`, `scn.clear_memset`, `scn.hash_build`,
  `scn.scatter`, `scn.count_wait_sync`, `scn.reduce_mean`,
  `scn.spconv_forward`).
- Adds `[MAPOD_CPU_SPLIT]`: per-section host wall time accumulated over the
  frame, with `calls=`. Section names match the corresponding `MAPOD_STAGE`
  marks except `scn.count_d2h_issue`, `scn.zero_voxel_fallback`,
  `camera.frontend_submit`, `od.head_enqueue`, `map.head_enqueue`,
  `od.head_decode`.
- Timing-only by construction: outside the timed path every hook is a null-trace
  no-op, and the existing `MAPOD_STAGE` mark names and order are unchanged, so
  the 101.25/106.97 baseline above remains comparable.
- Verified locally in `baize-welldriver-wviz-1` (CUDA 11.4 / TensorRT 8.5.2.2):
  `bevfusion_mapod_core` rebuilds from touched sources with exit 0 and no new
  warnings; ad-hoc assertions confirm the three translation units were really
  recompiled, every pre-existing hook name is retained, and no new CUDA call
  appears in the runtime path. Script: `/tmp/hermes-verify-mapod-scn-instr.sh`.
- **Orin's container has no GitLab credentials** (`git ls-remote` fails with
  `could not read Username for 'https://gitlab.qomolo.com'`), so the Orin
  checkout cannot `git pull`; sync by patch. Verified Orin layout: source
  `/debug/src/perception_q` (at `d39a0ecd1`, clean, tracking origin), build
  `/debug/build/perception_q` (Unix Makefiles, `CMAKE_INSTALL_PREFIX=/debug/install`,
  targets `bevfusion_mapod_core` and `install`), playback
  `/debug/baize_player/qbaize_play.sh`.

## 2026-09-15 Codex collaboration protocol (user-defined, in force)

- Codex directs this work; Hermes implements, records here, and reports back.
  Verified invocation: `codex exec -m gpt-6-astra -c model_reasoning_effort=medium
  -s read-only "<brief>"` (the read-only sandbox is what enforces the split — it
  cannot write files); a live probe self-reports as `GPT-6`.
- Continue the existing thread with `codex exec resume <session id>`; the task
  thread for this work is session id `01a070d7-60a9-7061-9286-4415abdedc73`
  (cwd `/data/baize/baize-welldriver/code/maptr`, fork of
  `019fa6aa-a93f-7e51-9d9b-5760534ff9a0`, last active 2026-09-15 10:07 CST).
- The user runs the Orin measurements and relays their results; Hermes summarises
  and reports to that thread, then implements what it decides.

## Open questions / handoff (2026-09-15)

- The SCN optimisation menu is queued pending the split measurement. Runtime-safe
  candidates (no model change): shrink or remove the per-frame 4.8 MB hash-table
  and 25.6 MB `voxels_temp` `cudaMemsetAsync` (generation-tag/epoch reset or
  clearing only the point-count array); right-size the hash table to the actual
  point count instead of `max_points`; half accumulation in `voxels_temp`;
  remove the redundant host-to-host staging copy; sweep
  `SPCONV_FIXED_LAUNCH_POINTS` (read at engine-build time, so one playback per
  value); move the voxel-count D2H/sync off the critical path, including the
  library's unused DDS pointer. Export/model-level candidates: rulebook fixed
  into the ONNX with a fixed point count and a tightened `max_output_points`;
  coarser XY voxels, narrower Z range, narrower backbone, calibrated INT8.
- `libspconv_q.so` internals are unreachable — it is a prebuilt third-party
  binary under `/opt/qomolo/welldrive/third_party/third_party_binary/lib` — so
  `scn.spconv_forward` can only ever be measured as one stage.
- Two correctness hazards sit inside the code the SCN work touches and must be
  fixed before any capacity experiment: the returned voxel count is not clamped
  after scatter drops out-of-capacity voxel IDs, and the zero-voxel fallback path
  has no valid initialised feature/index.
