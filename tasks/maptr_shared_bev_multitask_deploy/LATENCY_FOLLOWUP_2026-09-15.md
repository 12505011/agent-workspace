# MapOD latency follow-up after parallel runtime deployment

## Scope and evidence limits

On 2026-09-15, the user reported that latency remained high after the runtime
parallelization. This investigation inspected local source, Orin installation,
existing benchmark artifacts and instantaneous host/container load. It did not
change runtime code, profiles, playback scripts or running services, and did not
launch another playback/engine benchmark.

Runtime source: `perception_q`, branch `release-test-mapod-share-model-5.7`,
commit `d39a0ecd1` (`perf: parallelize MapOD runtime branches and heads`).
Task notes remain on `task/maptr_shared_bev_multitask_deploy`.

Orin checks at approximately 00:19-00:25 UTC / 08:19-08:25 Asia/Shanghai:

- Container: `baize_ruicao-wviz-1`. `/debug/src/perception_q` is at `d39a0ecd1`.
- Installed `/debug/install/lib/libperception_q_bevfusion_mapod_core.so` contains
  `parallel_lidar_camera_frontends` and
  `od.head_postprocess_parallel_map_head`. The parallel implementation reached
  the installed library. This does not prove which library an earlier process
  loaded; no MapOD `loader_exe` was running at inspection time.
- The most recently generated profile at
  `/tmp/baize_workspace_profile_cnwxijk_qthd/perception_q/profile.yaml` has
  `benchmark_single_bev: true`, `enable_timer: false`, `precision: fp16`,
  `num_camera: 4`, OD indices `[0,1,2]`, Map indices `[3,1,2]`.
- `/tmp/mapod_single_bev_timing.log` was last modified on September 14 at
  16:23 UTC, before the parallel library build. It must not be presented as a
  measurement of `d39a0ecd1`. No newer per-stage capture was found in the
  inspected locations.
- Two `docker stats --no-stream` samples showed `qpilot-orin` consuming
  594.59% and 573.19% CPU, while `baize_ruicao-wviz-1` was about 0.01%.
  There are eight online CPUs (`0-7`). Docker's percentages correspond to
  approximately 5.7-5.9 fully busy cores, not 594% of the whole machine.
- Two one-second `tegrastats` samples showed roughly 56-93% per-core load,
  CPU frequencies 2188 MHz, GPU utilization 0%, CPU temperature about 57 C
  and GPU temperature about 52.5 C. `nvpmodel -q` reported MAXN, with an EMC
  permission warning; full clock verification was unavailable without root.

The competing CPU load is a confirmed current condition and a strong
candidate for submission/NMS latency and tail variance. Its effect during
the user's latest playback is not measured. Do not stop or reconfigure the
other container without establishing that it is safe and authorized.

## Existing standalone TensorRT evidence

These are September 14 measurements, not fresh parallel-playback results.
Files reside in the Orin container at
`/debug/code/maptr/work_dirs/onnx_engines/mapod_latency_9nIvLE/`.

| Engine | GPU compute median | Host enqueue median | Source |
| --- | ---: | ---: | --- |
| Camera backbone | 14.1682 ms | 0.9128 ms | `camera.backbone.timing.log` |
| Camera VTransform | 2.4937 ms | 0.1255 ms | `camera.vtransform.timing.log` |
| Fuser + BEV encoder | 17.5714 ms | 1.9064 ms | `fuser.timing.log` |
| Anchor3D head | 2.6194 ms | 0.1777 ms | `anchorhead.bbox.timing.log` |
| Map decoder head | 6.8153 ms | 6.8108 ms | `maptr_decoder_head.timing.log` |

Map's timing log explicitly warns about enqueue-bound throughput. Comparable
host enqueue and GPU intervals can reflect CPU submission cost or internal
synchronization; a CUDA/Nsight timeline is needed to distinguish them. The
existing `maptr_decoder_head.profile.json` has 369 named layer entries.

The fuser profile sums to 17.7580 ms of average layer time. A disjoint
classification by layer name gives:

| Layer-name category | Sum of average layer times |
| --- | ---: |
| Convolutions | 8.2288 ms |
| Reformatting copies | 4.0738 ms |
| InstanceNormalization | 2.5076 ms |
| Affine/activation or fused elementwise entries | 2.4693 ms |
| Other | 0.4785 ms |

This is descriptive grouping, not a prediction that any category can be
removed. The fuser ONNX contains 14 InstanceNormalization nodes surrounded by
reshape/affine operations implementing trained GroupNorm. In particular, do
not attribute all 6.58 ms of normalization plus reformats to GN itself.

The four `ms_deform_attn` plugin layers and associated reformat entries total
about 0.3104 ms in the standalone Map profile. The plugin supports FP32 at its
TensorRT interface despite half templates in the CUDA launcher. FP16 plugin
support is possible future work, but this profile does not justify making it
the first optimization. It cannot explain tens of milliseconds on its own.

## What the parallel commit still leaves on the critical path

### 1. Multiple CUDA streams still share one CPU submission thread

`bevfusion_mapod/bevfusion.cpp:409` calls `launch_maptr()` before submitting OD
conversion/decode/postprocess at lines 414-417. `launch_maptr()` invokes the
TensorRT enqueue call synchronously on the calling CPU thread. If enqueue
itself takes several milliseconds or waits internally, that CPU thread has
not yet submitted the OD postprocess. Separate streams permit GPU overlap;
they do not guarantee it or eliminate this host dependency.

The dual-route compatibility path also intentionally waits for OD consumption
of the reusable fuser output before overwriting it with Map features. Retain
that lifetime protection. The current single-BEV override skips this second
route, but still pools OD's three-camera subset; it is not a newly trained,
accuracy-valid four-camera fusion model.

### 2. Camera BEVPool/VTransform still wait for LiDAR unnecessarily

`run_parallel_frontends()` joins both encoder streams before
`fuse_camera_route()` performs gather, camera BEVPool, VTransform and fusion.
Gather/pooling/VTransform depend on camera output and static geometry, not on
the SCN feature. They can be submitted on the camera route stream before the
LiDAR join; only fusion must wait for both modalities. In the old single-route
timing, this camera-only work was approximately 3-4 ms. Actual savings depend
on GPU resource availability; this is an incremental improvement, not a cure
for the whole 120-240 ms interval.

### 3. Point association performs substantial unused work

Verified call chain:

- `lidar_obj_det/.../dl_bevfusion_mapod.cpp:2061` copies the full point cloud
  into `pc_ptr_hdmap`, then calls `HdmapFilter::Proc`.
- `lidar_obj_det/hdmap_filter/hdmap_filter.cu:138` resizes output indices to
  768,000 entries for every call, although the historical input has about
  137,000 points; it uploads the point cloud and polygon arrays with blocking
  copies and uses the default CUDA stream.
- Lines 176, 190 and 196 call `cudaDeviceSynchronize`, waiting for other
  streams in the same process/device context as well.
- It downloads 768,000 indices, then runs `deletePoints`, downloads a count
  and downloads/resizes a filtered point cloud (lines 199-209).
- MapOD uses the indices to attach points from the original cloud to objects.
  It never consumes the filtered `pc_ptr_hdmap` after this call.

The deletion/filtered-cloud download is therefore unnecessary for this caller.
A MapOD-private association implementation can return only point-to-box
indices, reuse device/pinned buffers and transfer only the actual point
count. Preserve first-matching-box priority, `tag == 255` handling, rotated
box expansion, coordinate precision and polygon semantics. Existing shared
HdmapFilter and `dl_bevfusion` behavior must not change.

Object cloud accumulation and polygon reconstruction remain CPU work after
association; measure them separately. Replacing polygons with rectangular
boxes would change downstream behavior and is not an equivalent optimization.

### 4. OD postprocess remains more than its pinned D2H copy

The current profile has 180x180 cells, 20 anchors and 10 classes:
648,000 anchor candidates. `head-anchor3d.cu:157` converts all three dense
half outputs to float. `postprocess.cpp:354` scores/sorts all anchors, decodes
the top 2,000 and runs class-wise rotated CPU NMS.

Candidates: read half outputs directly for scoring, convert/decode only
selected candidates, replace full sort with an equivalent top-K algorithm
where profitable, and evaluate GPU rotated NMS. Preserve class-wise NMS,
score ordering/ties, angle convention and thresholds. The standard axis-aligned
TensorRT EfficientNMS plugin is not a drop-in equivalent for rotated BEV NMS.
Lazy allocation in the getters affects warmup; it does not explain every
steady-state frame after the buffers exist.

### 5. SCN computation and dynamic voxel-count synchronization remain

The old combined SCN stage had median 51.5 ms; it included GPU work, host
submission gaps and waits. It is not an isolated sparse-kernel benchmark.
Current source still:

- clears a 25.6 MB voxel-temporary buffer every frame by memset
  (the buffer is allocated once at initialization);
- uses a 4.8 MB maximum-capacity hash buffer;
- synchronizes the LiDAR stream for the CPU-readable voxel count;
- invokes the prebuilt spconv engine after voxelization.

Split measurements into clear/hash/scatter/count wait/reduce/spconv before
choosing a rewrite. The count copy is queued before scatter, so an event just
after that copy may let CPU submission proceed without waiting for scatter;
the same LiDAR stream still enforces scatter/reduce/SCN data dependencies.
Do not simply remove synchronization when the CPU immediately reads the count.

The exported sparse graph has 21 SparseConvolution nodes and takes the FP16
parser path. INT8 needs valid weight/activation scales and compatible runtime
support, not just `precision: int8`. Coarser voxels, reduced spatial range or
narrower channels change the model and require training/export validation.

Before lowering `max_voxels`, fix capacity handling: scatter discards voxel
IDs beyond capacity, but the current returned voxel count is not clamped
before reduce/SCN. The zero-voxel fallback also lacks a valid initialized
feature/index. These are correctness hazards for capacity/pruning experiments,
not established causes of the current latency report.

## Recommended next sequence

| Priority | Work | Expected benefit and validation |
| --- | --- | --- |
| P0 | Record the parallel baseline with `enable_timer: true`; compare controlled CPU load and normal production load | Separate actual overlap, CPU starvation and structural cost; record P50/P95 on the same clip |
| P1 | MapOD-only indices-only point association | Remove verified unused filtering, copies and same-context device-wide waits; no model/engine change |
| P2 | Test CUDA Graph on the static Map engine; split OD GPU submission from CPU collection | Reduce host dispatch gaps; submit OD GPU decode before entering a potentially expensive Map enqueue; capture compatibility must be measured |
| P3 | Move camera gather/BEVPool/VTransform before the LiDAR join | Extend useful overlap without changing feature values; validate event/buffer ownership |
| P4 | Split SCN profiling and optimize the measured dominant section | Active voxel statistics, buffer clear, count synchronization, rulebook/sparse kernels; do not assume all 50 ms is convolution |
| P5 | Half-native OD top-K/decode and class-wise rotated GPU NMS | Reduce dense conversion bandwidth and CPU work; compare exact candidates and final boxes |
| P6 | Fused GN/affine/activation and layout-aware fuser export/build | Target the measured normalization/reformat overhead; retain trained GN semantics; rebuild and compare outputs |
| Model change | Calibrated sparse INT8 or smaller SCN/BEV architecture | Needed if measured intrinsic compute remains above the target; independently evaluate accuracy |

P1 is the strongest concrete runtime simplification found in this review. P2
has a useful standalone enqueue signal. Both can be pursued without changing
the trained architecture. Scope any association/kernel changes to MapOD.

CUDA Graph should first cover the static Map TensorRT engine with fixed
addresses and an initialized context. Keep dynamic SCN/CPU voxel-count reads
outside capture. If capture fails, retain normal execution and inspect the
reason. Do not introduce a new CPU worker thread by default while most CPU
cores are already occupied; use profiling to justify a persistent, independently
owned submission thread if it is still needed after graph optimization.

GN is input-dependent and cannot be folded into Conv like frozen BN. A fused
GN plugin can preserve its math, with tolerances verified; reverting GN to BN
only to reduce latency would reintroduce the training/normalization issue.
Current four decoder layers are sequential refinement stages; exporting only
final outputs may prune unused auxiliary outputs, but cannot remove the
earlier layers/reference refinements required for the final prediction.

## Measurement protocol and latency expectations

Use the same model bundle, clip, thresholds, playback speed, camera routes and
power configuration for each comparison. After 30 successful warmup frames,
collect at least 200 complete calls and report core/process P50/P95 plus output
counts. Current three source-string tests prove neither GPU overlap nor speed.
The current timer combines branches; Nsight Systems CUDA/OS-runtime tracing
or stream-specific events are needed for actual branch overlap and CPU waits.

With timing enabled in the maintained profile and confirmed in the generated
profile, the user can capture existing playback output without modifying the
launcher:

```bash
cd /debug/baize_player
bash qbaize_play.sh 2>&1 \
  | grep -E --line-buffered 'MAPOD_BENCHMARK|MAPOD_STAGE|MAPOD_PROC_TIME|MAPOD_INPUT_GATE|MAPOD_OUTPUT' \
  | tee /tmp/mapod_parallel_followup_20260915.log
```

Filtering before tee reduces disk/terminal volume but does not suppress
producer-side log construction. `dl_bevfusion_mapod.cpp:1921` constructs all
box-detail strings unconditionally; a producer-side debug gate is an additional
low-risk candidate if profiling shows logging cost.

Rough budgeting, not a new benchmark: a roughly 50 ms SCN path plus roughly
18 ms fuser leaves very little of a 60-80 ms whole-process budget for heads,
association and other work, even with complete camera overlap. Measure
intrinsic SCN cost before promising that target. The old observed 93.2 ms
minimum/143.0 ms median core are measurements of the old schedule, not a
physical lower bound for optimized code. Do not add medians from overlapping
stages or subtract host and stream columns to claim saved milliseconds.

Cross-frame pipelining can increase throughput without reducing single-frame
latency. Latest-frame queues/decoupled Map publication can reduce data age or
OD waiting, but change scheduling/product behavior. They require explicit
evaluation and are not the first proposed fix. `map_instances=0` in old logs
still prevents treating those runs as correctness acceptance or representative
Map publication cost.

## Primary reference

[NVIDIA TensorRT performance optimization](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/optimization.html#inference-with-cuda-graphs)
explains CUDA Graph capture, fixed context/buffer requirements and multi-stream
resource contention. Use it for these principles; verify concrete APIs and
capture behavior against the installed TensorRT 8.5.2.2. No TensorRT/JetPack
upgrade is proposed by this note.

## User-authorized Orin load cleanup, 2026-09-15

After the analysis, the user explicitly requested stopping unnecessary load
so they could rerun playback themselves. At 00:31-00:32 UTC, `qpilot-orin`
still consumed 583.45% CPU. Supervisor status and recent logs confirmed that
six programs repeatedly exited with status 1 and restarted every roughly
1-2 seconds. Their logs reported missing `/debug/subway/install` setup files
and missing ROS packages, including `img_postprocess`, `alarm_agent`,
`ground_filter`, `ground_filter_livox`, `innovusion`, and `lidar_undistort`.

Stopped only these six Supervisor programs using the existing supervisor:

```bash
docker exec qpilot-orin supervisorctl stop \
  img_postprocess launch_alarmagent launch_groundfilter \
  launch_groundfilterlivox launch_iv_driver launch_lidarundistort
```

The command succeeded and all six remained `STOPPED` on a subsequent check.
No container was stopped/deleted. The existing `qp3_105to106` program and
previously exited `launch_livox_driver` were left unchanged. All other
containers, SSH sessions, Docker, editor processes, model files, profiles,
playback scripts and autostart configuration were preserved. No new playback
was launched by the agent.

At 00:33 UTC, two post-cleanup Docker samples showed `qpilot-orin` at 0.03%
and 0.02% CPU and `baize_ruicao-wviz-1` at 0.00-0.01%. The last two of three
one-second tegrastats samples showed 0-2% utilization on each CPU core and
0% GPU utilization. This verifies removal of the competing restart-loop CPU
load, not a measured MapOD inference speedup. Playback latency after cleanup
remains for the user to measure.

This is a temporary operational stop, not a repair of the missing packages.
Restarting Supervisor/container can launch the failed services again because
their configuration was deliberately not changed. For a future restoration,
first repair the missing installation or confirm that restarting is intended,
then use the same six explicit program names with `supervisorctl start`.
Do not use `start all`, global process killing, or container deletion for
this cleanup.
