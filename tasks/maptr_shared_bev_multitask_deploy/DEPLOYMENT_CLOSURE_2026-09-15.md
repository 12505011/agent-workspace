# MapOD deployment cleanup and closure — 2026-09-15

## Code identity

- Runtime repository: /data/baize/baize-welldriver/src/perception_q
- Branch: release-test-mapod-share-model-5.7
- Cleanup commit: 32b346f4
- Experimental snapshot: 4d5967ee, local annotated tag
  archive/mapod-latency-experiments-20260915.
- Cleanup tag: archive/mapod-deployment-cleanup-20260915.
- Commits/tags are local only; no push or target deployment was performed.

## Kept and retired

Kept parallel LiDAR/camera frontends, separate OD/MAP camera routes, buffer
consumption dependencies, and OD postprocessing/MAP execution overlap. Kept
MapOD-only configuration, input validation and existing result publication.

Removed forced single-BEV inference, explicit Map-ready waiting and dependency
experiment metrics/events. The existing checkpoint still requires its separate
routes; the roughly 100ms forced single-BEV measurement is not a validated
production accuracy/latency baseline.

Detailed SCN/Map timelines and CPU sections require both enable_timer=true and
enable_detailed_timer=true. Both default false. Basic timing log tags remain
compatible. Standalone bench_maptr_enqueue remains default-OFF and not installed.
Production CUDA Graph integration was not added.

## Profile migration and build boundary

Remove benchmark_single_bev and benchmark_map_ready_mode from effective profiles.
Legacy false/async values remain accepted; true/explicit/unknown ready modes
reject startup rather than silently changing inference semantics.

CoreParameter layout changed: rebuild core and algorithm together. No external
profile, startup script, model, engine, camera mapping, Orin environment or
installed runtime library was modified.

## Validation

- git diff --check passed; added-line security scan found no flagged patterns.
- Independent reviewer passed with no security concerns or logic errors.
- Local Docker baize-welldriver-wviz-1: cmake --build
  /debug/build/perception_q --target bevfusion_mapod_core -j2 passed.
- Same build, target lidar_obj_det -j2 passed.
- Builds emit macro and dependency deprecation warnings; not a zero-warning claim.
- No real-data playback or Orin validation was performed for this cleanup.

This closes deployment-side cleanup, not all potential optimization. Vendor SCN
work, runtime Graph integration and speed/accuracy changes remain separate tasks.
