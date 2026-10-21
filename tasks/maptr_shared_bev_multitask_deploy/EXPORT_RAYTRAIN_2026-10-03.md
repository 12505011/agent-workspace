# RayTrain custom MapOD: local ONNX export, 2026-10-03

## Scope and ownership

User associated this work with MapOD deployment and narrowed the immediate
scope to copying checkpoints into the local project and exporting locally.
No Orin transfer, engine build, runtime/profile modification, commit or push
was performed. Existing training worktree changes and historical products
were preserved.

Agent-workspace branch: `task/maptr_shared_bev_multitask_deploy`.
Training/export branch: `bev_3dod_maptr_shared_bev_mmdet3d`.
Repository: `/data/baize/baize-welldriver/code/maptr`.

## Verified checkpoint identity

Both are complete joint models from job `job-a9aeff604265f1b78341ec34`, not
independently composable task heads. They were copied, not moved, from
`/data/Downloads/mapodpth`. Each file has 532854675 bytes.

Local directory relative to repository:
`work_dirs/checkpoints/raytrain_custom_gn6_p20_voxel01_20261001/`.

| Checkpoint | Metadata epoch / iter | SHA256 |
| --- | --- | --- |
| `best_map_NuscMap_chamfer_mAP_epoch_12.pth` | 12 / 91356 | `9c0d92e02f26ef5976d0e329de2d4982b2c64e278c46b651635b602b144a488c` |
| `best_object_object_map_epoch_24.pth` | 24 / 182712 | `e35742ee9b573b60bdcb0df219d0239b209f0d0c4209ef6e98156addbaea60bb` |

Epoch 12 remains the primary candidate consistent with the selected joint
visualization. Epoch 24 was exported independently, without mixing weights.

## Config provenance and actual contract

Checkpoint `meta` contains no config. Used executable source
`configs/maptrv2/westwell/bevfusion_maptr_shared_bev_raytrain_custom_joint_6layer_voxel01_24e.py`.
Its resolved model dictionary equals the actual model dictionary printed in
the saved formal training log `/tmp/mapod-gn-p20-formal.log`, after ignoring
only the external ResNet pretrained initialization checkpoint path. Both
complete checkpoints loaded with strict state-dict checking.

Frozen expanded source config is beside the checkpoints:
`export_resolved_config.py`, SHA256
`2671451cf8c396b6d2eea5da05f44f1b6643ef52bb79b5ef7cf178371d24cbc6`.
This is an export snapshot of resolved local source, not a downloaded copy of
the platform's original `custom_joint_actual.py`.

- Both tasks: `[CAM_FRONT_MID, CAM_FRONT_LEFT, CAM_FRONT_RIGHT]`, same order.
  Read `FilterCameraViews` in actual validation pipelines; inherited
  top-level `od_camera_names` / `map_camera_names` remain stale historical
  declarations and must not determine this deployment.
- Camera input `[1,3,3,256,704]`; depth `[1,3,1,256,704]`.
- LiDAR voxels `[0.1,0.1,0.2]`, range `[-54,-54,-1,54,54,7]`, sparse grid
  `[1080,1080,41]`; native dense output `[1,256,135,135]`.
- Shared decoded BEV `[1,512,180,180]`; Fuser takes camera
  `[1,80,180,180]` and native LiDAR `[1,256,135,135]`, performing the same
  bilinear alignment to 180x180 as training (`align_corners=False`).
- Shared decoder retains GN. OD is **Anchor3DHead**, 10 classes / 20 anchors.
- Map is MapTRv2, six decoder layers, 40 vectors, 20 points, seven classes
  including stop_line. Map crop `[0,-10,-10,54,10,10]` becomes 34x90 using
  the trained xy-to-yx crop transpose.
- Raw Map outputs `[6,1,40,7]`, `[6,1,40,4]`, `[6,1,40,20,2]`.
- No temporal queue was added; these weights were trained with queue length 1.

## Artifacts and local exporter changes

Independent ONNX directories relative to repository:

- `work_dirs/onnx_engines/raytrain_custom_gn6_p20_voxel01_epoch12_20261003/onnx/`
- `work_dirs/onnx_engines/raytrain_custom_gn6_p20_voxel01_epoch24_20261003/onnx/`

Each contains `camera.backbone.onnx`, `camera.vtransform.onnx`,
`lidar.backbone.xyz.onnx`, `fuser.onnx`, `anchorhead.bbox.onnx`,
`maptr_decoder_head.onnx`, stage logs and `export_manifest.json` with MD5,
interfaces and trained camera routing.

This uses the **shared-BEV six-graph exporter**, not the camera-only four-graph
skill wrapper. Local exporter adaptations, still uncommitted:

- `export_anchor3d.py`: reproduce `_align_fuser_inputs`, trace distinct camera
  and LiDAR native input shapes, evaluate real shared output for OD input,
  persist static Fuser output shape after tracing.
- `inspect_shared_bev_onnx.py`: derive contracts from resolved config rather
  than hard-coded historical four-layer/15-point/180-native geometry; read
  camera routing from validation pipelines.
- Regression tests `test_shared_bev_fuser_export.py` and
  `test_shared_bev_onnx_contract.py` were observed failing before fixes.

Export command used `deployment/scripts/3dod_maptr/export_shared_bev_multitask_onnx.sh`
with explicit CONFIG, CHECKPOINT, CAMERA_COUNT=3, OUTPUT_ROOT and
PYTHON_BIN=/home/westwell/miniconda3/envs/maptr/bin/python.
`PYTHONNOUSERSITE=1` avoids user-site dependency contamination; wrapper uses
`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` and `NUMBA_DISABLE_JIT=1`.
Local versions: Python 3.8, Torch 1.10.1/CUDA 11.3, MMCV 1.4.0,
ONNX 1.12.0; GPU RTX3060.

## Validation actually completed

- Both checkpoint copies passed SHA256 verification and strict loading.
- Five standard/custom-domain dense graphs per checkpoint passed stock ONNX
  checker and exact declared name/shape contract validation.
- Sparse custom-parser graph passed input availability/topological
  connectivity and native 135x135 output shape checks. Stock ONNX checker
  does **not** support its default-domain sparse operators.
- Map exporter native-vs-patched PyTorch outputs: all three maximum absolute
  differences 0 for both checkpoints.
- Camera backbone/depth, camera downsample, shared Fuser/GN decoder and OD
  head: seeded synthetic input comparison between CUDA PyTorch and CPU ONNX
  Runtime passed for both checkpoints, finite outputs, atol=rtol=1e-3.
  Maximum absolute error: epoch12 2.47955e-5, epoch24 4.09484e-5.
  See each directory's `numerical_validation_strict_fp32.log`.
- First epoch12 comparison with default TF32 enabled failed the camera
  tolerance (max abs 0.00200808). Same seeded comparison with CUDA matmul
  and cuDNN TF32 disabled passed; original failed log is preserved as
  `numerical_validation.log`. Do not relax tolerance to hide precision mode.
- Eight relevant `test_shared_bev*.py` tests passed; `git diff --check` passed.

## Remaining gates

Synthetic numerical tests do not establish recorded-frame accuracy. Map ONNX
execution through its custom ms_deform_attn plugin and sparse ONNX execution
through the deployment parser remain unverified for this checkpoint. No
TensorRT engines have been built in this task.

Before Orin build/install, verify the target's plugin and runtime contract:
native LiDAR is now 135x135, Fuser has unequal native input sizes and includes
a resize, Map has six layers / 20 points, and both tasks use one shared
three-camera route. Historical epoch16 four-camera/two-route, four-layer /
15-point profile values are not this model. Build target-specific FP16 plans
in a new independent directory; never copy RTX3060 plans as Orin plans or
replace the active production bundle without separate authorization.
