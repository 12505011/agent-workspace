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
提交 `2044016` 将联合模型评估拆成 Map 与 OD 两套独立的数据集、任务路由、
指标和最佳 checkpoint 状态；独立测试进程可用 `--task map|object` 选择任务。

2026-08-29 已解决长期出现的 LiDAR voxel/spconv 多卡不稳定问题。问题不是
MapTR head、数据列数、相机数、NCCL 或 CUDA 源码差异，而是 CUDA 扩展的实际
编译工具链与 PyTorch 运行时不一致。当前 13 个扩展已统一使用 BEVFusion 容器
中的 CUDA 11.3/GCC 9.4 重新编译；8 卡评估另外固定关闭 cuDNN benchmark。

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
- 联合配置的验证集现在显式分为 `data.val.map` 和 `data.val.object`：Map 使用
  Map PKL、Map 相机名和 `chamfer`，OD 使用 OD PKL、OD 相机名和 `bbox`。
- `TaskModeDataset` 在验证 batch 中注入显式 `task_mode`，确保每套验证数据只
  执行自己的任务头。
- Map 与 OD 使用任务级 best 状态和文件名，二者的分数不会互相比较或覆盖。
- `tools/3dod_maptr/maptr_test.py --task map|object` 会选择对应验证集和任务头，
  因此可以把两个任务放在两个独立进程中评估。
- MapTR 与参考 BEVFusion 的 voxel CUDA 源码逐字节一致；旧错误来自二进制
  构建产物，而不是源码被修改。
- `maptr` 的 PyTorch 报告 CUDA 11.3，但 Conda 环境没有 `nvcc`；宿主机
  `/usr/local/cuda` 实际指向 CUDA 11.8，旧扩展因此由 CUDA 11.8/GCC 11
  编译后交给 PyTorch cu113 加载。
- 用 BEVFusion 容器的 CUDA 11.3/GCC 9.4 全量重编 13 个扩展后，所有扩展均可
  在 `maptr` Conda 环境正常导入。voxel 扩展的 ELF `.comment` 已确认 GCC 9.4。
- 关闭 voxel 重试和 CPU fallback 后，单卡同一 OD 路径连续通过 397 帧，证明
  x/z 后处理交换不是必要修复。
- 8 卡、`cudnn_benchmark=True` 时，模型在 decoder neck 的 FP16 1x1 Conv2d
  触发 `CUDNN_STATUS_INTERNAL_ERROR`，随后异步报告 `illegal instruction`。
  日志中的 `floordiv` 和 tensor-copy warning 与崩溃无关。
- `CUDA_LAUNCH_BLOCKING=1` 的 8 卡对照通过 2424 帧；不开 blocking、仅设置
  `cudnn_benchmark=False` 的对照通过 2736 帧。因此最终不需要全局同步，只需
  关闭 benchmark。
- 最终 8 卡 OD 评估在 `workers_per_gpu=0`、`cudnn_benchmark=False`、
  `voxelize_max_retries=0`、`voxelize_cpu_fallback=False` 下完整处理 10854 个
  样本，约 348 秒、31.2 task/s；无 `N=0`、非法指令、非法访存、cuDNN 错误。
  结果文件 114 MB，指标为 mAP 0.2601、NDS 0.3182。

## Commands and validation

- `python -m unittest -v tests.test_filter_camera_views`：3 项通过。
- 修改文件和配置通过 `python -m py_compile`。
- `mmcv.Config.fromfile` 断言通过：runner 仍为严格 `object -> map`、
  `epoch_size=object`，Map/OD 源相机不同但逻辑槽位一致，范围和 0.6 m 网格未变。
- `tests/test_task_evaluation.py`：5 项通过；任务路由、配置拆分和独立 best
  checkpoint 状态均已覆盖。
- `tests/test_gt_depth_cache.py`：3 项通过；`tests/test_filter_camera_views.py`：
  3 项通过。
- CUDA 扩展全量重编命令（在已挂载 MapTR 仓库的 BEVFusion 容器中）：
  `MAX_JOBS=8 python3 setup.py build_ext --inplace --force`，退出码 0，13 个扩展
  全部复制回 `mmdet3d/ops`。
- 完整 8 卡 OD 评估结果：
  `work_dirs/shared_bev/westwell/map_od_two_stage/eval_epoch20_od_8gpu_cuda113_no_benchmark_full/od_results.pkl`；
  日志中未检出 `N > 0`、`CUDNN_STATUS`、`illegal instruction`、
  `illegal memory` 或 `VoxelizeGuard`。

## Decisions

- 保留现有 OD/Map 独立 batch 的 1:1 交替更新，不将两类样本拼入同一 batch。
- 使用任务独立的源相机列表和逻辑槽位；不通过黑图或伪标定补齐相机数。
- 不重新生成 PKL；相机筛选和别名统一在数据 pipeline 完成。
- 四相机部署使用独立 ONNX/TensorRT profile，不复用三或五相机 engine。
- 长训练建议增加 `--no-validate`，训练只定期保存普通 checkpoint；Map 和 OD
  使用两个独立的 `maptr_test.py --task ...` 作业评估，单项失败不会中断训练。
- 不保留或引入 voxel x/z 自动交换。坐标交换属于损坏的 CUDA 输出，后处理
  猜测会掩盖二进制环境问题。
- 4090_8 的多卡训练和评估配置固定使用 `cudnn_benchmark=False`；不使用
  `CUDA_LAUNCH_BLOCKING=1` 作为常规方案。
- 正常运行不依赖 voxel retry 或 CPU fallback；最终验证显式将两者关闭。

## Open questions / handoff

- 四相机部署的实际源相机名称、逻辑槽位和固定顺序尚待确认。
- 四相机 engine 落地时需清除 C++ runtime 示例中的 `num_camera=5` 硬编码。
- Map 分离评估仍需在 4090 的实际 Map 验证 PKL 上完成一次端到端运行；OD
  分离评估已经完整通过。
