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

已在代码分支 `bev_3dod_maptr_shared_bev_mmdet3d` 实现源相机名称到逻辑
相机槽位的映射。联合训练继续使用独立 DataLoader 和严格 1:1 交替 runner。

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
- `FilterCameraViews` 现在同时输出逻辑 `camera_names` 和原始
  `camera_source_names`，并同步筛选图像与标定元数据。
- 联合配置分别定义 `map_camera_slots` 和 `od_camera_slots`，当前均为 3 路，
  后续可只扩展 OD 到 5 路而不改变 MapTR。
- PyTorch camera backbone/LSS 可处理 iteration 之间不同的相机数；ONNX/TensorRT
  应为 3/4/5 相机建立独立固定 profile，runtime `num_camera` 必须一致。

## Commands and validation

- `python -m unittest -v tests.test_filter_camera_views`：3 项通过。
- 修改文件和配置通过 `python -m py_compile`。
- `mmcv.Config.fromfile` 断言通过：runner 仍为严格 `object -> map`、
  `epoch_size=object`，Map/OD 源相机不同但逻辑槽位一致，范围和 0.6 m 网格未变。

## Decisions

- 保留现有 OD/Map 独立 batch 的 1:1 交替更新，不将两类样本拼入同一 batch。
- 使用任务独立的源相机列表和逻辑槽位；不通过黑图或伪标定补齐相机数。
- 不重新生成 PKL；相机筛选和别名统一在数据 pipeline 完成。
- 四相机部署使用独立 ONNX/TensorRT profile，不复用三或五相机 engine。

## Open questions / handoff

- 四相机部署的实际源相机名称、逻辑槽位和固定顺序尚待确认。
- 四相机 engine 落地时需清除 C++ runtime 示例中的 `num_camera=5` 硬编码。
- 尚未在 4090 数据上运行完整单卡/多卡 smoke training。
