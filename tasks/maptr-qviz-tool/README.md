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

- Successfully pushed module commit `897b898` via SSH to remote branch
  `release-test-maptr-vis-1020` on 2026-10-20 at the user's request. Verified
  the remote ref and configured upstream tracking. No ros_tools push occurred.

- User narrowed publishing scope to maptr_conv_image only. Removed the
  temporary ROS bridge commit worktree and local maptr-qviz-overlay-20261020
  branch; original ros_tools uncommitted source edits remain. No ROS remote
  changes occurred. Retried maptr_conv_image master push; GitLab still rejects
  initialization because an Owner/Maintainer must create the default branch.

- Requested master pushes on 2026-10-20: module committed locally on master
  as `897b898`; GitLab rejected initial push because the empty project has no
  default branch and requires an Owner/Maintainer to initialize it.
- ROS bridge committed separately as `2d4af75` on top of origin/master
  `b542924`, local branch `maptr-qviz-overlay-20261020`. GitLab rejected master
  push because the branch is protected. Original ros_tools worktree changes,
  including unrelated edits, were preserved. Neither remote was updated.

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
