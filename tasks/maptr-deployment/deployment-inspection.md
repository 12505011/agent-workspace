# MapTR deployment inspection

Verified on 2026-08-13 from the `perception_q` source tree and the
`cnwxijk/qthd` profile. This is an inspection record, not a claim that every
vehicle profile uses these exact values.

## Runtime topology

`dl_bevfusion_maptr` is a standalone Baize module, separate from the original
`dl_bevfusion` object-detection step.

1. `MapTRNode` reads `perception_q.dl_bevfusion_maptr.enabled`, runs a
   calibration preflight, and creates a `dl_bevfusion_maptr` algorithm object.
2. It subscribes to `camera_0` through `camera_7`, caches their latest frames,
   and uses `obstacle_pointcloud` only as the inference trigger and source of
   output timestamp/frame id.
3. It validates the required raw camera set, builds a frame dictionary, then
   calls `PreProc`, `Proc`, and `PostProc`.
4. `Proc` selects images in logical `camera_order`, runs the camera backbone,
   depth/BEV encoder and MapTR decoder, and stores vector results in
   `frame_data["maptr_instances"]`.
5. `BuildMapTRPointCloud` resamples every predicted polyline at roughly 0.1 m
   and publishes `maptr_pointcloud` as `PointCloud2`.

The node deliberately serializes inference with a try-lock. A trigger received
while the prior inference is executing is dropped rather than queued.

## Model artefacts and loading order

The model root is `perception_q.dl_bevfusion_maptr.params.maptr_model_path`.
Unless overridden in the nested `maptr` YAML, the runtime resolves the
following relative filenames:

```text
camera.backbone.plan
maptr.depthnet.plan
maptr.vtransform.plan
maptr_decoder_head.plan
libmaptr_plugins.so
```

The plugin is loaded via `dlopen(..., RTLD_NOW | RTLD_GLOBAL)` before the
decoder TensorRT engine is parsed. A missing/incompatible plugin therefore
prevents decoder initialization; it is not optional for engines containing the
MapTR `ms_deform_attn` layer.

TensorRT plans must match the target CUDA/TensorRT/GPU environment and the
profile's input and decoder geometry. Do not mix the above MapTR plans with
the independent LiDAR OD plans used by `dl_bevfusion`.

## Active profile observed

Profile source:
`/data/baize/baize-welldriver/src/profile_project/project/cnwxijk/qthd/perception_q/79-perception.yaml`

| Contract item | Observed value |
| --- | --- |
| enabled | `true` |
| model root | `/opt/qomolo/qpilot-resource/perception/model/dl_maptr_30` |
| physical -> logical ids | `0->0`, `1->2`, `6->5`; others disabled |
| model camera order | `[0, 2, 5]` |
| number of cameras | `3` |
| Player source after undistortion | `1400 x 1000` |
| ROI restored for MapTR | `(220, 116, 960, 768)` |
| raw model stream | `960 x 768`, BGR converted to RGB |
| network input | `640 x 352` after `resize_scale=0.6666667` and `crop_y=160` |
| BEV / decoder | pool `50 x 33`, decoder BEV `17 x 25`, 4 decoder layers |
| query/point/class limits | 40 vectors, 15 points/vector, 6 classes, score 0.4 |

## Deployment invariants

- `maptr.num_camera` must exactly equal `maptr.camera_order.size()` and cannot
  be empty.
- Every logical camera in `camera_order` must resolve through
  `camera_id_remap` to a calibrated physical camera. Calibration comes from
  `/etc/qomolo/profile/calibration/profile.yaml`.
- Raw image size, Player-undistortion ROI, `resize_scale`, crop, camera order,
  BEV geometry and decoder dimensions must match the exported engines.
- The module can consume device image pointers when available; the Player ROI
  crop takes a CPU clone, so cropped input follows the host-memory path.
- The output point cloud preserves the trigger point cloud's timestamp and
  frame id. Fields are `x,y,z,intensity,rgb`; intensity is the MapTR class id,
  and `rgb` is a packed colour float.

## Practical checks before rollout

```bash
MODEL=/opt/qomolo/qpilot-resource/perception/model/dl_maptr_30
ls -lh "$MODEL"/{camera.backbone.plan,maptr.depthnet.plan,maptr.vtransform.plan,maptr_decoder_head.plan,libmaptr_plugins.so}

# During replay/startup, verify initialization, input contract and outputs.
grep -E 'MapTR model_path|MapTR core initialized|first complete camera set|Not enough|Failed to create|Failed to dlopen|MapTR forward failed' \
  /debug/runqfile/baize_player/log.log | tail -200

ros2 topic hz /maptr_pointcloud
ros2 topic echo --once /maptr_pointcloud --no-arr
```

## 2026-08-13 vehicle-stop evidence review

The captured runtime profile from
`issue/maptr_test/3/dcu-1/qprofile/welldrive/qthd/perception_q/profile.yaml`
selects the generic pipeline step name `type: dl_bevfusion` in
`pipline-dl_bevfusion_cluster`. Per deployment-owner confirmation, this qthd
deployment runs that step in its LiDAR-only mode; the generic YAML type name
must not be interpreted as camera fusion. The deployed parallel combination is
therefore LiDAR-only detection plus three-camera MapTR.

The captured run is not evidence of a MapTR CUDA/TensorRT failure:

- In `maptr_test/3`, MapTR has no `MapTR core initialized`, `MapTR forward
  failed`, CUDA error, TensorRT error, or decoder-init-failure log entry.
- At `2026-08-13T02:56:19.700Z`, before any MapTR initialization record,
  the four LiDAR subscriber executors (`front_top`, `front_left_up`,
  `front_right_down`, `front_left_down`) all reach their queue threshold of
  10 and reject tasks.
- The sensor monitor then repeatedly publishes error `4124130`; the keeper
  error catalogue defines it as `lidar_driver: some lidars is wrong.`

This establishes an input-side LiDAR queue-overrun/data-loss safety fault for
the captured stop. It does **not** establish that enabling MapTR caused the
overrun: `maptr_test/1` contains successful concurrent MapTR and
`dl_bevfusion` timing logs (MapTR forward average about 33 ms, while the
`dl_bevfusion` step is roughly 70--90 ms), and no CUDA/MapTR forward failure.

Two configuration inconsistencies still need correcting before a controlled
on-vehicle reproduction:

1. The local `qbaize_play.yaml` has `camera_undistort=false`, while this
   MapTR profile requires a Player-undistorted `1400 x 1000` image then crops
   it to `960 x 768`. This local replay cannot validate the vehicle camera
   preprocessing contract as written.
2. The local player YAML has `det_obj_module` commented out. It is therefore
   not a faithful replay of concurrent object detection plus MapTR.

For the next vehicle test, capture the exact effective runtime profile,
module loader manifest, GPU memory/utilisation, each LiDAR callback queue/drop
count, and MapTR init/forward timing in the same timestamp interval. The
acceptance criterion is zero `4124130` while both algorithm paths are active.

## 2026-08-17 raw-instance output contract

Both 5.6 deployment variants were updated locally after confirming that the
runtime already holds the original decoder output as a vector of
`MapTRInstance { label, score, ordered points }`, but the old publication path
resampled every segment at 0.1 m and discarded its instance membership.

`maptr_pointcloud` is now the algorithm-facing, non-resampled output.  It has
one record per original decoder point (the active cnwxijk profile specifies 15
points per vector) and exposes these `PointCloud2` fields:

| field | type | meaning |
| --- | --- | --- |
| `x`, `y`, `z` | `FLOAT32` | original MapTR point coordinates |
| `intensity` | `FLOAT32` | MapTR class label |
| `rgb` | `FLOAT32` bits | `0x00RRGGBB` class colour for generic viewers |
| `score` | `FLOAT32` | prediction confidence, repeated for its instance points |
| `instance_id` | `UINT32` | frame-local post-threshold instance index |
| `point_index` | `UINT32` | original ordered point index inside the instance |

The record size is 48 bytes. `instance_id` is intentionally documented as
frame-local: it is not a MapTR temporal tracking token.

The new optional `maptr_pointcloud_vis` topic is visualization-only.  When
enabled it keeps the former RGB point-cloud style and may resample at a
configured spacing so RViz displays visually continuous lines. It must not be
used as an algorithm input.

The profile switch is at:

```yaml
perception_q:
  dl_bevfusion_maptr:
    params:
      maptr:
        visualization:
          enabled: false
          point_spacing_m: 0.1
        crop_player_undistorted_input: true
        enable_perf_timing: false
```

Both deployment branches now disable vehicle-side visualization and performance
timing logs, while enabling Player undistorted-input cropping for the padded
1400x1000 Player stream.

The changes were committed and pushed in both branches of both repositories:

| repository | normal | parallel |
| --- | --- | --- |
| `src/perception_q` | `af94ed99e` | `21b9bc92a` |
| `src/profile_project` | `338201276` | `f8289a664` |

The local ROS playback router was also updated to forward
`maptr_pointcloud_vis`; otherwise the topic would remain invisible to RViz.
Validation: the normal-branch modified objects compiled in
`baize-welldriver-wviz-1`; its final library link remains blocked by the
pre-existing missing `/opt/qomolo/welldrive/lib/libexternal_msg.so.5.6.9-0`.
The parallel branch's modified `dl_bevfusion_maptr_pointcloud.cpp` and
`maptr_node.cpp` objects compiled successfully after its CMake target was
configured in the same container. Both profile YAML files parse successfully.

For recordings made with visualization disabled, the local standalone ROS2
converter is `/data/baize/baize-welldriver/runqfile/maptr_pointcloud_to_vis_ros2.py`.
It subscribes to raw `maptr_pointcloud`, groups by `instance_id`, orders by
`point_index`, and publishes a dense `maptr_pointcloud_vis` display topic. A
two-instance synthetic ROS2 test verified that it does not interpolate from
one instance into another.

## Source anchors

- Node configuration, subscriptions and trigger: `maptr_node.cpp`.
- Engine paths and MapTR Core parameters: `dl_bevfusion_maptr.cpp`.
- Plugin-first load and encoder/head construction:
  `CUDA-BEVFusion/src/bevfusion_maptr/bevfusion.cpp`.
- Output `PointCloud2` layout: `dl_bevfusion_maptr_pointcloud.cpp`.
- Build targets and linked CUDA/TensorRT dependencies:
  `CUDA-BEVFusion/CMakeLists.txt`.

## 2026-08-17 55m parallel profile

The canonical deployment profile repository is
`src/perception_q_profile_project` (not the local-test copy in
`src/profile_project`). Its `release-test-maptralone-parallel-5.6-55` branch
was created from `release-test-maptralone-parallel-5.6` and pushed at
`c45f849`. It selects the packaged runtime directory
`/opt/qomolo/qpilot-resource/perception/model/dl_maptr_55`, which must contain
the `maptr_0807_x0_55_bev060_decoder4` engine artifacts, with
`pc_range: [0.0, -10.0, 55.0, 10.0]`, `bev_pool_width: 91`, and `bev_w: 46`.
Those dimensions were verified against the engine's vtransform contract:
input `1x256x33x91`, output `1x256x17x46`. Required plan files and plugin are
present and non-empty; the profile YAML parses successfully.
