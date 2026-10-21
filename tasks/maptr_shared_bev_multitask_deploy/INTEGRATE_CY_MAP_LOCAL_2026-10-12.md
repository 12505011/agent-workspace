# CY-MAP best1 local runtime/profile integration

User requested pushing the existing release version first, then creating a
separate branch for the newly exported RTX3060 model. User performs C++
compilation and playback. No training, Orin, installed-library or playback
script changes were made.

## Repositories and preserved fallback

- Runtime: `/data/baize/baize-welldriver/src/perception_q`.
- Profile: `/data/baize/baize-welldriver/src/perception_q_profile_project`.
- Existing branch `release-test-mapod-share-model-5.8-1012` pushed to origin
  in both repositories; remote refs independently verified:
  runtime `987d19b675594c479d9df84f620d36175769cfd0`,
  profile `b0fd0a02fe5896ee6dc57d0f89954b18f7bdb39a`.
- Both repositories now on local branch
  `release-test-mapod-share-model-5.8-1012-cymap`.
- New local commits (not pushed): runtime
  `79153076e85f2e3ce944eae80f332986e58aa422`; profile
  `469ad892dbd90133a92733b51f944f3d6eb6da92`. Both worktrees clean.

## Model/runtime contract

Container bundle:
`/debug/code/maptr/work_dirs/onnx_engines/qth_cymap_mapfit_best_epoch1_20261012/build_rtx3060_cuda114_trt8522_mixed`.
See [export identity and module parity](EXPORT_CY_MAP_BEST1_LOCAL_2026-10-12.md).

- Single shared camera/LiDAR frontend and one fuser enqueue. Fuser exposes
  `fused_bev [1,256,180,180]` for CY-MAP and
  `middle [1,512,180,180]` for Anchor3D OD. Parallel schedule retained; no
  serial option added. Old middle-only bundle is not accepted for CY-MAP.
- Standard-op MAP plan: no custom MapTR `.so`; `map_plugin: ""`.
  TensorRT built-in plugins still registered (needed by fuser).
- MAP6layers/70queries/20points/7classes; top50, operational score0.4;
  normalized cxcywh bbox ROI filter matches native MapQR coder x[0,54],
  y[-10,10]. No point clipping or adaptive score relaxation.
- OD11classes/22anchors. Runtime checks head binding shapes against parsed
  postprocess parameters before allocating/enqueueing. Correct RTGC width3.0,
  QC width3.7 and Qtractor anchor [3.4,1.9,2.8]; retain existing project
  label mapping and per-class scores, NMS0.2, pre2000, max500.
- All engine I/O FP16. Camera/VTransform/OD FP16-enabled, fuser/MAP FP32
  compute without TF32. This is not the old FP16 latency-only candidate.

## Camera/preprocess verification

Actual local container calibration, not inferred from old logical names:
raw0=`front_top_mid`, raw1=`front_mid_left`, raw6=`front_mid_right`;
raw7=`front_mid` is not used. Keep remap0/1/6 -> private0/1/2.
Actual saved config's final `data.val.map` and `data.val.object` pipelines
both select TOP_MID/MID_LEFT/MID_RIGHT and resize0.48+crop704x256.
All three profile modes remain `resize_crop_train`. Ignore stale top-level
reference dataset variables in the saved config that mention letterboxing.
Player1400x1000 crop(220,116,960,768), raw960x768 and intrinsic scaling remain.

Both profile79 and renamed overlay78-env0-mapod_cymap_best1.yaml match exactly.
Semantic comparison verified every non-MapOD field in profile79 unchanged.

## Validation and handoff

- 9 runtime source-contract checks + 3 YAML semantic checks pass;
  `git diff --check` clean. These are not C++ execution tests.
- Actual artifact config comparison verifies class count, flattened anchor
  dimensions/rotations, MAP top50/ROI and voxel0.075/0.075/0.2.
- All five dense plans pass manifest SHA256, deserialization with built-in
  plugins, FP16 I/O checks. Exact fuser/MAP/OD shapes/directions verified;
  camera backbone confirms three cameras, 256x704. No inference run this turn.
- Read-only Python deserialization needs existing TRT8.5.2.2 wheel at
  artifact `validation_tools/trt8522_python` and
  `LD_LIBRARY_PATH=/opt/TensorRT-8.5.2.2/lib:/usr/local/cuda/lib64` for that
  process only. No permanent environment modifications were made.
- Rebuild runtime core and algorithm together: Transfusion vtable and
  Anchor3D parameter layout changed. User compilation/install, sparse graph
  execution, full playback and actual accuracy/latency acceptance pending.
- Model engines/checkpoints are not committed to Git. Original branch and
  historical engine bundles remain available for fallback.

## Local MapTR ROS visualization topic

- Added `pointcloud_topic_list=maptr_pointcloud` under `ros_assistant_q.tags`
  in `/data/baize/baize-welldriver/runqfile/baize_player/qbaize_play.yaml`.
- Existing `ROSAssistant` implements this tag and the installed
  `/debug/install/lib/libvisassist.so` contains it. It subscribes to the
  Baize `PointCloud2` output and forwards `/maptr_pointcloud` as ROS
  `sensor_msgs/msg/PointCloud2`, preserving header and point fields.
- YAML parse and tag placement verified. No tool-library rebuild required;
  restart playback to load the tag, then add the PointCloud2 topic in RViz.
  Live publication/display has not been verified in this change.
- Existing unrelated `ros_tools` source edits were not modified.
