# Task: unhook_area_detection

## Goal

跟踪 `unhook_area_detection` 目录下新增的挂车语义掩码 BEV 检测模块，
保留可复用的实现上下文、技术决策和验证结果。

## Scope

代码仓库：`/data/baize/baize-welldriver/src/perception_q`

- 当前代码分支：`qp-49056-tug-self-loading-position-function-5.7`
- 新增源文件：`src/unhook_area_detection/trailer_mask_bev.cpp`
- 相关构建文件：`src/unhook_area_detection/CMakeLists.txt`
- 相关运行时实现：`src/dl_runtime/dl_yolo/dl_runtime.cpp`

## Current state

- 已迁移到 5.7 分支，并形成两个本地提交：`7c2b84f9`（主模块）与
  `47eb2868`（具名补充 YOLO 推理接口）。
- `unhook_area_detection.cpp` 通过 include 编入 `trailer_mask_bev.cpp`，再以单个
  Poco manifest 导出 `UnhookAreaDetection` 和 `TrailerMaskBevNode`；构建产物只有
  `libperception_q_unhook_area_detection.so`。
- `dl_runtime.cpp` 支持配置 `supplemental_only: true` 的 YOLO 模型：模型仍加载，但
  不订阅相机 topic、也不参加常规调度；BEV 模块通过
  `RunNamedYoloModelOnBgrMatsWithMasks("dl_yolo_trailer_mask", ...)` 精确调用它。
- 当前 2D 验证阶段仅保留 `qpilot/perception/trailer_bbox_center_debug_2d`：代码提交
  `00ddd95a` 将实时链路收敛为 `camera_3 → ROI → 具名 YOLO → 绿色 mask 叠加图`，
  不进行全图回填、BEV/距离/zone 投影、点云验证或 3D marker 发布。原有位置估计实现
  仍保留在源文件中，尚未删除，供后续恢复使用。
- 曾试验 `debug_base_box` 的 base_footprint 矩形投影和 MarkerArray 发布，但相机畸变/
  标定误差使其暂不适合作为当前链路；实现记录保留在 Git 历史供后续参考。
- 2026-09-17 起当前有效链路回到 ROI 图像域：输出为 300×300（按 profile 可调）推理裁剪图，
  绿色为目标 class mask，不再回填整张相机图或进行 base 投影。
- ROI 由 `mask_zone_detection.zone_count`（当前 10）等宽竖向切分。profile 的
  `selected_zones` 可填写任意不重复的 0-based 编号组合；选中区域的掩膜像素总数达到
  `min_pixels` 时，在 `qpilot/perception/trailer_mask_zone_result` 发布整数 `1`，否则 `0`。
  `trailer_bbox_center_debug_2d` 每格底部直接绘制对应编号；黄色代表选中，灰色代表未选中。
  该话题的使用由 `unhook_area_detection.cpp` 控制：收到区域后，点云命中即立即输出
  `unhook_area_result=1`；只有连续空点云帧达到 `detection_frame_count` 才发布一次
  `trailer_mask_zone_request`。相机模块在下一帧图像上推理一次，回传
  `trailer_mask_zone_result`，其 0/1 即为最终 `unhook_area_result`。默认等待 1500 ms，
  超时或推理失败按 0 收口，防止区域检测状态卡住。
- 尚未在本任务记录中确认编译或测试结果。

## Verified facts

- 模块类名为 `qpilot::perception::TrailerMaskBevNode`，模块名常量为
  `trailer_mask_bev`。
- 配置首先从 `perception_q.trailer_mask_bev` 读取；若不存在，
  兼容读取 `perception_q.unhook_area_detection.trailer_mask_bev`。
- 源码通过由 `unhook_area_detection.cpp` 统一定义的 Poco manifest 导出两个模块类，
  避免把同一 CPP include 后再独立编译造成重复定义。
- 实现包含语义掩码到 BEV 投影、bbox 中心投影、远程裁剪推理、
  点云验证以及多种调试输出路径。

## Commands and validation

- 2026-09-16：已通过 `git diff --check`、接口调用点和 Git 提交检查核实迁移结果。
- 2026-09-17：ROI 分区变更通过 `git diff --check`，并用 `yq` 成功解析 profile 与 qfile YAML。
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

- 需要在目标环境完成 `perception_q`/目标库构建验证。
- 需要确认实际 profile 中采用顶层还是嵌套的
  `trailer_mask_bev` 配置路径。
- 运行该管线前必须确认 `dl_runtime` 与本模块处于同一进程，且名为
  `dl_yolo_trailer_mask` 的 YOLO handler 已完成加载；否则全局 live-node 指针为空或
  找不到具名模型，worker 会持续失败。
