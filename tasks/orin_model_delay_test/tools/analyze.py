#!/usr/bin/env python3
"""Standalone offline, dependency-free BEV timing report."""
import argparse
import csv
import json
import math
from pathlib import Path
import re
import statistics
from collections import defaultdict

def percentile(values, quantile):
    values = sorted(values)
    at = (len(values) - 1) * quantile
    low = int(at)
    return values[low] + (values[min(low + 1, len(values)-1)] - values[low]) * (at-low)

def stats(values):
    return dict(n=len(values), mean=statistics.mean(values), p50=percentile(values, .5),
                p95=percentile(values, .95), minimum=min(values), maximum=max(values))

def summarize(folder, warmup=30):
    folder = Path(folder)
    rows, frames, seen = [], defaultdict(list), set()
    warnings = []
    text = (folder / "model.log").read_text(errors="replace")
    for line in text.splitlines():
        if "[BEV_PERF]" not in line: continue
        row = dict(re.findall(r"([A-Za-z_]+)=([^\s]+)", line))
        if not all(k in row for k in ("model", "scope", "frame", "complete", "stage")): continue
        identity = (row["model"], row["scope"], row.get("tid", "0"), row["frame"])
        rows.append((identity, row))
        if row.get("phase") == "frame" and row["complete"] == "1" and identity not in seen:
            frames[identity[:2]].append(identity)
            seen.add(identity)
    valid = set()
    for group in frames.values(): valid.update(group[warmup:])
    buckets = defaultdict(lambda: defaultdict(list))
    for identity, row in rows:
        if identity not in valid or row["complete"] != "1": continue
        key = "/".join(identity[:2]) + "/" + row["stage"]
        for field in ("wall_ms", "thread_cpu_ms", "stream_ms"):
            if field == "stream_ms" and row.get("gpu_valid") != "1": continue
            try: value = float(row[field])
            except (KeyError, ValueError): continue
            if math.isfinite(value): buckets[key][field].append(value)
    result = {"run": str(folder), "warmup_successful_frames": warmup,
              "metrics": {k: {field: stats(v) for field, v in fields.items()}
                          for k, fields in buckets.items()}, "warnings": warnings}
    core_rows = [row for identity, row in rows if identity in valid and
                 row.get("scope") == "core" and row.get("phase") == "frame"]
    if not core_rows: warnings.append("没有有效 core 帧：不能据此宣称模型运行或延迟达标。")
    elif len(core_rows) < 300: warnings.append("稳态 core 样本少于 300 帧，P95 的代表性有限。")
    for needle in ("using lidar only", "Not enough images", "No enough images", "core_not_initialized"):
        if needle.lower() in text.lower(): warnings.append("日志包含降级/输入问题：" + needle)
    if any(row.get("cameras") == "0" for row in core_rows):
        warnings.append("出现零相机 core 帧，禁止作为融合模型有效对照。")
    manifest_path = folder / "manifest.json"
    result["manifest"] = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    result["observed"] = dict(core_frames=len(core_rows),
        camera_counts=sorted(set(r.get("cameras", "unknown") for r in core_rows)),
        map_enabled=sorted(set(r.get("map", "unknown") for r in core_rows)))
    case = result["manifest"].get("case")
    if case == "onemodel" and result["observed"]["map_enabled"] != ["1"]:
        warnings.append("OneModel 实际帧未全部开启 MAP，不能当双任务结果。")
    if case == "matched_od" and result["observed"]["map_enabled"] != ["0"]:
        warnings.append("matched_od 实际帧 MAP 开关不符，不能当单因素对照。")
    before_path = folder / "profile.before.json"
    after_path = folder / "profile.after.json"
    result["configuration"] = json.loads(before_path.read_text().splitlines()[-1]) if before_path.exists() else {}
    if after_path.exists():
        after = json.loads(after_path.read_text().splitlines()[-1])
        if result["configuration"].get("params") != after.get("params"):
            warnings.append("播包前后 profile 参数发生变化，必须核对初始化日志，不能假定预检配置就是实测配置。")
    if result["manifest"].get("playback_exit", 0) != 0:
        warnings.append("播放器返回非零退出码，检查启动失败还是测量后 shutdown 异常。")
    begin, end = 0, float("inf")
    if core_rows and all("mono_ms" in row for row in core_rows):
        begin = min(float(r["mono_ms"]) for r in core_rows) / 1000
        end = max((float(r["mono_ms"]) + float(r["wall_ms"])) for r in core_rows) / 1000
    resource = defaultdict(list)
    for line in (folder / "system.jsonl").read_text().splitlines() if (folder / "system.jsonl").exists() else []:
        sample = json.loads(line)
        if not begin <= sample["mono_s"] <= end: continue
        resource["cpu_system_pct"].append(sample["cpu_system_pct"])
        resource["cpu_loader_pct_one_core_100"].append(sum(p.get("cpu_pct", 0) for p in sample["processes"]))
        resource["loader_rss_mb"].append(sum(p.get("rss_mb", 0) for p in sample["processes"]))
    tegra = folder / "tegrastats.log"
    for line in tegra.read_text(errors="replace").splitlines() if tegra.exists() else []:
        stamp = re.search(r"mono_s=([\d.]+)", line)
        if not stamp or not begin <= float(stamp[1]) <= end: continue
        for name, pattern, scale in [
            ("gpu_busy_pct", r"GR3D_FREQ\s+(\d+)%", 1),
            ("ram_used_mb", r"RAM\s+(\d+)/", 1),
            ("board_input_w", r"(?:VDD_IN|VIN_SYS_5V0)\s+(\d+)(?:mW)?/", .001),
            ("gpu_temp_c", r"\bGPU@([\d.]+)C", 1),
            ("emc_busy_pct", r"EMC_FREQ\s+(\d+)%", 1),
            ("cpu_cv_rail_w", r"VDD_CPU_CV\s+(\d+)(?:mW)?/", .001),
            ("gpu_soc_rail_w", r"VDD_GPU_SOC\s+(\d+)(?:mW)?/", .001),
        ]:
            match = re.search(pattern, line, re.I)
            if match: resource[name].append(float(match[1]) * scale)
    result["resources"] = {k: stats(v) for k, v in resource.items() if v}
    return result

def write_report(results, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    lines = ["# Orin OneModel / BEVFusion 耗时对比", "",
        "统计剔除各模型/层级最前面的预热成功帧及失败帧。单位 ms；NA 不按 0 处理。",
        "wall 是主线程墙钟，thread CPU 是该线程实际获记的 CPU 时间（可包含驱动忙等），",
        "stream 是 CUDA Event 经过时间，可能含提交间隙、资源竞争，不是纯 kernel 时间。",
        "不同流、嵌套阶段不可求和；线程 CPU 不含其他 worker；端到端不含上游传感器/解码等待。", ""]
    totals = []
    csv_rows = []
    for result in results:
        run = Path(result["run"]).name
        manifest = result["manifest"]
        lines += ["## " + run, "", "目录：`" + result["run"] + "`", "",
                  "案例：`" + str(manifest.get("case", "unknown")) + "`；计时：`" + str(manifest.get("level", "unknown")) + "`。", ""]
        lines += ["实际帧契约：`" + json.dumps(result["observed"], ensure_ascii=False) + "`", ""]
        lines += ["- 注意：" + w for w in result["warnings"]]
        lines += ["", "| 阶段 | N | Wall均值 | Wall P50 | Wall P95 | 线程CPU P50 | Stream P50 | GPU有效N |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|"]
        for key, metric in result["metrics"].items():
            def value(field, quantile):
                return "%.3f" % metric[field][quantile] if field in metric else "NA"
            lines.append("| %s | %d | %s | %s | %s | %s | %s | %d |" % (
                key, metric.get("wall_ms", {}).get("n", 0), value("wall_ms", "mean"),
                value("wall_ms", "p50"), value("wall_ms", "p95"),
                value("thread_cpu_ms", "p50"), value("stream_ms", "p50"),
                metric.get("stream_ms", {}).get("n", 0)))
            for field, statistic in metric.items(): csv_rows.append(dict(run=run, stage=key, field=field, **statistic))
            if key.endswith("/core/total"): totals.append((run, manifest.get("level"), metric["wall_ms"]))
        lines += ["", "### 整机及 loader 资源（按稳态 core 时间窗对齐）", "",
                  "| 指标 | N | 均值 | P50 | P95 |", "|---|---:|---:|---:|---:|"]
        for key, statistic in result["resources"].items():
            lines.append("| %s | %d | %.2f | %.2f | %.2f |" % (key, statistic["n"], statistic["mean"], statistic["p50"], statistic["p95"]))
        lines += ["", "整机 GPU/内存/输入功耗包括解码及其他服务，不能归属于本模型。CPU loader 100%=一个逻辑核。", ""]
    lines += ["## 对照汇总", "", "| Run | 计时级别 | Core P50 | Core P95 |", "|---|---|---:|---:|"]
    lines += ["| %s | %s | %.3f | %.3f |" % (run, level, s["p50"], s["p95"]) for run, level, s in totals]
    lines += ["", "## 同级别成对差值", "",
              "| OneModel run | 对照 run | Core P50增量 | 增幅 | 可比性 |",
              "|---|---|---:|---:|---|"]
    for one in results:
        if one["manifest"].get("case") != "onemodel": continue
        for other in results:
            if other["manifest"].get("case") not in ("matched_od", "bevfusion"): continue
            if one["manifest"].get("level") != other["manifest"].get("level"): continue
            def core_median(run):
                return next((m["wall_ms"]["p50"] for k, m in run["metrics"].items()
                             if k.endswith("/core/total") and "wall_ms" in m), None)
            a, b = core_median(one), core_median(other)
            if a is None or b is None or b == 0: continue
            ca, cb = one["configuration"], other["configuration"]
            pa = {k:v for k,v in ca.get("params", {}).items() if k != "enable_maptr"}
            pb = {k:v for k,v in cb.get("params", {}).items() if k != "enable_maptr"}
            matched = bool(ca) and pa == pb and ca.get("model_files") == cb.get("model_files")
            note = "同 engine、同输入参数，需再核对帧与资源状态" if matched else "配置/engine不同，仅产品方案差异；不可单因素归因"
            lines.append("| %s | %s | %.3f ms | %.2f%% | %s |" % (
                Path(one["run"]).name, Path(other["run"]).name, a-b, 100*(a-b)/b, note))
    lines += ["", "## 结论边界与验收", "",
        "- OneModel 全开与同权重关闭 MAP 的差值才用于衡量加 MAP 的整体增量；不能用 MAP 阶段自身耗时代替。",
        "- 原版 BEVFusion 若相机数、图像尺寸、体素、权重、精度或后处理不同，只能报告产品配置差异，不作单因素归因。",
        "- 基础计时与详细插桩分开比较；详细插桩会有开销，以 basic 重复轮的整体时间为主。",
        "- 同一段包 A→B→A，检查两次 A 是否接近；检查每轮模型初始化、输入就绪、无 LiDAR-only 降级。",
        "- 查 manifest、profile.before/after、资源日志、引擎与库 SHA256，确认实测加载路径和配置未中途改变。",
        "- MAP ROI+neck+decoder 在同一 engine 内，外部只能测合计；逐层拆分需独立 TensorRT profiler，不能伪造分项。",
        "- Fuser engine 包含融合和 BEV encoder；稀疏 backbone 依赖第三方库，不能用 trtexec 代替整段。",
        "- GPU 时间线含等待，不足以给出纯 GPU kernel 忙时；需时另做 Nsight trace，不混入主延迟轮。", ""]
    (output / "report.md").write_text("\n".join(lines))
    with (output / "stages.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["run", "stage", "field", "n", "mean", "p50", "p95", "minimum", "maximum"])
        writer.writeheader(); writer.writerows(csv_rows)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--warmup", type=int, default=30)
    args = parser.parse_args()
    if args.warmup < 0: parser.error("warmup must be non-negative")
    write_report([summarize(run, args.warmup) for run in args.runs], args.out)
    print(args.out / "report.md")

if __name__ == "__main__": main()
