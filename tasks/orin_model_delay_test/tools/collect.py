#!/usr/bin/env python3
"""Run on Orin HOST: collect CPU/GPU and original container playback together."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

HOST_ROOT = Path("/data/code/all_ws/ws/ruicao/baize_ruicao")
PROFILE = "/etc/qomolo/profile/welldrive/qthd/perception_q/profile.yaml"

def process_cpu_pct(old, new, seconds, hz):
    return max(0, new-old) / hz / seconds * 100 if seconds > 0 else 0

def command(argv, seconds=20):
    try:
        result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=seconds, encoding="utf8", errors="replace")
        return dict(code=result.returncode, output=result.stdout)
    except (OSError, subprocess.TimeoutExpired) as error:
        return dict(code=-1, output=str(error))

def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""): digest.update(block)
    return digest.hexdigest()

def snapshot():
    import yaml  # installed in the deployment container, not needed on host
    root = Path("/debug/src/perception_q")
    data = yaml.safe_load(Path(PROFILE).read_text())["perception_q"]
    pipeline = data["lidar_obj_det"]["enabled_pipline"]
    steps = data["lidar_obj_det"][pipeline]
    types = [step["type"] for step in steps]
    model = "dl_bevfusion_mapod" if "dl_bevfusion_mapod" in types else "dl_bevfusion"
    params = data.get(model, {}).get("params", {})
    fingerprint = {}
    directory = Path(params.get("model_path", "/nonexistent"))
    for path in sorted(directory.glob("*")):
        if path.is_file() and path.suffix in (".plan", ".onnx", ".so", ".json"):
            fingerprint[str(path)] = dict(bytes=path.stat().st_size, sha256=file_hash(path))
    libraries = {}
    for path in Path("/debug/install/lib").glob("*bevfusion*.so*"):
        if path.is_file(): libraries[str(path)] = file_hash(path)
    objdet = Path("/debug/install/lib/libperception_q_lidar_obj_det.so")
    if objdet.exists(): libraries[str(objdet)] = file_hash(objdet)
    playback_yaml = Path("/debug/baize_player/qbaize_play.yaml")
    selected_libraries = []
    def find_libraries(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "lib_name" and isinstance(value, str) and "lidar_obj_det" in value:
                    path = Path(value)
                    selected_libraries.append(dict(path=value, exists=path.is_file(),
                        instrumented=path.is_file() and b"[BEV_PERF]" in path.read_bytes(),
                        sha256=file_hash(path) if path.is_file() else None))
                else: find_libraries(value)
        elif isinstance(node, list):
            for item in node: find_libraries(item)
    if playback_yaml.exists(): find_libraries(yaml.safe_load(playback_yaml.read_text()))
    result = dict(profile=PROFILE, profile_sha256=file_hash(Path(PROFILE)),
                  pipeline=pipeline, types=types, model=model, params=params,
                  model_files=fingerprint, library_sha256=libraries,
                  selected_libraries=selected_libraries,
                  playback_sha256=file_hash(Path("/debug/baize_player/qbaize_play.sh")),
                  playback_yaml_sha256=file_hash(playback_yaml) if playback_yaml.exists() else None,
                  source=command(["git", "-C", str(root), "rev-parse", "HEAD"]),
                  source_status=command(["git", "-C", str(root), "status", "--short"]),
                  cuda_launch_blocking=os.environ.get("CUDA_LAUNCH_BLOCKING", "<unset>"))
    print(json.dumps(result, ensure_ascii=False))

def playback(seconds, script):
    """Container-side supervisor, owns exactly one playback process group."""
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM): signal.signal(sig, lambda *_: stop.set())
    child = subprocess.Popen(["bash", script], cwd="/debug/baize_player", start_new_session=True)
    print("BEV_CAPTURE_WRAPPER wrapper_pid=%d pgid=%d" % (os.getpid(), child.pid), flush=True)
    deadline = time.monotonic() + seconds
    requested = False
    while child.poll() is None:
        if stop.wait(.2) or time.monotonic() >= deadline:
            requested = True
            break
    # Also clean descendants when the wrapper shell exits before its children.
    try: os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError: pass
    until = time.monotonic() + 10
    while time.monotonic() < until:
        try: os.killpg(child.pid, 0)
        except ProcessLookupError: break
        time.sleep(.2)
    try: os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    result = child.wait()
    return 0 if requested else result

def cpu_totals():
    first = Path("/proc/stat").read_text().splitlines()[0].split()[1:]
    values = [int(v) for v in first[:8]]  # guest/guest_nice already in user/nice
    return sum(values), values[3] + values[4]

def process_sample(pid):
    path = Path("/proc") / str(pid)
    text = (path / "stat").read_text()
    rest = text.rsplit(")", 1)[1].split()
    return dict(pid=pid, comm=text.split("(", 1)[1].rsplit(")", 1)[0],
                ticks=int(rest[11]) + int(rest[12]), start_ticks=int(rest[19]),
                rss_mb=int(rest[21])*os.sysconf("SC_PAGE_SIZE") / 1048576,
                threads=int(rest[17]))

def monitor_system(stop, folder, container):
    previous_cpu = cpu_totals()
    previous_proc = {}
    mapped = set()
    pids, next_inventory = [], 0
    with (folder / "system.jsonl").open("w", buffering=8192) as handle:
        while not stop.wait(1):
            now = time.monotonic()
            if now >= next_inventory:
                top = command(["docker", "top", container, "-eo", "pid,comm"], 5)
                with (folder / "container_processes.log").open("a") as inventory:
                    inventory.write("mono_s=%.6f\n%s\n" % (now, top["output"]))
                pids = [int(line.split()[0]) for line in top["output"].splitlines()
                        if len(line.split()) >= 2 and line.split()[0].isdigit()
                        and "loader" in line.split()[1]]
                next_inventory = now + 5
                for pid in pids:
                    if pid in mapped: continue
                    # Read from the container as its normal user; paths are evidence,
                    # not an assumption that install/lib wins over an old RPATH.
                    maps_code = ("from pathlib import Path; "
                                 "p=Path('/proc/%s/maps'); "
                                 "print(''.join(x+'\\n' for x in p.read_text().splitlines() "
                                 "if 'bevfusion' in x or 'lidar_obj_det' in x))")
                    # docker top gives HOST PIDs. NSpid maps to the container PID.
                    try:
                        status = (Path("/proc") / str(pid) / "status").read_text()
                        match = re.search(r"^NSpid:\s+(.*)$", status, re.M)
                        inner_pid = int(match[1].split()[-1]) if match else pid
                        result = command(["docker", "exec", container, "python3", "-c", maps_code % inner_pid], 5)
                        with (folder / "loaded_libraries.log").open("a") as libraries_handle:
                            libraries_handle.write("host_pid=%d mono_s=%.6f\n%s\n" % (pid, now, result["output"]))
                        # Retry if early startup had not loaded the libraries yet.
                        if "lidar_obj_det" in result["output"]: mapped.add(pid)
                    except (OSError, ValueError): pass
            processes, updated = [], {}
            for pid in pids:
                try: sample = process_sample(pid)
                except (OSError, ValueError, IndexError): continue
                identity = (pid, sample["start_ticks"])
                old = previous_proc.get(identity)
                sample["cpu_pct"] = process_cpu_pct(old[0], sample["ticks"], now-old[1], os.sysconf("SC_CLK_TCK")) if old else 0
                updated[identity] = (sample["ticks"], now)
                processes.append(sample)
            current = cpu_totals()
            delta = current[0] - previous_cpu[0]
            busy = 100*(1-(current[1]-previous_cpu[1])/delta) if delta else 0
            handle.write(json.dumps(dict(mono_s=now, epoch_s=time.time(),
                          cpu_system_pct=max(0, min(100, busy)), processes=processes)) + "\n")
            previous_cpu, previous_proc = current, updated

def monitor_gpu(process, folder):
    with (folder / "tegrastats.log").open("w", buffering=8192) as handle:
        for raw in iter(process.stdout.readline, b""):
            handle.write("mono_s=%.6f %s" % (time.monotonic(), raw.decode("utf8", "replace")))

def capture(args):
    if not shutil.which("docker") or not shutil.which("tegrastats"):
        raise SystemExit("请在 Orin 宿主机运行，需要 docker 和 tegrastats；不要在容器内运行。")
    stop = threading.Event()
    interrupted = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM): signal.signal(sig, lambda *_: interrupted.set())
    root = Path(args.root).resolve()
    if root != HOST_ROOT and HOST_ROOT not in root.parents:
        raise SystemExit("输出目录必须位于已有 /debug 绑定挂载内：" + str(HOST_ROOT))
    root.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix=datetime.now().strftime("%Y%m%d_%H%M%S_") + args.case + "_" + args.level + "_", dir=str(root)))
    container_script = "/debug/tools/onemodel_delay_test/collect.py"
    def inside(*argv, **kwargs): return command(["docker", "exec", args.container, *argv], **kwargs)
    def save_snapshot(name):
        result = inside("python3", container_script, "_snapshot", seconds=60)
        (folder / name).write_text(result["output"])
        if result["code"] != 0: raise RuntimeError("配置快照失败，见 " + str(folder / name))
        return json.loads(result["output"].splitlines()[-1])
    before = save_snapshot("profile.before.json")
    active = command(["docker", "top", args.container, "-eo", "pid,comm"])
    if any("loader" in line.split()[-1] for line in active["output"].splitlines()[1:] if line.split()):
        raise SystemExit("目标容器已有 loader 在运行；先停止你之前的播包，采集脚本不会替你杀其他任务。")
    if not before["selected_libraries"] or not all(
            lib["exists"] and lib["instrumented"] for lib in before["selected_libraries"]):
        raise SystemExit("播包指定的 lidar_obj_det 库不存在或未装入计时版本。先编译安装；详见 " + str(folder / "profile.before.json"))
    is_mapod = before["model"] == "dl_bevfusion_mapod"
    map_enabled = bool(before["params"].get("enable_maptr", True))
    if (args.case == "onemodel" and not (is_mapod and map_enabled)) or \
       (args.case == "matched_od" and not (is_mapod and not map_enabled)) or \
       (args.case == "bevfusion" and is_mapod):
        raise SystemExit("当前运行时 profile 与 --case 不符；先修改原 79-perception.yaml 并刷新 profile。")
    if before["cuda_launch_blocking"] not in ("<unset>", "0"):
        raise SystemExit("CUDA_LAUNCH_BLOCKING 已开启，禁止与默认异步结果混比。")
    manifest = dict(case=args.case, level=args.level, seconds=args.seconds,
                    utc=datetime.now(timezone.utc).isoformat(), host=os.uname().nodename,
                    container=args.container, cpu_count=os.cpu_count(),
                    script_sha256=file_hash(Path(__file__)), original_playback=args.script,
                    resources_cpu="loader processes in target container; one core=100%",
                    resources_gpu="system-wide tegrastats, NOT per-model utilization")
    for key, cmd in {
        "docker": ["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
        "power_mode": ["nvpmodel", "-q"], "clocks": ["jetson_clocks", "--show"],
        "disk": ["df", "-h", "/", "/data"], "uptime": ["uptime"],
    }.items(): manifest[key] = command(cmd)
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    if args.check:
        print("Preflight passed: " + str(folder))
        return 0
    print("采集目录：" + str(folder), flush=True)
    print("将调用原播包脚本，不修改它。Ctrl-C 可停止本次采集和它启动的播放器。", flush=True)
    gpu = subprocess.Popen(["tegrastats", "--interval", "1000"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    gpu_thread = threading.Thread(target=monitor_gpu, args=(gpu, folder), daemon=True)
    cpu_thread = threading.Thread(target=monitor_system, args=(stop, folder, args.container), daemon=True)
    gpu_thread.start(); cpu_thread.start()
    wrapper_pid = []
    process = None
    def stop_playback():
        if not wrapper_pid: return
        # Revalidate identity, never signal a reused PID or another player's group.
        code = ("import os,signal,sys; p=int(sys.argv[1]); "
                "a=open('/proc/%d/cmdline'%p,'rb').read().split(b'\\0'); "
                "assert b'/debug/tools/onemodel_delay_test/collect.py' in a and b'_playback' in a; "
                "os.kill(p,signal.SIGTERM)")
        inside("python3", "-c", code, str(wrapper_pid[-1]))
    try:
        process = subprocess.Popen(["docker", "exec", "-e", "BEV_PERF_LEVEL=" + args.level,
            args.container, "python3", "-u", container_script, "_playback", str(args.seconds), args.script],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        def read_output():
            keep = re.compile(r"BEV_PERF|BEV_CAPTURE|MAPOD_|ObjDetTiming|Independent MapOD|Camera [0-9]|camera_infos:|model_path|model=|baize run|error|failed|abort|lidar.only|no enough", re.I)
            with (folder / "model.log").open("w", buffering=65536) as handle:
                for raw in iter(process.stdout.readline, b""):
                    line = raw.decode("utf8", "replace")
                    match = re.search(r"BEV_CAPTURE_WRAPPER wrapper_pid=(\d+)", line)
                    if match: wrapper_pid.append(int(match[1]))
                    if keep.search(line): handle.write(line)
        reader = threading.Thread(target=read_output, daemon=True); reader.start()
        while process.poll() is None:
            if interrupted.wait(.5) and wrapper_pid:
                stop_playback()
                interrupted.clear()
        reader.join(timeout=15)
        manifest["playback_exit"] = process.returncode
        manifest["output_reader_finished"] = not reader.is_alive()
    finally:
        if process is not None and process.poll() is None and wrapper_pid:
            stop_playback()
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.terminate()
        stop.set(); gpu.terminate()
        try: gpu.wait(timeout=5)
        except subprocess.TimeoutExpired: gpu.kill(); gpu.wait()
        gpu_thread.join(timeout=5); cpu_thread.join(timeout=10)
        save_snapshot("profile.after.json")
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    report = Path(__file__).with_name("analyze.py")
    result = command([sys.executable, str(report), str(folder), "--out", str(folder / "summary")], 60)
    print(result["output"], end="")
    print("完成，分析时提供整个目录：" + str(folder))
    summary_path = folder / "summary/summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text())[0]
        if not summary["observed"]["core_frames"]:
            print("INVALID: 未采到剔除预热后的有效 core 帧，不能用于模型延迟结论。", file=sys.stderr)
            return 3
    return result["code"]

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_snapshot": snapshot(); return 0
    if len(sys.argv) > 1 and sys.argv[1] == "_playback": return playback(int(sys.argv[2]), sys.argv[3])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=["onemodel", "matched_od", "bevfusion"], required=True)
    parser.add_argument("--level", choices=["off", "basic", "detail"], default="detail")
    parser.add_argument("--seconds", type=int, default=240)
    parser.add_argument("--root", default=str(HOST_ROOT / "benchmarks"))
    parser.add_argument("--container", default="baize_ruicao-wviz-1")
    parser.add_argument("--script", default="./qbaize_play.sh")
    parser.add_argument("--check", action="store_true", help="只检查，不启动播包或资源采样")
    args = parser.parse_args()
    if args.seconds <= 0: parser.error("seconds must be positive")
    return capture(args)

if __name__ == "__main__": sys.exit(main())
