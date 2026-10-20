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

- On 2026-10-20 the user confirmed that projection is fully aligned after
  setting `image_undistorted=false` and using the four cameras' distortion
  coefficients. Preserve this default for the current raw-image replay.
  This is user-verified visual playback validation; actual image dimensions
  were not independently measured during this session.

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

- User confirmed on 2026-10-20 that the actual playback images are distorted.
  Changed the module default `image_undistorted` to false so OpenCV uses each
  camera's profile distortion coefficients. All four active profiles have
  distortion_type=0 and eight coefficients (rational pinhole model).
  The earlier zero-distortion numerical comparison did not test this image
  geometry. Playback's camera_undistort tag alone is insufficient evidence
  of rectification. Image resolution still needs direct frame verification.

- Projection reference reviewed: `code/maptr/tools/3dod_maptr/maptr_visualize.py`,
  especially `project_points_to_image`, `raw_image_lidar2img`, and
  `draw_camera_overlay`. It projects with the exact source-image matrix and
  does not apply network image augmentation to the original image.
- Numerical comparison on 2026-10-20 used the four active camera calibrations,
  a 960x768 image (half-size K), and z=0. Reference versus current module
  projection differed by less than 0.0003 pixels on visible test points.
  This verifies formula equivalence under those assumptions, not alignment
  on real images. Actual replay image geometry and synchronization remain
  to be checked; no replay process was active during this check.

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
