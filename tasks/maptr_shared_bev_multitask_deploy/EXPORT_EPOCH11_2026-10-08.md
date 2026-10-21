# MapOD epoch11 local ONNX and 98 Orin engine build

User requested copying `/data/Downloads/mapodpth/epoch_11.pth` into the local
MapTR repository, exporting ONNX, checking 98 Orin connectivity, and building
target engines. This authorizes independent artifact creation/build, not
production profile installation, service changes, or Git pushes.

## Verified inputs and contract

- Local repository: `/data/baize/baize-welldriver/code/maptr`.
- Checkpoint copy: `work_dirs/checkpoints/mapod_samearch_joint_epoch11_20261008/epoch_11.pth`.
- Source and copied checkpoint SHA256:
  `db2c5fc2b14acedbc316071eec1e9a130046f775aab67077936c45d568aa1517`.
- Metadata epoch11 / iteration38885; same entity as joint training
  `job-4eb88b7f2b38f52a3b329ea5` and user-approved visualization
  `job-fa6183a93a61a1b2b28e87a1`.
- Downloaded actual parent training config `config/same_arch_actual.py` beside
  the checkpoint. SHA256:
  `ee24b34871e4b2e447373d1cf925599daaaefff1c7c23a6e8b75197993ca78a7`.
  This config is executable, and strict full checkpoint restoration passed
  for all 870 model state entries. Do not substitute current voxel0.1 recipes.
- Voxel `[0.075,0.075,0.2]`, sparse grid `[1440,1440,41]`, native and shared
  BEV180x180, decoded channels512, GN decoder.
- Both tasks share `[CAM_FRONT_MID,CAM_FRONT_LEFT,CAM_FRONT_RIGHT]`, 256x704,
  identical validation preprocessing and a single camera/fusion route.
- Anchor3DHead: 10 OD classes; MapTRv2: six decoder layers,40 vectors,20points,
  seven map classes including stop_line. Crop34x90 with configured transpose.
- A machine-readable `deployment_contract.json` stores actual camera
  preprocessing, anchors/classes/ranges and postprocess defaults.

## Local export and verification

Artifact root:
`work_dirs/onnx_engines/mapod_samearch_joint_epoch11_20261008/`.

The existing Shared-BEV exporter created six graphs in `onnx/`:
camera.backbone, camera.vtransform, lidar.backbone.xyz, fuser,
anchorhead.bbox, maptr_decoder_head. Export logs and export_manifest.json
are retained. Five dense graphs passed stock ONNX checker; the custom sparse
graph passed topology/interface checks.

- Native/patched Map output parity: maximum absolute difference0 for all
  three raw outputs; shapes `[6,1,40,7]`, `[6,1,40,4]`, `[6,1,40,20,2]`.
- Fixed synthetic FP32 PyTorch vs CPU ONNX Runtime: camera.backbone,
  camera.vtransform,fuser,OD head all passed atol/rtol1e-3; maximum absolute
  discrepancy3.505e-5. TF32 disabled. Map custom plugin is not stock ORT
  compatible; a native reference is saved for target TRT comparison.
- Sparse graph has21convolutions with all21fused-BN bias tensors serialized,
  all weights finite, no INT8 precision attributes. It remains custom
  sparse-runtime ONNX rather than a standard TensorRT plan.
- Three exporter/contract unittests passed. Pytest is not installed in local
  maptr env; tests ran using unittest, without installing dependencies.

Existing dirty exporter fixes and unrelated converter edits were preserved.
No training recipe or runtime/profile was modified for this export.

## 98 Orin

- SSH connectivity passed; host `miivii-tegra`.
- Fixed container `baize_ruicao-wviz-1`, CUDA11.4/TRT8.5.2, ARM64.
- Existing ARM MapTR plugin source .cu/.cpp hashes match local maintained
  source; dependencies resolve. Use the target ARM plugin, not local x86 so.
- New independent host artifact root:
  `/data/code/all_ws/ws/ruicao/baize_ruicao/code/maptr/models/mapod_samearch_joint_epoch11_20261008/`.
- Container artifact root:
  `/debug/code/maptr/models/mapod_samearch_joint_epoch11_20261008/`.
- Six ONNX MD5 values verified against local manifest after transfer.
- Target build directory: `build_orin_cuda114_trt8522_fp16/`.
- Owned build started once with PID199999 (host docker-exec client).
  `build_orin.log` plus `build.exitcode` preserve true completion status.
- Build script invokes five FP16 dense-engine builds and deserialize/inference
  smoke checks. Camera backbone, VTransform,fuser,OD builds verified complete;
  MAP build was still running when this initial note was written.

## Outstanding acceptance

Finish target build/smokes and fixed-input native-vs-TRT comparisons. Record
numeric tolerances and any failures explicitly. Recorded-data full pipeline
replay, sparse-runtime execution and production deployment are not yet
validated by these synthetic checks. Existing deployment has historical
camera/layer/point settings and must not be silently replaced.

## Baseline completion and precision failure (verified)

- The five default FP16 plans finished, build.exitcode=0; all five trtexec
  deserialize/inference smokes returned PASSED. A checksum-verified copy is
  now also under the local artifact root's build_orin_cuda114_trt8522_fp16/.
- Fixed-input numerical checks reject the baseline MAP plan: decoder layers
  0/1 are finite, layers2–5 are entirely NaN, affecting8160of12240raw values.
  The trtexec output JSON contains lowercase nan, so a generic JSON parser
  error was the first symptom; it is not just a JSON-formatting problem.
  DO NOT install/use this baseline MAP engine as an accepted model.
- Camera and OD fixed-input outputs are finite and within atol/rtol0.02.
  Fuser outputs are finite, relativeL2=0.0036083;347of16588800elements exceed
  atol/rtol0.02, maxAbs0.0588685. The elementwise gate is not marked passed.
- A minimal sigmoid→inverse_sigmoid graph reproduces FP16 Inf on Orin for
  logits9/11/12. Keeping this math FP32 while preserving FP16 bindings yields
  finite results9/11/11.5078/-11.5156, consistent with the FP32 reference.
  Local CUDA FP16 arithmetic independently reproduces Inf. This identifies
  an actual unsafe arithmetic path; full-model sufficiency still needs testing.
- Precision-controlled MAP candidate is being built independently in
  build_orin_cuda114_trt8522_fp16_safe/. Original ONNX/weights untouched.
  map_precision_policy.json protects121reference-point-related nodes and109
  floating outputs inFP32, with obey constraints, other eligible layers and
  external bindings stillFP16. PID2423133; safe_build.exitcode records outcome.
- Candidate builder and minimal precision_probe artifacts are retained under
  the same local/Orin artifact roots. No production source/profile changed.

### Targeted reference-point policy was insufficient

- The protected MAP candidate built successfully in504.275seconds and loaded,
  but the identical fixed-input test still has8160NaN outputs. Do not accept
  either FP16 MAP candidate.
- Engine layer inspection confirms protected Sigmoid_567 usesFP32 inputs and
  output; the policy was applied, not silently omitted. The minimal inverse
  sigmoid reproducer identifies a real precision hazard, but does not prove
  it is the full model's sole failure cause. Normalization/attention and
  plugin arithmetic still need distinguishing.
- A second controlled candidate is now building the same entire MAP graph in
  FP32 computation with TF32disabled, while retaining FP16 external bindings.
  Directory build_orin_cuda114_trt8522_mixed_safe/, owned PID2582138,
  builder build_map_fp32.py, completion fp32_build.exitcode. Do not claim it
  passed before target fixed-input output comparison.

### FP32 control and attention localization

- Full FP32-compute MAP built successfully in195.891seconds. It removesNaN,
  but still fails parity severely: class maxAbs5.88665, normalized point
  maxAbs0.684806, synthetic local-coordinate point max error33.5812m.
  Layer0agrees within FP16 output rounding; divergence starts at layer1.
  This candidate is NOT accepted for deployment.
- Verification-only graph replaces the six single-level MSDA ops with
  mathematically equivalent standard GridSample+weighted sum. CPU ORT vs
  native PyTorch agrees across all six layers: cls maxAbs6.676e-6,
  bbox7.749e-7, points7.153e-7. Thus the exported surrounding graph itself
  is validated by an independent standard-op execution path.
- Actual native per-layer MSDA inputs and layer1 first self-attention inputs
  captured. OnOrin, six isolated MSDA executions each have maxAbs4.992e-7;
  isolated MHA maxAbs5.484e-6. Both isolated implementations are consistent.
  Remaining discrepancy is full-graph execution/interoperation, not proven
  to be a standalone plugin-kernel or MHA error.
- A standard-op full MAP FP32 target control is being built in
  build_orin_cuda114_trt8522_standard_map_fp32_v2/ (PID2879987,
  standard_v2_build.exitcode). Its standard graph is uploaded to the
  user-writable artifact root as map_standard_diagnostic.onnx.
- Initial standard build preflight failed because scp could not write into
  a root-owned validation subdirectory. Failure retained in the non-v2
  directory; no library, system permission, or old model was changed.

## Accepted accuracy-first components and final bundle

- Standard GridSample MAP FP32-compute candidate built successfully in
  62.7931 seconds, with FP16 input/output bindings. Identical fixed-input
  comparison passes across all six decoder layers: class maxAbs0.0027895,
  normalized points maxAbs0.000245392, bbox maxAbs0.000243902. All outputs
  finite. Synthetic local-coordinate point difference max0.0138716m,
  mean0.00483237m; this is a module parity result, not a dataset metric.
- Fuser FP32-compute control, FP16 input/output bindings, also passes the
  original atol/rtol0.02 gate: maxAbs0.00195169, relativeL2=0.000207637;
  zero out-of-tolerance elements among16588800values. No tolerance loosened.
- Validated six-graph ONNX directory: `onnx_validated_standard_map/`. The
  standard MAP graph MD5 is0c3e13d1004d17d351934c1d976a49f3. All six shape/
  structural contracts checked, including the custom sparse LiDAR contract.
- Selected new target bundle: `build_orin_cuda114_trt8522_mixed_validated/`
  under the same local/Orin artifact roots. Camera backbone, VTransform,
  OD head are baseline FP16 plans; Fuser and standard-op MAP use FP32
  compute with TF32disabled. Dense runtime bindings remainFP16. Five plans,
  sparse LiDAR ONNX, ARM plugin, actual config, deployment/export/engine
  manifests, source logs and SHA256SUMS are assembled without modifying
  older candidates. Standard MAP does not require the custom MAP plugin.
- Repeated deserialize/fixed-input inference of all five final-bundle plans
  succeeds (validation.exitcode=0). Final plans/outputs were mirrored locally;
  SHA256SUMS verifies all20initial package files. Repeat numerical comparison
  against native PyTorch passes all5modules with the unchanged predefined
  tolerances; all outputs finite. Report:
  `validation_mixed_validated/trt_numerical_report.json`, pass=true. Packaging
  also attaches this report and the accuracy/precision caveats README.
- No recorded-data full-pipeline replay, sparse-runtime execution or
  performance acceptance has been completed. No production profile/model/
  service was replaced. This is not a pure FP16 optimized deployment.
