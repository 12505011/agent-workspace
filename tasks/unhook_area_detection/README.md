# Task: unhook_area_detection

## Goal

跟踪 `unhook_area_detection` 目录下新增的挂车语义掩码 BEV 检测模块，
保留可复用的实现上下文、技术决策和验证结果。

## Scope

代码仓库：`/data/baize/baize-welldriver/src/perception_q`

- 当前代码分支：`qp-49056-tug-self-loading-position-function`
- 新增源文件：`src/unhook_area_detection/trailer_mask_bev.cpp`
- 相关构建文件：`src/unhook_area_detection/CMakeLists.txt`
- 相关运行时实现：`src/dl_runtime/dl_yolo/dl_runtime.cpp`

## Current state

- `trailer_mask_bev.cpp` 已存在，目前为 Git 未跟踪文件（3155 行）。
- `src/unhook_area_detection/CMakeLists.txt` 已有本地修改：将源文件从
  `file(GLOB ./*.cpp)` 改为显式列出 `unhook_area_detection.cpp` 和
  `trailer_mask_bev.cpp`，并将两者编入同一
  `unhook_area_detection` 共享库。
- `src/dl_runtime/dl_yolo/dl_runtime.cpp` 也存在本地修改；
  `trailer_mask_bev.cpp` 声明并调用其具名掩码推理入口
  `RunNamedYoloModelOnBgrMatsWithMasks`。
- 尚未在本任务记录中确认编译或测试结果。

## Verified facts

- 模块类名为 `qpilot::perception::TrailerMaskBevNode`，模块名常量为
  `trailer_mask_bev`。
- 配置首先从 `perception_q.trailer_mask_bev` 读取；若不存在，
  兼容读取 `perception_q.unhook_area_detection.trailer_mask_bev`。
- 源码将 `TrailerMaskBevNode` 通过 Poco manifest 导出，与
  `unhook_area_detection.cpp` 作为独立翻译单元共用一个动态库。
- 实现包含语义掩码到 BEV 投影、bbox 中心投影、远程裁剪推理、
  点云验证以及多种调试输出路径。

## Commands and validation

- 2026-09-16：已通过 `git status`、`git diff` 和源码静态检查核实上述现状。
- 未运行构建、单元测试或实车/数据回放验证。

## 2026-09-16 logic review

- 当前生效的是中心点模式而非旧的掩码轮廓投影：`init()` 强制要求
  `center_point_mode: primary`、`enable_remote_crop: true` 与
  `enable_direct_crop_inference: true`。不满足任一条件会初始化失败。
- 有效数据流为：`camera_<remote_crop_camera_id>` 原图缓存和节流（默认 camera3、
  每 200 ms）→ 居中并上移的正方形 ROI（默认 640 px）→ 单槽后台 worker →
  `dl_runtime::RunNamedYoloModelOnBgrMatsWithMasks("dl_yolo_trailer_mask", ...)`
  → 将 ROI mask 还原到全图 → `projectBboxCenter()`。
- `projectBboxCenter()` 只保留位于目标横向位置和纵向窗口内、面积足够的一个连通域。
  它取 bbox 的横向中心及可配纵向比例作为锚点，把该像素射线与
  `center_anchor_height_m` 平面求交；再加 `center_depth_offset_m`、应用
  `center_range_lut`，并通过 `center_base_x` gate 和 zone 规则。
- 成功时会以中心点为几何中心、沿相机径向/切向摆放固定
  `center_box_length_m × center_box_width_m` 的 BEV 矩形。主输出
  `output_topic` 在中心点无效时发布全零 mask，不会回退至旧的 footprint。
- 推理 worker 只保存最新待处理 ROI；被 GPU/DL 互斥锁占用时，具名模型接口使用
  `try_lock` 直接失败，当前帧会被丢弃，下一次节流后的相机回调再尝试。这是代码中
  明确的低延迟取舍。
- `projectGroundContactMask()`、`buildBottomEdgeFootprint()`、全帧/裁剪语义订阅
  兼容路径仍被编译保留，提供旧版轮廓、底边和全掩码 BEV 投影，但当前初始化路径
  没有创建这些语义 topic 的订阅，因此不会驱动它们。
- 可选点云验证会按时间选取最近语义 mask，将点云投影回图像并用 BEV 膨胀区域关联；
  满足点数后以 PCA 拟合可见侧，再按 `trailer_width_m / 2` 补偿估计几何中心，仅发布
  QA/调试结果，不修正生产输出。

## Decisions

- 本任务的 agent-workspace 分支为 `task/unhook_area_detection`。

## Open questions / handoff

- 需要后续确认 `trailer_mask_bev.cpp` 与 `dl_runtime.cpp` 的最终接口契约，
  并完成目标库构建验证。
- 需要确认实际 profile 中采用顶层还是嵌套的
  `trailer_mask_bev` 配置路径。
- 运行该管线前必须确认 `dl_runtime` 与本模块处于同一进程，且名为
  `dl_yolo_trailer_mask` 的 YOLO handler 已完成加载；否则全局 live-node 指针为空或
  找不到具名模型，worker 会持续失败。
