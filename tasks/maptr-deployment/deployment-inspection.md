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

## Source anchors

- Node configuration, subscriptions and trigger: `maptr_node.cpp`.
- Engine paths and MapTR Core parameters: `dl_bevfusion_maptr.cpp`.
- Plugin-first load and encoder/head construction:
  `CUDA-BEVFusion/src/bevfusion_maptr/bevfusion.cpp`.
- Output `PointCloud2` layout: `dl_bevfusion_maptr_pointcloud.cpp`.
- Build targets and linked CUDA/TensorRT dependencies:
  `CUDA-BEVFusion/CMakeLists.txt`.
