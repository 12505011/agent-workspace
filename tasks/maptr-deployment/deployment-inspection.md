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
does not select a literal `dl_bevfusion_lidar_only` pipeline step. Its selected
step is `type: dl_bevfusion` in `pipline-dl_bevfusion_cluster`; whether that
implementation selects LiDAR-only engines internally depends on its vehicle
configuration and should not be inferred from the pipeline name.

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

## Source anchors

- Node configuration, subscriptions and trigger: `maptr_node.cpp`.
- Engine paths and MapTR Core parameters: `dl_bevfusion_maptr.cpp`.
- Plugin-first load and encoder/head construction:
  `CUDA-BEVFusion/src/bevfusion_maptr/bevfusion.cpp`.
- Output `PointCloud2` layout: `dl_bevfusion_maptr_pointcloud.cpp`.
- Build targets and linked CUDA/TensorRT dependencies:
  `CUDA-BEVFusion/CMakeLists.txt`.
