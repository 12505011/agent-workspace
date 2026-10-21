# epoch11 deployment to 98 Orin (runtime installation pending)

## Camera audit correction (2026-10-08, deployment not ready)

**Resolved deployment selection, superseding the physical[7,1,6] notes below:**
User explicitly confirmed CAM_FRONT_TOP_MID. Both current dcu-1/dcu-2 recorded
calibrations independently show raw0=front_top_mid, raw1=front_mid_left,
raw6=front_mid_right. Actual dcu-1 camera0 QFILE header confirms camera_0,
LI-VENUS-ISX031-GMSL2-118H, 960x768; calibration is 1920x1536. Runtime source
selects the calibration node and image through the same raw-ID remap.
Changed ONLY MapOD camera_id_remap_vals to [0,1,-1,-1,-1,-1,2,-1] in source79,
active profile, staged79, and all five env0 overlays (8 files). OD and MAP both
keep private route [0,1,2], now physical [0,1,6]; raw7 is ignored.
All YAML parsed and matched their exact previous semantic values except this
one sequence. Backups and SHA report:
`/debug/code/maptr/models/mapod_samearch_joint_epoch11_20261008/camera_top_mid_20261008_053229/`.
Local correction script: deployment_review/correct_top_mid_camera.py. It guards
old remap, raw image dimensions, routes, and recorded calibration locations.
Initial candidate parsing failed before backup/writes; corrected block-sequence
rendering then all8 replacements verified. No calibration file/model/source C++
changes, no build/install/playback, no commit/push in this correction.
User compilation/installation for the earlier opt-in preprocessing modes and
real-data playback remain pending. Historical install_profile.py/deployment
reports describe the initial raw7 deployment, not the corrected current state.

User recalled that the intended middle camera is the front TOP_MID, not MID.
The physical[7,1,6] selection below was carried from an older four-run GT
visualization and is **not a verified deployment contract for epoch11**.
Do not run the candidate profile until physical sources/calibration are resolved.
The saved effective training config uses canonical MID/LEFT/RIGHT slots;
the generators explicitly rename real source channels into these slots.
Current generation contracts and prior audited data notes show MAP old sources
and the 729-frame validation use TOP_MID, while four additional training runs
use MID; OD four-site sources also differ by site. Thus a canonical MID slot
does not prove physical camera7. The Jinke calibration previously audited maps
camera0 to front_top_mid and camera7 to front_mid; this still needs checking
against the actual deployment recording. No remote camera profile was changed
in this correction audit; no compilation or playback was started.

## Authorization and boundary

User authorized installing the previously validated epoch11 MapOD bundle into
98 Orin perception_q/profile, explicitly reserving program execution to them.
Later they reserved compilation to themselves. One agent build had already
finished (exit0) at that point; **no installed library was replaced**, and no
additional build was started. No playback, loader or service was launched.
No Git commit/push or branch switch was performed.

User also explicitly requested stopping every other Orin container. Read-only
enumeration found two other running containers, `qp_tl-wviz-1` and `qpilot-orin`;
both were stopped. Only `baize_ruicao-wviz-1` remains running. Other containers
were already stopped and were untouched. One-minute load declined from6.60 to2.33;
this is a host average, not a model performance measurement. Restart policies
were not modified (stopped containers may return after a daemon/host restart).

## Artifact and profile installation

Container model path:
`/debug/code/maptr/models/mapod_samearch_joint_epoch11_20261008/build_orin_cuda114_trt8522_mixed_validated`.
The22-file SHA256 manifest check passed immediately before configuration changes.
The old `/opt/qomolo/qpilot-resource/perception/model/dl_bevfusion_mapod` bundle
was not overwritten. See EXPORT_EPOCH11_2026-10-08.md for engine numeric gates.

Remote runtime repository remains branch
`release-test-mapod-share-model-5.8-serial-benchmark`, HEADc03af0d0.
Profile repository remains same branch, HEADc40784f. Existing user changes to
79-lidar_preprocess.yaml and79-perception.yaml were backed up and preserved.

Updated source profile:
`/debug/src/perception_q_profile_project/project/cnwxijk/qthd/perception_q/79-perception.yaml`.
Effective profile:
`/etc/qomolo/profile/welldrive/qthd/perception_q/profile.yaml`.
Selected `lidar_obj_det.enabled_pipline=pipline-dl_bevfusion_mapod_cluster`.
Both MapOD routes now use three cameras, physical[7,1,6], private[0,1,2]; raw0
is ignored. MAP decoder6layers,40vectors,20points,7classes. Voxel0.075 (NOT0.1),
anchors match the actual checkpoint config. Existing score gates and unrelated
modules were preserved: OD raw decode0.3, Map0.4, plus pre-existing per-class
OD acceptance gates. These are deployment thresholds, not evaluation metrics.

## Preprocessing fixes, waiting for user build/install

Recorded camera7 qfile header verified raw960x768. Calibration image_size is
1920x1536. Existing runtime had two mismatches with this checkpoint:

- resize_crop produced horizontal crop-122 (centered padding); native training
  validation clamps crop_x to0 (right padding). Added explicit
  `resize_crop_train` mode; configured all three cameras to this mode.
- Calibration scaling applied cy/2-110 for old960x540 semantics. Added opt-in
  `intrinsics_scale_to_raw_image:true`: scale rows of K by raw/calibration image
  dimensions without the110px offset; invalid/missing dimensions fail closed.

Only MapOD algorithm source changed:
`/debug/src/perception_q/src/lidar_obj_det/lidar_obj_det/dl_bevfusion_mapod/dl_bevfusion_mapod.cpp`.
Old default resize_crop, letterbox and intrinsic behavior remain unchanged.
Tests compiled and executed the actual C++ source slices using yaml-cpp, no
GPU/replay. Crop test first failed for missing train mode then passed; intrinsic
test first failed on legacy110 offset then passed. Combined suite passed.
Build log shows exit0, with existing PCL deprecation/macro-redefinition warnings;
do not describe this as warning-free. User must build/install before playback,
since currently installed library does not implement the new opt-in modes.

Installed libraries remain byte-identical to before deployment:

- libperception_q_lidar_obj_det.so SHA256
  c4d2780dc9ed3d0ea02b08914b69540f7157be0dd89def66299f8d84285f7b77
- libperception_q_bevfusion_mapod_core.so SHA256
  19932b89cebde785000089c57bdd76d97db8a3fd11f05fa0a3a794564ea3feba

Playback uses `/debug/install/lib/libperception_q_lidar_obj_det.so`, NOT merely
the build/bin copy. Required middleware/SPCONV dependencies exist under
/opt/qomolo/welldrive; the normal Baize environment setup provides those paths.

## Configuration regeneration trap and scoped solution

Player `/debug/baize_player/qbaize_play.sh` invokes `baize profile debug` for the
bag before running. qprofile selects the FIRST matching module directory from
its search roots, not a per-file merge across all roots. Current first root is
/tmp/qprofile_opt, copied from the bag's .opt snapshot. Updating the ordinary
source79-perception.yaml or only/tmp/qprofile did not affect the generic merge.
This was demonstrated by a generated profile missing the MapOD node.

Added a **MapOD-only** `78-env0-mapod_epoch11.yaml` overlay in these locations:

- source project directory beside79-perception.yaml;
- /tmp/qprofile/welldrive/qthd/perception_q;
- /tmp/qprofile_opt/welldrive/qthd/perception_q;
- /debug/issue/jk_mapod/dcu-1/qprofile/.opt/welldrive/qthd/perception_q;
- /debug/issue/jk_mapod/dcu-2/qprofile/.opt/welldrive/qthd/perception_q.

Original recorded bag YAML files were untouched. Existing playback script/YAML
were untouched. Scoped `qprofile update welldrive/qthd/perception_q` then returned
exit0 and matched all new MapOD settings. Its generic regeneration also changed
unrelated effective values from old bag defaults, so the final effective file
was reconstructed from its exact pre-deployment snapshot with only MapOD and
the selected pipeline changed; semantic equality of every other setting passed.
Later player-triggered full generic regeneration is the player's existing
behavior. The new bag overlays ensure the MapOD selection survives it.
For a different bag/project, carry/review the scoped overlay explicitly.

## Backup and handoff

Container backup:
`/debug/code/maptr/models/mapod_samearch_joint_epoch11_20261008/deployment_20261008_051553`.
Host equivalent starts
`/data/code/all_ws/ws/ruicao/baize_ruicao/code/maptr/models/`.
Contains source/config before images, both installed libraries, complete profile
tar backup, original dirty diff, regression harness/build log/exitcode, JSON
report and created-overlay path manifest. This is outside agent-workspace;
large binaries/config archive were not copied into task notes.

Local inspection/report directory:
`/data/baize/baize-welldriver/code/maptr/work_dirs/onnx_engines/mapod_samearch_joint_epoch11_20261008/deployment_review/`.
Contains scoped candidate source/config, install script, tests and report.
Do not rerun install_profile.py blindly: it intentionally guards existing overlay
creation and source identity. User owns build/install and actual playback.

For rollback, restore the exact backed-up algorithm/source/staged/effective
profile and move the five created overlays out of YAML search directories using
created_overlay_paths.json. Restore backed-up installed libraries only if the
user has since installed new ones. No rollback was executed in this session.

## Remaining acceptance

### User-built single-fusion timing, MAP head cost (2026-10-08)

Full64-metric snapshot report and CSV (n141, same171-frame capture) saved
locally under deployment_review/single_fusion/timing_shared_bev_all_20261008.md
and .csv. Each metric has P50, nearest-rankP95, mean, min, max and count;
includes caller stream, SCN stream, MAP stream, host CPU sections, outer
pre/postprocessing and the per-frame derived MAP-through-decode interval.
No individual Camera-backbone or OD-head GPU measurement exists in this log;
host submit timings must not be used as those GPU costs. Additional tail
caller map.decode_sync_d2h_cpu and map.decode_done sub-timeline refer to
different boundaries and should not be summed together.

User compiled/installed and reported substantially lower latency. Read-only
snapshot /debug/mapod_timing.log565,163bytes,171completeframes, excludes30
warmup frames; n141 frames31–171. All mode=shared_bev, fusion_passes1,
union_cameras3; zero map.fuser_bev_encoder stage records. Installed core SHA
d9bd1be1d7b64a84d0d62e46d895ccda8bf40c3935c5b6bf9977fb0f2e497ceb
differs from the old core. Source fix is now exercised, not merely staged.

P50/P95 ms: core wall157.022/172.071, outer169approx
(proc_total168.926/184.867), one fuser+encoder66.149/67.814,
frontends51.894/57.823, SCN-own-stream46.481/53.120.
MAP-own-stream head interval24.691/37.268. Source places start AFTER upstream
cudaStreamWaitEvent, so this interval excludes that dependency wait, but still
includes submission/idle gaps, not pure GPU kernels. Per-frame sum of adjacent
MAP stream intervals through decode_done yields P50/P95=28.876/42.514;
decode_done also includes host/postprocessing gaps, not pure MAP decode kernel.
MAP host enqueue96.406/113.707 is blocking/submission wall and is NOT isolated
head compute. Combined caller head region31.480/45.939 overlaps these values.

Observed P50 core falls227.601→157.022, outer244.304→168.926 versus previous
73-frame sample, consistent with eliminating~66ms second fuser plus gather/
pool/vtransform; samples/run conditions are not fully controlled and no exact
causal savings or OD-only delta is claimed. MAP head stream interval~25ms,
through-decode interval~29ms; incremental whole-frame cost versus OD-only
requires same-frame/same-engine MAP-disabled control, not subtraction of
nested timings. Current log does not isolate MAP-specific cloud association
or establish output accuracy. No additional config/build/run changes by agent.

### Equal-route single fusion source fix, awaiting user build (2026-10-08)

User authorized the runtime correction after confirming the duplicate fusion.
Modified ONLY Orin runtime `src/dl_runtime/dl_bevfusion_mapod/CUDA-BEVFusion/
src/bevfusion_mapod/bevfusion.cpp`. Ordered nonempty OD/MAP route equality,
with camera enabled, now reuses od_feature for MAP instead of calling
fuse_camera_route again, across TransBBox, serial Anchor3D and parallel
Anchor3D paths. Unequal routes still take their original second fusion call.
Existing OD-consumption event ordering, MAP ready event and both task decode
completion protections remain unchanged. MAP head reads shared BEV through
a const input binding. This is a minimal reuse correction, not a further
head-stream scheduling optimization.

Timer mode now shared_bev/serial_shared_bev with configured_fusion_passes1 for
equal routes; unequal routes retain dual_route/serial_dual_route and2. Shared
mode will retain od.* fusion stage names but omit the second map.* fusion
marks. No YAML, engine, thresholds, model weights or camera mapping changes.

Source-contract unittest checks failed on old source, then both passed locally
and against patched Orin source; git diff --check passes. THESE ARE STATIC
CHECKS, not C++ compilation or CUDA behavior/numerical equivalence tests.
No build/install/playback/stop/commit/push performed. Existing user dirty
dl_bevfusion_mapod.cpp was preserved. Before/after installed library SHA checks
are identical: core19932b89cebde785000089c57bdd76d97db8a3fd11f05fa0a3a794564ea3feba,
algorithm32cf7907d5ae578e337a90d6eaa4d071e34f27a9aec8d9e9a18d6ba2e9c18a94.
User owns compilation/installation and playback; current process still uses
the old installed core. Expect mode=shared_bev, fusion_passes1, no second
map.fuser_bev_encoder stage after user build/install/restart; validate output
parity and new latency separately, do not claim a66ms saving as measured.

Guarded source preimage SHA=d60169db8935a7bbefa3fc39c3fb94e2914b934423caeda8e06fc9ed4c8d0cff;
patched SHA=90b6634cbb730a0d9adb6638c67ebe15fa827037e7ab02577b5bd618e3b96b5b.
Backup/patch/test in container bundle root `single_fusion_fix.406DEp/`;
local copies in deployment_review/single_fusion/. Source is cleanly reversible
with git apply --check --reverse then git apply --reverse on the saved patch,
provided no overlapping edits. No rollback executed. Initial scp directly
into root-owned container backup directory failed without changing source;
transferred via host /tmp/mapod-single-fusion.xI16vH/ and docker cp instead.

### First successful epoch11 component timing sample (2026-10-08)

User subsequently restored image delivery and ran filtered timing capture.
Read-only snapshot `/debug/mapod_timing.log`,370,088bytes,103complete frames;
exclude first30, analyze73 frames31–103. Every benchmark is dual_route,
union_cameras3, configured_fusion_passes2. Active profile selects the validated
mixed bundle, timers true, serial benchmark false, corrected raw[0,1,6].
No playback, stop, build or runtime/config changes by agent in this analysis.

P50/P95 milliseconds: core wall227.601/246.291; outer proc244.304/261.577;
caller-stream frontend54.579/61.497; SCN-own-stream spconv46.125/53.395;
OD fuser+encoder65.974/68.261; MAP fuser+encoder66.125/68.467;
OD BEVPool1.220/1.305, VTransform2.546/3.515;
MAP BEVPool1.217/1.235, VTransform2.540/2.568;
caller-stream combined head region27.432/41.657;
MAP-own-stream enqueue-return interval23.808/37.563;
outer points prepare3.387/3.697, cloud association9.723/17.138,
object output0.394/0.967. SCN is nested in frontend; columns/medians must not
be summed as independent stages. Camera-only backbone and OD-only head GPU
durations are not separately exposed in this log.

Map head host enqueue P50/P95=163.599/179.534 (TRT enqueueV3 itself
163.555/179.490), much larger than its own-stream interval. These host durations
include blocking/submission and must not be reported as pure MAP compute or
proof of CPU-bound execution. Largest measured caller-stream regions are two
fuser+BEVEncoder passes, each~66ms, then frontend~55ms. Existing validated
Fuser/MAP plans use FP32 compute/noTF32 with FP16 bindings for numerical safety;
cannot compare directly with historical FP16/single-route latency or switch
precision/skip a route without parity validation. Successful inference does
not establish real-data accuracy, output finiteness or completion beyond the
captured103frames. User visual/output acceptance remains separate.

### Existing component timers enabled (2026-10-08)

User requested a breakdown after observing outer dl_bevfusion_mapod239.289248ms.
Read-only source/BENCHMARK.md and installed-library strings confirm existing
MAPOD_STAGE/SCN_STAGE/MAP_STAGE/CPU_SPLIT/PROC_TIME instrumentation. Active timers
were false. Enabled enable_timer and enable_detailed_timer in the same8 source,
active, staged and bag-overlay profiles; all semantic values other than these
two flags stayed identical, including raw[0,1,6] remap and parallel scheduling.
Backup/report: bundle root/component_timers_20261008_053655/.
No compile, library installation, playback, service restart or scheduling change.
No new measured component numbers yet: user must rerun with filtered log capture.
Existing camera frontend groups normalize/depth/backbone; fuser+BEV encoder is
one bundled plan. Runtime still performs two route fusion passes even when
routes match, as confirmed by forward_timer hardcoding configured_fusion_passes2
and separate route calls; not optimized in this measurement setup. Timers are
nested/non-additive and perturb timing; skip first30 complete frames and report
P50/P95, separating host wall from stream intervals. Local deployment_review
enable_component_timers.py is guarded against concurrent/unexpected state.

### User playback blocked before model inference (2026-10-08)

Latest captured playback `/debug/mapod_input.log` (05:54:37–05:54:56 UTC,
4,234,111 bytes) gets beyond pipeline creation, unlike the earlier VPI load
failure below. All four raw camera pipelines0/1/6/7 were constructed; node
subscribes camera_0 through camera_7. Log contains388 instances of
`player_util.cpp:2127 size is wrong,64768960`. Required camera0/1/6 remain
null/no-data throughout the observed detection frames. MapOD reports
`skip: insufficient_images; site=1 images=0 ids=0 required=3`, and there are
zero MAPOD_STAGE records. This run provides no model component latency.
Failure is isolated upstream to player image delivery; exact buffer/caps
interpretation requires player callback/source inspection. Do not interpret
the concatenated error suffix64768960 as a verified byte count, and do not
claim an engine failure or disable undistortion without checking geometry.
No config/library changes, playback or compilation performed for this audit.

User supplied startup log: player init fails72 because no element vpiconvert;
no component timings were collected. Read-only inspection of current player YAML
shows camera_undistort=true (earlier observed false); no agent change to this flag.
Plugin exists at utility/drivers/lib/libvpiconvert.so. Tight direct load probe
`gst-inspect-1.0 <absolute plugin path>` reproduces failure independently of
playback: cupva2.3 libcupva_host.so.2.3 has unresolved
PvaProgramSetDMADescriptorsV2. ldd links VPI2.3.9, CUPVA2.3 and Tegra
libnvpvaintf/libnvpvaumd. Therefore not simply a missing plugin file/path;
dependency symbol compatibility/loading remains the root investigation target.
EGL and optional DeepStream warnings also occur, but missing vpiconvert is the
observed fatal player error. No library/config changes or replay performed.
Do not turn off undistortion as an unreported workaround: this changes image
geometry relative to associated intrinsics and affects accuracy comparability.

User build/install, real-data sparse-runtime execution, full OD/MAP projection
and production latency remain unvalidated. Five dense-engine numeric gates do
not substitute for those checks. Current runtime still executes a second fuser
pass even when both routes are equal; no scheduling/latency optimization was
attempted during this deployment. This duplicates compute, not model inputs.
