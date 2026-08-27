# Task: maptr_shared_bev

## Goal

设计并实现共享图像/BEV主干的 OD + MapTR 多任务训练，使不同任务能够使用不同相机集合。

## Scope

- 当前数据：`nuscenes_map` 与 `nuscenes_od`。
- 当前 PKL：`pkl_shared_bev_map_x0_54` 与 `pkl_shared_bev_od_x0_54`。
- 当前两任务均使用前视三相机，但中央相机命名不同：MapTR 为
  `CAM_FRONT_TOP_MID`，OD 为 `CAM_FRONT_MID`。
- 后续扩展目标：OD 使用 5 相机，MapTR 仍使用 3 相机。

## Current state

正在讨论相机异构输入下共享主干与任务头的接口设计，尚未选定新方案。
现有联合配置已经为 Map 与 OD 构造独立的相机筛选 pipeline，并通过交替
runner 分 batch 前向，具备支持不同相机集合的基础。

## Verified facts

- OD 与 MapTR 的相机集合及中央相机命名不完全一致。
- 后续不同任务的相机数量也可能不同。
- `bevfusion_maptr_shared_bev_nuscenes_map_od_alternating.py` 当前分别使用
  `camera_names` 和 `od_camera_names`，不会用同一个源字段名过滤两套 PKL。
- `AlternatingTaskEpochBasedRunner` 每次只向模型发送一个任务的 batch，并通过
  `task_mode` 路由任务头；不会把 Map 与 OD 样本拼进同一个 batch。
- 相机 backbone 和 LSS view-transform 从输入张量动态读取相机维 `N`；共享
  BEV 输出的空间尺寸与相机数量无关。
- 当前 MapTR 使用 `shared_bev` 输入路径，decoder 不依赖原始相机数；配置中的
  `num_cams=3` 主要属于相机特征/BEVFormer兼容路径，不应作为异构相机接口。

## Commands and validation

尚无。

## Decisions

尚无。

## Open questions / handoff

- 相机别名应在数据转换、数据集 pipeline，还是模型输入适配层统一。
- 共享范围应停留在逐相机图像 backbone，还是包含 view-transform/BEV encoder。
- 5 相机 OD 与 3 相机 MapTR 如何组织 batch、相机 mask 和任务路由。
