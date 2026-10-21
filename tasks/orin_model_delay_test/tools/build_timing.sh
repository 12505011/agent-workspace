#!/usr/bin/env bash
# Standalone helper inside baize_ruicao-wviz-1; no playback or YAML changes.
set -euo pipefail
build=/debug/build/perception_q
source_root=/debug/src/perception_q
mkdir -p /debug/benchmarks
backup=$(mktemp -d /debug/benchmarks/build_before_timing.XXXXXX)
log="$backup/build.log"
printf 'Build log: %s\n' "$log"
if cmake --build "$build" --target bevfusion_mapod_core bevfusion_core lidar_obj_det -j "${JOBS:-4}" >"$log" 2>&1; then
  printf '\nBUILD_EXIT=0\n' >>"$log"
else
  result=$?
  printf '\nBUILD_EXIT=%d\n' "$result" >>"$log"
  tail -n 40 "$log"
  exit "$result"
fi
for name in bevfusion_mapod_core bevfusion_core lidar_obj_det; do
  lib="libperception_q_${name}.so"
  test -s "$build/bin/$lib"
  if test -f "/debug/install/lib/$lib"; then
    cp -a "/debug/install/lib/$lib" "$backup/$lib"
  fi
  install -D -m 755 "$build/bin/$lib" "/debug/install/lib/$lib"
done
grep -aq '\[BEV_PERF\]' /debug/install/lib/libperception_q_lidar_obj_det.so
grep -aq '\[BEV_PERF\]' /debug/install/lib/libperception_q_bevfusion_mapod_core.so
grep -aq '\[BEV_PERF\]' /debug/install/lib/libperception_q_bevfusion_core.so
git -c safe.directory="$source_root" -C "$source_root" status --short >"$backup/source_status.txt"
sha256sum /debug/install/lib/libperception_q_bevfusion*_core.so /debug/install/lib/libperception_q_lidar_obj_det.so >"$backup/installed.sha256"
printf 'Build/install complete. Original playback unchanged. Backup/log: %s\n' "$backup"
