# Orin OneModel / BEVFusion 延迟测试

最后核验：2026-10-21（北京时间）。本任务的 agent-workspace 分支为 **`orin_model_delay_test`**。

## 目标与边界

复用相同数据段、输入与测量口径，比较带 neck OneModel（OD+MAP）和单 BEVFusion 的延迟、CPU/GPU 负载、前后处理开销。
由用户编译和播包；代理准备代码、脚本、检查环境及离线分析。未经当次授权，不自行启动正式播包，不改原播包脚本或停止其他服务。
本笔记不包含凭据、原始会话、原始大日志或模型文件。

## 仓库、分支和目录

| 用途 | 路径 / 分支 |
|---|---|
| agent-workspace 实际仓库 | `/home/westwell/agent-workspaces/agent-workspace`；旧约定 `/home/westwell/agent-workspace` 在本次检查中不存在 |
| 本任务独立工作区 | `/home/westwell/agent-workspaces/agent-workspace-orin-model-delay-test` |
| 本地部署代码 | `/data/baize/baize-welldriver/src/perception_q` |
| Orin 部署代码 | `/data/code/all_ws/ws/ruicao/baize_ruicao/src/perception_q`，容器内 `/debug/src/perception_q` |
| 延迟测试代码分支 | **`release-test-onemodel-delay-test-1020`** |
| 延迟代码提交 | **`20954deed76c3c1767afa1d16d69c6db828e3c8b`**；本地和 Orin 已核验一致 |
| 原部署代码分支 | `release-test-mapod-jk-test-1020`，保持 `0b67c598df77e257108f19ae95e630a941d7f548`，不混入计时改动 |
| Orin profile 分支 | `release-test-mapod-jk-test-1020`，有 Orin 播包专用配置，不可直接丢弃 |
| profile 源文件 | `/data/code/all_ws/ws/ruicao/baize_ruicao/src/perception_q_profile_project/project/cnwxijk/qthd/perception_q/79-perception.yaml` |
| 生效 profile | 容器内 `/etc/qomolo/profile/welldrive/qthd/perception_q/profile.yaml`；须与源码和初始化日志一起核对 |
| 本地独立工具 | `/data/Downloads/onemodel_delay_test_20261020/` |
| Orin 独立工具 | 宿主工作区 `tools/onemodel_delay_test/`，容器内 `/debug/tools/onemodel_delay_test/` |
| 原播包入口 | 容器内 `/debug/baize_player/qbaize_play.sh`，不修改 |
| 目标容器 | `baize_ruicao-wviz-1`，宿主工作区映射为 `/debug` |
| Orin SSH | `nvidia@192.168.103.98`，凭据仅使用已有授权方式，不记入本仓库 |

采集、分析、编译辅助脚本**独立于 perception_q 仓库**；本任务 `tools/` 保存小型可复用快照。
不要把采集脚本重新塞进 perception_q；该代码分支只保存插桩和相关测试。

## 当前 OneModel 已核验的契约

- bundle：`/debug/code/maptr/models/qth_map5_roi_neck_q40_epoch20_20261013/build_orin_cuda114_trt8522_fp16`。
- 对应 `job-67a73089ce831308cdc4c86c`、epoch20，checkpoint SHA256：`bffe2ddf0a485cb344eec7217d52355025475a1172768d4f8484a40140bcbb69`（bundle manifest 核验）。
- ROI 后接独立 neck；6 层 decoder、40 query、每条 20 点；7 个规范类槽中 5 类生效。
- 相机 raw **0、1、6** → 模型 slot **0、1、2**。
- **98 Orin 本次是播包，不是实车**：读取 `camera_x`，`use_undistorted_camera_topics: false`，不是 `/undistort`。
- `crop_player_undistorted_input: true`：1400×1000 padded 输入裁 `(220,116,960,768)`；已有原生 960×768 的输入直接通过，再按训练预处理到 704×256。
- 单次共享融合：OD 用 `middle512`，MAP 用 `fused_bev256`，`schedule=parallel_production`。
- 体素 `[0.075,0.075,0.2]`；OD XY `[-54,54]`；MAP `[0,54]×[-10,10]`。
- FP16 bundle 文件齐全，但 FP16 构建开关不保证所有内部层都是 FP16；比较必须保存 engine SHA256/实际格式证据。

## 目前完成与未完成

1. 延迟分支已建立、提交，并同步到 Orin；截至记录时未由本任务 push 代码分支。
2. 本地三个目标编译通过（`BUILD_EXIT=0`），CPU 休眠/实际线程 CPU 时间测试、CUDA Event 实设备读数测试通过。
3. 用户在 Orin 已执行编译安装辅助，成功目录：`/debug/benchmarks/build_before_timing.mRfpDY/`。
4. 2026-10-21 手动播包曾持续出现 `MAPOD_OUTPUT`，OD 候选框约 41–47、MAP 实例 2–4，说明那次确实完成双任务推理；输出数量不等于最终发布数量。
5. 相邻日志约 168ms 仅是输出间隔，**不当作纯模型耗时**。
6. 自动采集轮 `benchmarks/20261021_022413_onemodel_detail_g9rp0hmm/` **无效**：播放器退出码72，`vpiconvert` 依赖加载失败；没有有效 core 帧，禁止当性能结果。
7. 同轮 CPU 采样文件句柄变量被库清单写入复用而关闭，已修复并同步；`test_tools.py` 3 项测试通过（含复现原错误的两次采样测试）。只需更新 Python 脚本，不用重编模型代码。
8. **尚无这套新采集流程的完整、有效 OneModel vs 单 BEVFusion 对照结论。**

## 当前优先工作流：原播包 + 独立整机负载

用户最新选择先直接看整机负载，暂不让自动采集器接管播包。

1. 容器内沿用用户已跑通的原播包命令/环境。需要模型分段计时时，在同一已跑通环境设置：

```bash
cd /debug/baize_player
BEV_PERF_LEVEL=detail bash qbaize_play.sh 2>&1 \
  | grep -aE --line-buffered 'BEV_PERF|MAPOD_|ObjDetTiming|Independent MapOD|failed|error' \
  | tee /debug/mapod_detail_A1.log
```

只改外层环境和过滤，不改原脚本。实际使用唯一文件名，避免覆盖历史轮次；先确认没有另一份播放器。
关闭分项时使用 `BEV_PERF_LEVEL=basic` 测整体，或不设置该变量关闭这套插桩。
这版统一使用 `[BEV_PERF]`，不再输出旧版 `MAPOD_STAGE` / `MAPOD_BENCHMARK`；
`MAPOD_OUTPUT` 只证明模型有结果。普通播包未设置 `BEV_PERF_LEVEL` 时不显示本套分段耗时，旧 profile 的 timer 字段不能代替这个开关。

2. **另开 Orin 宿主机终端**，不是容器终端。切换到宿主路径并不会退出容器；`docker` 和 `tegrastats` 应在宿主可用：

```bash
command -v docker tegrastats
sudo tegrastats --interval 1000 \
  | tee /data/code/all_ws/ws/ruicao/baize_ruicao/orin_mapod_load_A1.log
```

该命令保存整机逐核 CPU、GPU、内存、EMC、频率/温度等可用字段；播完 Ctrl-C。
若普通用户无写入权限，用可写目录或让 root 的 `tee` 写入，不要扩大整个工作区权限。
可同时另用 `pidstat` 做进程 CPU 采样，但整机负载不等于模型独占资源。

3. 保存每轮开始/结束时间（Orin 日志常用 UTC，北京时间加8小时），配套保留播包计时日志和资源日志。
原始 `tegrastats` 自带日期时间，独立自动采集版本另加 monotonic 时间戳；不能忽略时间对齐就作段级归因。

## 可选：自动同步采集（环境问题解决后使用）

### 编译安装：容器内

```bash
bash /debug/tools/onemodel_delay_test/build_timing.sh
```

只增量构建 `bevfusion_mapod_core`、`bevfusion_core`、`lidar_obj_det`，安装三个库到原配置使用的 `/debug/install/lib/`。
旧库和构建日志另存 `/debug/benchmarks/build_before_timing.XXXXXX/`。确认 `BUILD_EXIT=0`。
切换分支只切源码；**不编译安装不会切换实际执行库**。

### 采集：Orin 宿主机

```bash
cd /data/code/all_ws/ws/ruicao/baize_ruicao
sudo python3 tools/onemodel_delay_test/collect.py \
  --case onemodel --level detail --seconds 240
```

`benchmarks` 曾由容器 root 创建，因此普通用户创建运行目录会失败；当前 sudo 方式已越过此权限错误。
采集器会调用原播包，不要再手动启动第二份。当前环境还存在下面的 `vpiconvert` 问题，需先解决/对齐手动环境。

产物：`model.log`（关键日志，非全量）、`tegrastats.log`、`system.jsonl`、库加载路径、profile前后快照、engine/库 SHA256、manifest、`summary/report.md` 和 CSV/JSON。
每次唯一目录，保留原始证据；无有效 core 帧时报告 INVALID，不当作成功。

## 已定位的播包环境问题（不擅自修包）

2026-10-21 自动启动播包及独立 `gst-inspect` 显示：

- 宿主 L4T 35.3.1、VPI 2.2.6；容器 VPI 2.3.9、CUPVA 2.3。
- `libvpiconvert.so` 存在，但 `libcupva_host.so.2.3` 引用的 `PvaProgramSetDMADescriptorsV2`、`PvaProgramSetPointerValueEx` 在当前宿主 PVA 库不可解析。
- GStreamer 将插件列入黑名单，最终 `no element vpiconvert`，播放器初始化失败。
- DeepStream OSD 警告、EGL 警告不应直接替代这条已验证的缺符号证据。
- 手动某轮能跑通，**不代表采集器启动环境已一致**。额外 export/初始化/命令参数差异尚未确认；先对齐，不改 engine、不绕过去畸变、不贸然升级驱动或系统包。

## 统计口径与对照方案

三组：A=OneModel 全开；B=同一 bundle 只设 `enable_maptr:false`（`matched_od`）；C=原版单 BEVFusion。
在原有79文件调整、按工程原方式刷新 profile，不另起 YAML 覆盖层。

- B 用于衡量增加 MAP 的整体增量，除 MAP 开关外保持输入、权重、几何、精度、阈值等一致。
- **当前原版 BEVFusion 代码相机不足5个会降级 LiDAR-only**，不能只播0/1/6然后拿低延迟冒充融合对照。
- C 若相机/engine/图像/体素等不同，只能解释产品配置差异，不作“只有加MAP这一个变量”的结论。
- A→B→A 重复、同一数据段；先看 A 的可重复性。每层剔除最前30个成功帧和失败/跳过/降级帧，建议至少300个稳态 core 帧。
- report 同时给样本N、均值、P50、P95和GPU有效N，不只截几帧。
- `core/total` 是 forward 主体墙钟，含内置后处理与必要等待；`proc/total` 还含外部前处理和点云关联；`node/total` 还含其他算法/发布。
- `thread_cpu_ms` 是本线程实际获记CPU时间，含可能的驱动忙等，不含其他worker；不等于整机CPU占用。
- `stream_ms` / `model.device_window` 为CUDA Event经过时间，可能含提交空隙/等待，不是纯kernel忙时。
- 并行流、父子阶段不可相加；MAP ROI+neck+decoder在一个engine内，只测合计，不编造neck单独耗时。
- Fuser engine 含融合及 BEV encoder/decoder；稀疏 backbone 是第三方库，不可用 trtexec 代替。
- 主延迟用 basic 重复轮；detail 用于拆分，单独说明插桩开销。
- 不自动改锁频、功耗或启停其他容器；保存实际状态和负载。2026-10-21 无效轮记录 MAXN、8核约2188MHz、GPU约930.75MHz，但不能把此状态假定为以后所有轮次。

## 交接给后续代理

先读本文件和 `shared/`，核验实际Git分支、安装库、源码profile/生效profile/初始化日志。
优先沿用手动已跑通的播包环境 + 整机资源日志；拿到有效数据再生成最终性能文档。
独立工具可用 `python3 tools/test_tools.py` 回归；分析命令为 `python3 tools/analyze.py RUN_A RUN_B --out REPORT_DIR`。
不要将无效轮当结果，不要将输出频率当模型耗时，不要用容器里的 `/tmp` 代指宿主 `/tmp`。
