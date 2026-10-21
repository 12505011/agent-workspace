# Six-decoder MapOD FP16 latency-only recipe and measured playback

User explicitly requested precision alignment and latency only, without effect/
accuracy acceptance. This supersedes prior numerical-acceptance gating for THIS
experimental candidate, not the acceptance status of production artifacts.
No C++ compile or playback by agent; no engine build started in preparation.
User runs Orin build per current division of labor.

Prepared script on Orin:
`/debug/code/maptr/models/mapod_samearch_joint_epoch11_20261008/prepare_fp16_latency.py`.
Local source under epoch11 artifact `deployment_review/` together with
`test_fp16_latency.py`. Tests first failed before implementation, then passed
locally and on Orin (2tests). Dry-run preflight on actual8profiles passed.
Source ONNX SHA checked; source engine manifest hashes verified; source five
dense plan interfaces cross-checked on target. No active loader/build observed.

User command: `python3 prepare_fp16_latency.py --build-and-select` in the
epoch11 root. Default WITHOUT flag only does read-only preflight.
New independent output `build_orin_cuda114_trt8522_fp16_latency_only` does not
exist yet. Existing mixed-validated and legacy4 models are not overwritten.

Recipe builds ONLY fuser and standard-op MAP from existing validated-standard
ONNX with --fp16 --noTF32, FP16 external bindings, detailed inspection.
No FP32 layer constraints or weight/graph changes. TRT may retain FP32 layers;
actual layer-format report is retained, not assumed pureFP16 from bindings.
Fuser ONNX SHA a278f55c18bcda6cd18042c9d7b55de2c64ef91d8fcf4a69ba6f35cc81ae3e0c.
MAP ONNX SHA dc82960bfa7dda1660b040489057abb821bacfc8b7fa3a90a53fac17dba25d74.
Preserves epoch11sixlayers/20points,40vectors,7classes,voxel.075. Reuses existing
FP16 Camera/VTransform/AnchorOD engines, sparseLiDAR ONNX and targetplugin.
Fuser/MAP build+smoke true exitcodes and full logs retained. Deserialization,
allfivebinding shapes/dtypes and short inference must succeed before selection.
No numerical parity/finite output/accuracy gate is asserted, as requested.
Candidate README/manifest marked LATENCY ONLY, NOT production/accuracy accepted.

After successful builds and checks, script restores exact six-layer baseline
MapOD params (only new model_path plus timers), raw[0,1,6], private[0,1,2],
shared3/singlefusion/parallelproduction, and MapOD pipeline in8profiles.
Other module semantics remain identical; profiles compare-and-swap guarded
against changes during build, timestamp backup and rollback of own writes.
No premature profile switch while engine absent. Current selection remains
original third-party OD until user executes successfully.

Prior default custom-plugin FP16 MAP showedNaN, so do not infer accuracy from
build/smoke success. This candidate keeps the independently verified standard
MAP graph; precision is the intended change versus previous6layer baseline.
Six-versus-four still differ inpointcount/weights/attention architecture, so
it is not a strict decoder-depth-only ablation. Invalid predictions may also
change CPU postprocess work; report stage-level and end-to-end separately.

## User build succeeded; plugin registration fix and safe resume

User executed recipe: Fuser and standard6layer MAP build exit0, bothplans
present. Python validation then failed at Fuser deserialization because the
script omitted `trt.init_libnvinfer_plugins(logger, '')`. FuserFP16 graph builds
InstanceNormalization_22...165 as built-in TRT PLUGIN_V2 layers. This is not
an engine-build failure or a missing custom MAP shared object.

Read-only target reproducer: unregistered Fuser fails exact creator error;
after built-inplugin registration the SAME Fuser101layers and MAP21layers both
deserialize successfully. C++ runtime `mapod_common/tensorrt.cpp:133` already
calls initLibNvInferPlugins; no C++ edits or recompilation required.

Fixed and uploaded prepare_fp16_latency.py, retaining oldscript as
`prepare_fp16_latency.before_plugin_fix.py`. Added --resume: checks bothbuild
exitcodes0, nonemptyplans, exact matchingbuildcommands and trtexecPASSED before
reusing. Existing copied baselinefiles requireSHAidentity, notoverwrite.
Resume still validates sourcegraphs and baselineplan hashes, and performs
fresh profile preimage checks; no inference/selection during dryrun.
New resume+real targetplugin regressiontests firstRED thenGREEN.
Local4tests:3pass/1targetskip; Orin4testsPASS with existingTRTAPIdeprecation
warnings. Actual --resume dryrun PASS. No smoke inference, profile switch,
playback, engine rebuild or C++ compile was performed by agent in this fix.

User continuation: `python3 prepare_fp16_latency.py --resume --build-and-select`.
This skips engine rebuilds, finishes five smokechecks/metadata and switches
eightprofiles ONLY after checks. Accuracy gate remains intentionally waived
for this latency-only candidate. Candidate is not yet selected.

User also asked about per-task frequencies. Explained feasibility only; no
scheduling implementation authorized or changed. Existing Core waits for MAP
results each call. OD everysharedBEV frame + MAP everyNframes can avoid head
computation on skippedframes, not sharedfrontends/Fuser cost. Publish-only
throttling saves no enginework. NonblockingOD publication while MAP executes
needs independentresultpublication, protectedBEVbuffers/events and true input
timestamps; actual achievableHz depends on measuredworkload, not just settings.

## User completed selection and playback; measured result

Supersedes earlier pending-state paragraphs. User resumed: allfive smokechecks
exit0, profile backup `profile_before_fp16_latency_20261008_082934`, selection
READY. Read-only activeprofile check confirms candidatepath, raw[0,1,6],
sharedprivate[0,1,2], MapOD pipeline and parallelproduction. Inspected MAP
layerformats still include twoFP32 outputs; do not label allcompute pureFP16.

User playback `/debug/mapod_timing4.log`: stable remote/local SHA256
`a6c012a6f538f06f5791886985f52a59b672ff7e6d9afcf7e88222b6c51cadbb`,
1319682bytes,398completeframes and398PROCs. Skip30:368samples31–398.
Allframes shared_bev/3cameras/1fusion/complete1; ALL398haveMAP enqueue,
so no MAP inference downsampling demonstrated. No errorstrings captured;
filteredlog lacksstartupenginepath and numerical outputverification.

P50/P95ms: algorithm113.976/119.470, Core102.548/107.146,
frontends52.984/59.895, nestedSCN46.822/53.316,
Fuser17.668/20.119, MAPownstream17.174/24.655,
MAPthroughdecode21.999/29.228. Overall vs sixlayer mixedbaseline
168.926 saves54.950ms/32.53%; Fuser66.149->17.668 is largestchange.
Old4layer shared3 overall110.037 vs current113.976(+3.939ms),
MAP14.507 vs17.174(+2.667ms); not a depth-only ablation.
No sameframeODonlycontrol: cannot assert exactMAP addedwalltime.
Detailed localreport `deployment_review/single_fusion/timing_six6_fp16_20261008.md`
under epoch11 ONNX/engine artifact. No compilation/build/playback/statechange
by agent. Accuracy remains intentionally NOTaccepted for latencycandidate.
