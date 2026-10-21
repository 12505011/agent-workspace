# Epoch24 staging on 98 Orin — engine ready, waiting for playback

User requested same deployment code and epoch24 model for Orin latency testing.
Per current division of labor, no agent C++/engine build or playback on Orin.

- Reachable:98Orin, fixed container `baize_ruicao-wviz-1`, aarch64/TRT8.5.2.2.
- Previous source clean, HEAD539a3d82, installed core/algorithm dated Oct8.
  It lacked the new CY fused_bev binding; merely replacing engines was unsafe.
- New branch `release-test-mapod-share-model-5.8-1013-map5-epoch24` created
  from539a3d82. Applied binary diff of ONLY12MapOD source/doc files from local
  current working tree. All12sourceSHA256 match local; git diff--check passed.
  No commit/push; original branch retained. Installed libraries unchanged.
- Bundle `/debug/code/maptr/models/qth_frozen_map5_epoch24_20261013/`;
  host bind root `/data/code/all_ws/ws/ruicao/baize_ruicao`.
  SixONNX SHA256 checks passed. RTX3060 plans were NOT transferred.
- Target precision matches local mixed acceptance: camera/vtransform/OD FP16
  enabled; fuser/MAP FP32 noTF32; all externalbindings FP16. Do not call it a
  pureFP16 latency candidate or compare blindly toOct8FP16latency-only timing.
- Target Python NumPy1.24.4/YAML/TRT8.5.2.2 and trtexec available.
- `build_runtime_orin.sh`: user compiles core+algorithm, records trueEXIT,
  backs up installed libraries under new bundle/runtime_before, selectively
  installs only the two newly built libraries. No unrelated module install.
- `prepare_orin_deployment.py --build-and-select`: requires both installed
  library hashes changed and fused_bev symbol; builds all5denseplans ON TARGET,
  checks each deserialize/execute and fixed-input MAP parity before generating
  independent `/debug/baize_player_map5_epoch24/`. Verified successful-plan
  receipts allow safe resume; unknown partial plans refuse automatic overwrite.
- Independent complete perception profile preserves Orin non-MapOD baseline,
  replaces onlyMapOD params from locally tested epoch24profile. Canonical7wire
  slots contain5trainedclasses, unusedslots4/5disabled;50queries/20points/6layers,
  raw0/1/6, private0/1/2, singlefusion, parallel schedule, timers enabled.
- Existing playback/profile untouched. New player retains existing Orin packet
  directory `/debug/issue/jk_mapod`, fixes inherited camera7 blacklist typo to
  camera_7 while retaining required raw0/1/6; creation waits for allbuildchecks.
- System eMMC initially100%full; failed payload copy left97MBof OUR partial
  archive. Moved thatpartial todata disk, resumed--append-verify successfully.
  Existing models/logs/data untouched. NVMe/data has~150GBfree; systemdisk remains
  nearfull, can still affect unrelated services. No containers stopped.
- 2026-10-13: user decided to retain the existing C++ runtime and original player;
  no C++ build/install is required for this model update. The actual source profile
  `/debug/src/perception_q_profile_project/project/cnwxijk/qthd/perception_q/79-perception.yaml`
  was backed up as `79-perception.yaml.before_map5_epoch24_20261013` and its
  `dl_bevfusion_mapod.params` was replaced with the epoch24 contract.
  Verified: model path `.../build_orin_cuda114_trt8522_mixed`, raw camera remap
  `[0,1,-1,-1,-1,-1,2,-1]`, 3 cameras, 50 vectors, 20 points, 6 decoder layers.
- 2026-10-13: all target-native mixed-precision engines were built in
  `.../build_orin_cuda114_trt8522_mixed`: camera backbone/vtransform/OD head use
  FP16; fuser and Map decoder retain FP32 internals with FP16 external I/O and
  `--noTF32`. Five build checks plus five deserialize/execute checks passed;
  SHA256 manifest covers all five plans, lidar ONNX, and `libmaptr_plugins.so`.
  Existing runtime/player are unchanged. Playback and latency remain user-run.
