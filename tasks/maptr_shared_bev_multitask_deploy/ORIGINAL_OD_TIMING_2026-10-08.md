# Original Orin OD model: selected, awaiting user playback

User clarified testing the old third-party OD model already on Orin, not our
MapOD checkpoint with MAP disabled. Six-layer FP16 rebuild was paused; no new
FP16 candidate, build, source changes, playback or service start/stop.

Original model directory:
`/opt/qomolo/qpilot-resource/perception/model/dl_bev_qthd_cnwxijk`.
Existing source/active/original bag `dl_bevfusion.params` agree exactly:
site_name=qthd_cnwxijk, Anchor3DHead11classes/22anchors, voxel.075/.075/.2,
score_thresh.5/nms.1, original identity camera remap. The dense fusion camera
engine is fixed5cameras; preserve its native configuration, do not force3.
Both fused and separate LiDAR-only models are present, all8 files nonempty.
Six dense engines deserialize on TRT8.5.2, all bindings FP16, validated by
read-only engine inspection without inference.

Actual detailed engine inspector results (not just binding inference):
- camera.backbone85layers, camera.vtransform5layers, fusion AnchorOD10layers:
  all inspected tensor formats FP16.
- fuser20layers: predominantly FP16, final Conv_27+Relu_28 FP32 tensor formats,
  surrounded by FP16/FP32 reformat. Not whole-network FP32 or pureFP16.
- LiDAR fuser20layers: predominantly FP16, final Conv_24+Relu_25 FP32.
- LiDAR-only Anchor head8layers: floating conv/output path FP32 internally,
  with FP16 external bindings.
Layer tensor formats do not specify internal accumulator precision.

Scoped selector `select_original_od.py` saved under local epoch11 artifact
deployment_review and Orin legacy4/shared3 root. Dry run passed, verifies all
three original bag/staged79-env0 configs agree with current originalOD params.
Applied only `perception_q.lidar_obj_det.enabled_pipline` in8 source/active/
staged/bag-overlay profiles: `pipline-dl_bevfusion_mapod_cluster` ->
`pipline-dl_bevfusion_cluster`. Exact semantic equality outside this one scalar
verified; original OD/MapOD params, model files and libraries untouched.
All8 post-application YAML checks and profile repo diff check passed.
Timestamped backup/report under legacy4 root `profile_before_original_od_*`.
No loader was running at guarded selection; playback remains user's action.

Legacy Proc falls back to lidar-only when input/mapped images<5, emits
`Cameras is not enough, using lidar only mode.` Model startup uses `dl_bev`
domain, emits `bevfusion models: fusion_enabled=... site_name=...` and paths.
Must capture these logs with per-step `dl_bevfusion` timings, not MAPOD-only
grep. Legacy source sets core timer false, so no guaranteed component-level
breakdown from this unmodified model. Timing comparison is different weights,
classes,5vs3cameras, thresholds and possible fallback; not isolated MAP delta.
No measured latency/accuracy result for originalOD yet.

## First user OD playback: fallback confirmed

Read `/debug/od_timing.log` in one read-only Python snapshot434508bytes,
SHA256 `cc23be16eadf27ac1f6ad4e0ae2e7cccbc34f65703ada570032119c8b5cf4dc4`.
Startupfusion_enabled1 is capability, NOT per-frame execution mode. Actual
logged calls show `No enough images to process. Need5,got0/2/3/4`487times
(0:2,2:1,3:7,4:477), and lidar-only fallback warning5times (rate-limited).
SourceProc setslidar_onlytrue and passes nullptr camera_images; Coreforward
selectsforward_lidar_only, using separate `.lidar` sparse/Fuser/Anchor models.
Thus this run is LiDAR-only, not five-camera or three-camera fusedOD.
Vectorimagecount4 does not prove four unique camera sources; IDs not recorded.

480 captured step0dl_bevfusion timing rows, exclude first30 ->450samples:
P50 89.49264ms, P95 96.137632ms, mean89.28526ms. Logged output calls return
boxes (example57); no create_corefailed/CUDAerror/FATAL/Aborted in filtered
snapshot. Timings/call/overall counts differ; do not label480 as a completed
dataset or exact fullpipeline frame count. No independent component timer.
Cannot deriveMAP incremental cost from this differentmodel/LiDAR-only run.

Immediately subsequent user playback overwrote the same od_timing.log while
scp was being attempted; local transfer was only163bytes with no timing rows. Originalhash/stats refer
only to the earlier atomic read, not the newly reset file. Do not reuse this
path as immutable evidence; futurecapture must use distinct log names or
download after recording has stopped. No processes stopped by agent.

## Second overwritten OD log: steady phase is five-camera fusion

User explicitly requested reanalysis of the overwritten log. New360884byte
snapshot SHA256 `ac264856da94ea61915aecabe4487992ced3ff05fe390be0e1888b48c8a7c62a`,
local `deployment_review/single_fusion/od_timing_second_20261008.log`.
258 loggedcalls,256 bboxreturns,251parsablestep0timings; exclude first30
CALL blocks ->223paired step0/pipeline timing samples. Finalcall incomplete.
Step0 P50/P95/mean122.382/127.271/122.193ms; matched overall149.530/155.810/
149.381ms. All227 available postwarmup overallrows P50149.610ms (sameP95).

Crucial: only initialcalls2–4 fallback(got0/0/4). Call5onward loads five
rawcameras[7,6,1,3,4] mapped[0,5,2,3,4]; all228postwarmupcalls have exactly
these loadrecords and NO insufficient-image gate. Steady measuredrun is old
fusedOD, not LiDAR-only. This supersedes the previous run's mode but not its
correctly dated LiDAR-only measurements. Raw0notincluded in old route.
Step0+32.890ms vs first89.493ms reflects different execution paths, not
evidence of regression. Different model/class/input/postprocess prevents
subtracting it from MapOD110.037ms to inferMAPincremental latency.
No independent GPU component timers; all postwarmup227recorded bboxreturns
nonzero(count55–58), not anaccuracyclaim. Full localreport
`timing_original_od_second_20261008.md`. No config/source/process changes.
