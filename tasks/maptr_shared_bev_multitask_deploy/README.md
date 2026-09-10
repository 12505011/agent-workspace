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
- [ ] Export the selected checkpoint to ONNX.
- [ ] Validate ONNX outputs against PyTorch on fixed samples.
- [ ] Build TensorRT engines for the selected target GPU/TensorRT environment.
- [ ] Validate TensorRT outputs against ONNX/PyTorch.
- [ ] Integrate the shared runtime and both postprocessing/output paths into
  `release-test-mapod-share-model-5.7`.
- [ ] Update and validate `79-perception.yaml` for the new model contract.
- [ ] Build, replay, and verify both OD and Map outputs together.

No ONNX or TensorRT engine has been produced for this selected checkpoint yet.

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

1. Use `release-test-mapod-share-model-5.7/src/dl_runtime/dl_bevfusion` as the
   target integration point.
2. Reuse verified infrastructure from the 5.6 `dl_bevfusion` and
   `dl_bevfusion_maptr` implementations, but port only contracts compatible
   with the selected shared model.
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
