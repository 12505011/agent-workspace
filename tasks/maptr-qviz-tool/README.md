# MapTR front camera overlay

## Verified context

- Implementation checkout: `/data/baize/baize-welldriver/src/maptr_conv_image`.
- The `perception_q` MapOD publisher writes `maptr_pointcloud` as a 32-byte
  `PointCloud2` record with `x/y/z`, `category`, `score_q`, `instance_id`, and
  `point_index`. The cloud header is copied from its source LiDAR cloud.
- `/data/baize/baize-welldriver/runqfile/maptr_pointcloud_to_vis_ros2.py`
  groups points by instance and sorts by point index before visual interpolation.
- The `perception_q` `surround_bev` profile names `camera_16` as the front
  primary camera. This is the provisional default for the new overlay module.

## Implementation and validation

- Standalone Baize module subscribes to `maptr_pointcloud` and a configured
  camera image, pairs source timestamps, interpolates each instance, projects
  through the selected camera calibration, and publishes a `bgr8` overlay.
- The pure C++ decoder and interpolation test passed with CMake/CTest on
  2026-10-19. It covers unordered instances, short intermediate segments,
  and a big-endian padded PointCloud2 payload.
- Full Baize module configuration/build was unavailable on this host because
  its Baize development package (`baizeConfig.cmake` and headers) is absent.
  Complete that build and playback check in a Baize SDK environment.

## Handoff

- Confirm the camera topic and calibration key before vehicle or qfile use;
  the module defaults are `camera_16` and `camera16`.
- Merge the example module profile and loader entry from the implementation
  README into the intended Baize replay configuration.
