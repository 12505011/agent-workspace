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

## Decisions

- 本任务的 agent-workspace 分支为 `task/unhook_area_detection`。

## Open questions / handoff

- 需要后续确认 `trailer_mask_bev.cpp` 与 `dl_runtime.cpp` 的最终接口契约，
  并完成目标库构建验证。
- 需要确认实际 profile 中采用顶层还是嵌套的
  `trailer_mask_bev` 配置路径。
