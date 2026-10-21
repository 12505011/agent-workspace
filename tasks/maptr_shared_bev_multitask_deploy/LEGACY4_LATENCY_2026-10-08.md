# Legacy four-layer MapOD latency comparison: measured

User requested measuring the previous four-layer MapOD deployment after the
epoch11 six-layer single-fusion run. Agent selected the original bundle but
did not start playback, compile, stop processes, change libraries or commit.

## Verified old artifact contract

- Bundle: `/opt/qomolo/qpilot-resource/perception/model/dl_bevfusion_mapod`.
- Export manifest checkpoint: historical best MAP epoch16, MD5
  `6a06245320f1f92a6f643db280222eea` (manifest identity, not new checkpoint read).
- Manifest Camera backbone inputs `[1,4,3,256,704]` and four depth images.
- MAP outputs classes `[4,1,40,7]`, points `[4,1,40,15,2]`:
  four decoder layers,40vectors,15points,7classes.
- All eight entries in engine_checksums.md5 passed actual file verification.
- Original FP16 deployment, legacy MSDA plugin, same `.075,.075,.2` voxel grid.
- Original union order raw[7,1,6,0]; OD slots[0,1,2] = raw[7,1,6],
  MAP slots[3,1,2] = raw[0,1,6]. These are different task inputs, so production
  runtime correctly retains two fusion passes. No forced single-route shortcut.

## Scoped selection and preserved baseline

Replaced only `perception_q.dl_bevfusion_mapod.params` using the exact original
79-perception.yaml.before snapshot from deployment_20261008_051553, except both
existing timer flags are enabled. Restored original four camera preprocessing
entries (three resize_crop, TOP_MID letterbox_width528x256), original anchors,
label mappings, thresholds, intrinsic defaults and model geometry.
Retains original player-undistorted crop1400x1000→ROI220,116,960x768.
Other module semantics unchanged, explicitly verified before and after render.

Updated eight source/active/staged/recording-overlay profiles as in the epoch11
deployment, so the existing qbaize profile regeneration selects this bundle.
No player script/YAML changes. Existing MapOD pipeline remains selected.
No loader_exe was running at the guarded application point.

Exact six-layer profile preimages and baseline log saved at:
`/debug/code/maptr/models/mapod_samearch_joint_epoch11_20261008/legacy4_timing_20261008_064706/`.
Report.json records each original/changed file SHA and backup path.
Baseline copy: `epoch11_shared_bev_6layer.baseline.log` (171completeframes,
141postwarmup; previous local all64metrics report remains).
Mechanical guarded deployment script locally in deployment_review/
switch_legacy4_profile.py and remotely in single_fusion_fix.406DEp/.
Dry run passed before writes; full post-application eight-profile checks passed.

## User execution and interpretation

User runs the same clip and captures `/debug/mapod_legacy4_timing.log` using
grep-before-tee with MAPOD_ tags. Expect `mode=dual_route`, cameras4,
fusion_passes2, complete1. Exclude first30completeframes for statistics.
Compare MAP-own-stream head timing, full core, outer algorithm and all stages.

THIS IS ORIGINAL OLD VS NEW DEPLOYMENT, NOT DECODER-DEPTH ABLATION.
Camera count/routes, one-vs-two fusion passes, FP16-vs-FP32-compute engines,
15-vs20points, custom-vs-standard attention and image preprocessing differ.
Do not attribute aggregate latency difference solely to4vs6decoderlayers.
Timing results are recorded below; no real-data accuracy assessment was performed.

To return to epoch11, restore exact backed-up eight profiles with after-SHA
guards; keep current shared-route source/library fix. No rollback executed.

## Measured user playback result

Actual capture: container `/debug/mapod_timing2.log`, host
`/data/code/all_ws/ws/ruicao/baize_ruicao/mapod_timing2.log`.
Snapshot size1164916bytes, mtime2026-10-08T06:50:56.887660UTC, SHA256
`6f59a496d5bfa06c4ed65c361fc9da533dee14c1996c686a3e1e0dae2f5f6bfe`.
322completeframes, exclude first30,292samples(frames31–322).
All dual_route/cameras4/fusionpasses2; no incomplete frame in capture.

P50/P95 milliseconds:
- Outer algorithm139.561/149.052; core wall127.608/137.198.
- Camera+LiDAR parallel frontend58.085/64.546; nested SCN spconv51.005/55.217.
- OD gather.132/.983, pool1.122/1.278, vtransform2.544/3.554,
  Fuser+BEVEncoder17.590/19.483.
- MAP gather2.825/3.068, pool1.098/1.136, vtransform2.529/2.548,
  Fuser+BEVEncoder17.770/20.758.
- Combined OD/MAP head caller-stream region22.878/27.608;
  MAP own-stream head17.300/22.246, through decode22.766/27.904.
- Point preprocessing3.380/3.610, cloud association7.602/10.928,
  object output.412/.608, final MAP decode CPU.081/.147.

Previous6layer baseline:141postwarmupframes, shared_bev/cameras3/fusion1;
outer168.926/184.867, core157.022/172.071, frontend51.894/57.823,
singleFuser66.149/67.814, MAPhead24.691/37.268.
New minus old median: outer+29.365ms, core+29.415ms, MAPhead+7.391ms.
Largest observed stage difference is Fuser, not solely MAPdecoderdepth.
OldtwoFP16Fusers each~18ms vs newoneFP32computeFuser~66ms is not
proof that precision alone caused the difference; graphs/routes differ too.
Pointcount medians137629/137633, not matched-frame comparison.
CPU MAP enqueue~62.7ms contains blocking, not pure MAP GPU cost.
Own-stream intervals can contain submission/idle gaps; nested stages must not
be added together. No isolated MAP incremental whole-pipeline latency test.
Filtered log has no MAPOD_OUTPUT, so no output-count/finite/accuracy conclusion.

Full72metric Markdown and CSV under local
`/data/baize/baize-welldriver/code/maptr/work_dirs/onnx_engines/mapod_samearch_joint_epoch11_20261008/deployment_review/single_fusion/`
as `timing_legacy4_all_20261008.md` and `.csv`.
This analysis was read-only on Orin; old profile remains selected.

## Three-camera / one-fusion candidate prepared (2026-10-08)

User requested aligning the old4layer deployment to the same three cameras and
one fusion as epoch11. Historical checkpoint manifest proves OD trained onMID
and MAP onTOP_MID; old rawOD[7,1,6]/MAP[0,1,6] explain its two fusion passes.
The request changes deployment inputs, not checkpoint training history.
Target private slots[0,1,2] both tasks, physicalraw[0,1,6], all three
resize_crop_train(.48) and intrinsics_scale_to_raw_image=true as epoch11.
Preserve old4layers/15points, voxel/grid/ranges, thresholds, labels and anchors.
This changes old OD middle camera and both tasks' historical preprocessing;
old accuracy equivalence is not asserted. User must review real-data outputs.

Original camera ONNX fixed4; cannot just change num_camera in YAML.
Prepared independent3camera ONNX by changing ONLY four shape initializers
1285/1295/1300/1301 plus input/output shapes, removing stale intermediate
shape hints. Learned parameters and all operator nodes unchanged (test passed).
OriginalMD5=608dcc5b03f29970b6860b8d70ce2475;
newSHA256=e7b51c47ce2633d2d9292d065778811c55bd914673c97a86d8b57e1e7e78db34.
Fixedseed20261008 ORTCPU comparison: newthree inputs selected from original
four in order[3,1,2]; camera_feature and camera_depth_weights both finite,
maxabsdiff=0, shapes[3,32,88,80]/[3,118,32,88]. This tests graph adaptation,
NOT TensorRT numerical parity or real-data prediction accuracy.
Converter and scoped profile selector each tested RED thenGREEN; suite2testsOK.

Local ONNX:
`/data/baize/baize-welldriver/code/maptr/work_dirs/onnx_engines/mapod_legacy4_shared3_20261008/onnx/`.
Local preparation scripts/tests:
epoch11 deployment_review/legacy4_shared3/.
Uploaded Orin candidate root:
`/debug/code/maptr/models/mapod_legacy4_shared3_20261008/`.
Transferred ONNX and validation JSON SHA checks pass; shell syntax check passes;
eight-profile candidate dry run passes, preserving unrelated YAML semantics.
Current installed core SHA d9bd1be1d7b64a84d0d62e46d895ccda8bf40c3935c5b6bf9977fb0f2e497ceb
already contains equality-gated one-fusion reuse. No C++ edits/build needed.

User command in baize_ruicao-wviz-1:
`bash /debug/code/maptr/models/mapod_legacy4_shared3_20261008/build_and_select_legacy4_shared3.sh`.
It builds/smokes ONLY camera.backbone plan in independentbundle, reuses the six
original noncamera model/plugin artifacts byte-for-byte, verifies TRT bindings
and checksums, refuses switching while loader_exe runs, backs up eight profiles,
then applies identical3camera routes and epoch11preprocessing to those profiles.
Does not start playback or compile C++; no automatic agent engine build.
Target bundle: root/build_orin_cuda114_trt8522_fp16.
No engine yet generated, no active profile yet changed, no playback run,
no latency/accuracy result, no commit/push. Current old4camera profile remains.
Expected subsequent timing shared_bev/union_cameras3/fusionpasses1/complete1.
Remote host upload staging retained /tmp/mapod-legacy4-shared3.C0oack.

## Superseding status: strict shared-three source applied

The preceding candidate-only/no-C++-edits status is superseded. User requested
actual Orin source changes, then halted branch organization and requested the
legacy four-layer, three-camera, single-fusion version for user compilation.
No experiment branches were created, no push or agent compilation/playback.

In `/debug/src/perception_q`, current branch remains
`release-test-mapod-share-model-5.8-serial-benchmark`. Changed core
`bevfusion.cpp`/`.hpp` and integrating `dl_bevfusion_mapod.cpp`:
require three shared slots `[0,1,2]`, default camera count3 and matching routes;
TransBBox, serial Anchor3D and parallel Anchor3D all reuse `od_feature` for MAP
and invoke fusion only once. Cross-stream completion dependencies retained.
Source-contract tests3 passed and `git diff --check` passed on Orin; these are
not C++ compilation or runtime tests. Source backup:
`/debug/code/maptr/models/mapod_legacy4_shared3_20261008/code_before_strict_shared3.ANlN2Q/`.

All eight source/active/staged/overlay profiles were staged to legacy4/15,
three shared cameras physicalraw[0,1,6], aligned preprocessing and candidate
bundle `mapod_legacy4_shared3_20261008/build_orin_cuda114_trt8522_fp16`.
Backup `profile_before_shared3_20261008_071739/` under that candidate root.
Camera plan still absent at latest read-only check. User must compile targets
`bevfusion_mapod_core` and `lidar_obj_det`, install the resulting
`libperception_q_bevfusion_mapod_core.so` and
`libperception_q_lidar_obj_det.so` from build/bin to install/lib, then execute
the prepared camera-engine builder/selector before playback. The builder now
checks for the strict three-camera diagnostic in the installed core.
No new latency or accuracy result exists for this candidate yet.

## User playback of legacy4/shared3/single fusion: measured

User supplied host `/data/code/all_ws/ws/ruicao/baize_ruicao/mapod_timing3.log`.
Read-only snapshot1165907bytes, SHA256
`1508c00186211958401ad83148e766fe7f84e0115226f8d2951a15fe7a61d46e`,
verified against remote after transfer. This supersedes the pending-playback
status above:352completeframes, allshared_bev/cameras3/fusionpasses1;
exclude first30,322samples(frames31–352), pointsmedian137631.
FrameIDsunique and PROC_TIME/BENCHMARK counts match352; all metrics have322
postwarmup samples. No MAPOD_OUTPUT or INPUT_GATE records in this capture.

P50/P95ms: MapOD Proc110.037/114.953, core98.594/102.954,
parallelfrontends52.567/60.000, nestedSCN46.911/53.318,
gather.129/1.237, BEVpool1.209/1.333, VTransform2.543/2.856,
singleFuser17.697/19.831, OD/MAPparallelheadregion23.133/28.235,
MAPownstreamhead14.507/20.101, MAPthroughdecode19.411/25.456,
finalMAPCPUdecode.074/.102, pointsprepare3.358/3.530,
cloudassociation7.406/9.940, objectoutput.405/.498.
Overallmedian decreased29.524ms(21.2%) against original4camera/dualfusion;
decreased58.889ms(34.9%) against6layer baseline.
SCN/frontends are currently the largest stage. MAP enqueue CPU40.498ms
contains waiting, not pureMAP computation. Nested/overlapping intervals cannot
be added; noOD-only matched-frame run, so noexactMAPincremental latency.
Newcamera/preprocessing and nonmatched frames preclude isolated fusion
ablation. Four-v-six differ inweights/points/attention/engineprecision;
sixlayerFuser66.149ms vs this17.697ms is major difference, notdecoderalone.
Noaccuracy/finite-output conclusion from filteredtiminglog.
Fullreport local deployment_review/single_fusion/
`timing_legacy4_shared3_all_20261008.md` with all64timingmetrics.
No source/profile changes, build, playback start/stop or push in this analysis.
