# CY MAP best epoch1 — local ONNX/RTX3060 export

User associates this work with task/maptr_shared_bev_multitask_deploy and
selects local effect inspection rather than an Orin build. No Git commit/push,
training cancellation, playback, runtime/profile edits, or service changes.

- Moved Downloads/best_map_NuscMap_chamfer_mAP_epoch_1.pth into local MapTR
  `work_dirs/checkpoints/qth_cymap_mapfit_best_epoch1_20261012/`.
- SHA2568dc3e421f0fa050c8a8b14c6a102ca92b5b0bec8992cc65de87c241ef2329f05;
  matches job-3f76fe848bad65327edd2bef bestMAP1; metadata epoch1/iter1190.
- Artifact root local MapTR
  `work_dirs/onnx_engines/qth_cymap_mapfit_best_epoch1_20261012/`.
- Complete actual config recovered from existing parent training log, not
  guessed from filename; strict902entry model restoration passed.
- CYMapTRv2Head: dedicated dilated GN neck on256channel pre-OD-decoder fused
  BEV; metric sampling ROI x[0,54],y[-10,10] to34x90;6layers,70vectors,20points,
  MAP7classes; OD Anchor3D11classes; LiDAR0.075/0.075/0.2, native180x180;
  three cameras TOP_MID/MID_LEFT/MID_RIGHT, normalized to MID/LEFT/RIGHT.
- New export-only CY wrapper preserves neck/metric sampling, uses standard
  GridSample MSDA, and omits only unrelated auxiliary segmentation outputs.
  Training model files unchanged. Fuser exporter exposes middle512channels
  and fused_bev256channels from one fusion; old shared-BEV export unchanged.
- Local native ops restored from existing maptr-cy-before-flatten backup only
  after non-.so/non-pycache ops trees compared identical; actual model load
  and native attention execution passed.
- Five new exporter tests pass, including CUDA ROI exact rounding,
  native/patched/CPUORT roundtrip, one-fusion/two-output contract, actual-log
  config extraction, and dynamic graph contract.
- Six ONNX graphs structurally verified; five standard graphs checker-pass.
  Sparse graph remains custom parser ONNX, not a TensorRT plan.
- Native-vs-ORT MAP comparison passed; maxAbs cls0.00041056,
  bbox0.00005260,normalized points0.00012213 on fixed synthetic input.
- All five RTX3060/TRT8.5.2.2/CUDA11.4 dense plans built, deserialized,
  executed and passed unchanged fixed-input parity gates, all outputs finite.
  Selected directory `build_rtx3060_cuda114_trt8522_mixed/`.
- Camera/VTransform/ODFP16-enabled; fuser/MAPFP32compute,FP16I/O,TF32disabled.
  Not a pureFP16 latency result. Native-vs-TRT MAP maxAbs cls0.00865364,
  normalized points0.00270283 under atol+rtol0.002 gate (not maxAbs0.002).
  Numerical report retained at `validation/trt_numerical_report.json`.

Outstanding: local playback integration, sparse runtime execution and actual
recorded-data effect inspection. Existing old runtime cannot be assumed to
accept this model by changing only paths: MAP now consumes fused_bev256,
fuser has two outputs, MAP70vectors, OD11classes. User was asked whether
local effect inspection means qbaize playback or validation-set images.
No local mount of platform `/mnt/storage/public` / JK validation data found.
Do not overwrite historical engine bundles or switch perception_q branch
without the user's selected playback workflow.
