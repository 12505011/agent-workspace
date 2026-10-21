# Local JK deployment branch

- User requested latest master plus deployment, without latency instrumentation.
- Repo `/data/baize/baize-welldriver/src/perception_q`, current branch
  `release-test-mapod-jk-test-1013`, base origin/master `dae52adfa`.
- Migrated current shared-three-camera/single-fusion OD+MAP implementation and
  OD-only option. Preserved fused_bev256/middle512 input contracts, output wire
  layout and existing obstacle/maptr_pointcloud publication.
- Removed timed-forward path, SCN/TensorRT/MAP trace arguments and marks,
  processing-time log block, timer header and standalone benchmark source/target.
  Required stream dependency events remain. Legacy set_timer is inert.
- Four source contract tests and git diff --check pass. User will compile and
  playback; no build, commit or push performed.
- Original uncommitted source changes preserved in git stash named
  `preserve pre-1013 MapOD deployment edits`; old branch retained. Source snapshots
  also retained in `/tmp/mapod1013-source.PosjyZ`. Unrelated old-branch changes
  (openwiki, cluster-distance/default-delay edits) were not migrated.
