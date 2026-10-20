# MapTR front camera overlay

## Verified context

- Implementation checkout: `/data/baize/baize-welldriver/src/maptr_conv_image`.
- The `perception_q` MapOD publisher writes `maptr_pointcloud` as a 32-byte
  `PointCloud2` record with `x/y/z`, `category`, `score_q`, `instance_id`, and
  `point_index`. The cloud header is copied from its source LiDAR cloud.
- `/data/baize/baize-welldriver/runqfile/maptr_pointcloud_to_vis_ros2.py`
  groups points by instance and sorts by point index before visual interpolation.
- The requested front camera topics are `camera_0`, `camera_1`, `camera_2`,
  and `camera_6`. The overlay uses calibration keys `camera0`, `camera1`,
  `camera2`, and `camera6` by default.

## Implementation and validation

- Standalone Baize module subscribes to `maptr_pointcloud` and four camera
  images, pairs source timestamps per camera, interpolates each instance once,
  projects through each camera calibration, and publishes four `bgr8` overlays.
- The pure C++ decoder and interpolation test passed with CMake/CTest on
  2026-10-19. It covers unordered instances, short intermediate segments,
  and a big-endian padded PointCloud2 payload.
- Full Baize module configuration/build was unavailable on this host because
  its Baize development package (`baizeConfig.cmake` and headers) is absent.
  Complete that build and playback check in a Baize SDK environment.

## Handoff

- On 2026-10-20, added the four overlay topic registrations to `ros_tools`'s
  `src/visualization_assist/vis_assisant.cpp`. Built target `visassist` in
  container `baize-welldriver-wviz-1` with ROS/interface setup sourced and
  installed `/debug/install/lib/libvisassist.so`. Its dependencies resolve
  with the replay environment. Restart replay to load the new library.
- ROS output names are `/camera_0/maptr_overlay`, `/camera_1/maptr_overlay`,
  `/camera_2/maptr_overlay`, and `/camera_6/maptr_overlay`, with type
  `sensor_msgs/msg/Image`. Live message flow still needs replay verification.

- Confirm each camera topic's calibration key against the deployment profile
  before vehicle or qfile use.
- Merge the example module profile and loader entry from the implementation
  README into the intended Baize replay configuration.
