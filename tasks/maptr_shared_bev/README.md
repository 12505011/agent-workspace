# Task: maptr_shared_bev

## Goal

设计并实现共享图像/BEV主干的 OD + MapTR 多任务训练，使不同任务能够使用不同相机集合。

## Scope

- 当前数据：`nuscenes_map` 与 `nuscenes_od`。
- OD 使用 `pkl_shared_bev_od_x0_54`；正式七类 Map 实验使用独立的
  `pkl_shared_bev_map_x0_54_7cls_stopline`，历史六类 PKL 保留用于复现。
- 当前 G/GN 方案为 OD 5 相机、MapTR 前视 3 相机。中央相机源名称不同：
  MapTR 为 `CAM_FRONT_TOP_MID`，OD 为 `CAM_FRONT_MID`。

## Current state

当前训练是基于 G24 分组 LR 的 fresh decoder-GN 实验，见
[experiments.md](experiments.md#current-decisions)。相机、数据、调度和 loss
权重继承 G24；只将共享 BEV decoder 的 BN 改为 GN。OD/shared LR=1e-4、
camera backbone=6e-5、Map head=2e-4，外层权重 1/0.12/0.04。以下 1:1 与
front3 描述是历史实验，不是当前启动默认值。

已在代码分支 `bev_3dod_maptr_shared_bev_mmdet3d` 实现源相机名称到逻辑
相机槽位的映射。联合训练使用两个独立 DataLoader 和交替 runner；早期 E/E2
采用严格 1:1，当前 G/GN 正式方案采用 OD:Map=16:1。
提交 `2044016` 将联合模型评估拆成 Map 与 OD 两套独立的数据集、任务路由、
指标和最佳 checkpoint 状态；独立测试进程可用 `--task map|object` 选择任务。

2026-08-29 已解决长期出现的 LiDAR voxel/spconv 多卡不稳定问题。问题不是
MapTR head、数据列数、相机数、NCCL 或 CUDA 源码差异，而是 CUDA 扩展的实际
编译工具链与 PyTorch 运行时不一致。当前 13 个扩展已统一使用 BEVFusion 容器
中的 CUDA 11.3/GCC 9.4 重新编译；8 卡评估另外固定关闭 cuDNN benchmark。

2026-09-04 增加了多任务采样比例/独立 batch size 的受控实验能力，以及训练、
评估和离线 TensorBoard 可视化脚本。2026-09-07 的实验审计表明，从头端到端、
OD:Map 更新频率 16:1 的 one-stage G 是当前最好的联合 Pareto 方案；详细设置、
逐实验结果与 Map 指标口径见 [experiments.md](experiments.md)。

## Key fixes and current handoff (2026-09-10)

### Data and evaluation contract

- 固定原始数据规模：OD 为 39,933 train / 4,374 val，Map 为 4,212 train /
  729 val；CBGS 后的 loader 长度不能当作原始样本数。联合模型必须分别使用
  OD val 与 Map val，历史上混用验证 PKL 得到的指标需要重新评估。
- Map 已恢复 `stop_line`，当前正式训练/评估采用 7 类。历史 Shared-BEV 六类
  mAP 与 Map-only 七类 mAP 不能直接比较；主指标为每类 AP@0.5/1.0/1.5 先求
  平均，再对全部配置类别（包括零 GT 类）求平均。
- `maptr_test.py` 强制通过 `--task object|map` 路由独立验证集和任务头；训练内
  验证也保存 OD/Map 独立 best 状态，避免两个任务互相覆盖 checkpoint。

### Training semantics and selected baseline

- 放弃表现不稳定的两阶段高频 1:1 联合微调，当前基线为 one-stage G：从头
  端到端训练、OD:Map=16:1、每个 task batch 各自一次 forward、backward 和
  optimizer step，不做跨任务梯度累积。
- 当前 G24/GN 延续 24 epoch、每 2 epoch 双任务评估、AdamW、warmup + 按
  iteration cosine。分组 LR 为 shared/OD/LiDAR `1e-4`、camera backbone
  `6e-5`、Map head `2e-4`；外层 loss scale 为 OD/Map/depth=
  `1/0.12/0.04`，depth 模块内部仍乘 3。
- 4-epoch G pilot 的 epoch 4 为 OD mAP/NDS `0.5651/0.5791`、Map mAP
  `0.4445`，是目前已验证的联合 Pareto 基线；24-epoch 结果必须与此使用同一
  数据、类别和评估口径后再比较。

### BN diagnosis and model-side fix

- 对同一 epoch-20 权重只重算 BN running statistics（不反传、不更新权重）后，
  Map 指标可大幅恢复而 OD 会下降，证明掉点不只是“Map 没学到”，共享 BN
  统计分布冲突是主要因素之一。
- 分模块校准确认 decoder 是最强冲突点：Map 约 `0.184 -> 0.447`，OD 约
  `0.610 -> 0.591`；camera、LiDAR encoder 次之，fuser 基本无贡献。全模型
  换 Map BN 会明显伤害 OD，因此不作为最终方案。
- 最终部署要求一个模型、一次共享前向同时输出 OD+Map，故 task-specific BN /
  双 checkpoint 只保留为诊断工具。当前结构性对照仅将共享 BEV decoder 的
  SECOND/SECONDFPN 从 BN 改为 GN32（eps `1e-3`），其余 camera、LiDAR sparse
  encoder、fuser 和任务头保持原状，从头训练；没有把全模型 BN 粗暴替换为 GN。
- decoder-GN 实验已通过 config、resume 和相关测试验证；当前训练从同目录
  `epoch_2.pth` 真正恢复 optimizer、LR scheduler、epoch/global iteration，
  而不是只加载模型权重重新开始。

### Runtime and tooling fixes

- CUDA `illegal instruction`/cuDNN 崩溃最终定位为扩展编译工具链与 PyTorch
  cu113 不一致；13 个扩展已用 CUDA 11.3/GCC 9.4 重编。8 卡常规运行固定
  `cudnn_benchmark=False`，不依赖 `CUDA_LAUNCH_BLOCKING=1`、voxel retry
  或 CPU fallback。
- 训练、评估、可视化均已有可编辑 shell 入口；使用短 `TMPDIR` 规避
  `AF_UNIX path too long`。离线 TensorBoard 转换会替换自身 event 快照，
  避免重复转换造成曲线回连到 step 0。
- 多任务日志现按同一全局窗口输出：`loss/overall` 是按实际 16:1 频率加权的
  训练目标，`loss/task_balanced=(loss/od+loss/map)/2` 仅用于等权观察；Map
  进一步拆成 head/depth 与 main/aux，`loss_raw/*` 为去除外层 scale 的量。
- 已定位一个尚未修复的展示 bug：compact logger 用后缀 `map` 搜索 OD mAP，
  会先匹配 `loss/map`，因此日志中的 `eval/od_mAP` 可能与 `loss/map` 完全相同。
  该字段当前禁止作为评估结果；真实 OD mAP 以独立 object 评估日志及
  `od_metrics.json` 为准。修复时应精确匹配 `object/map` 等评估 key，并补回归
  测试。

### Map projection / ego-pose conclusion

- Map→ego→camera 的投影链应对所有场站一致。mxvlkica 地图范围与 ego
  translation 相交，但其现有 `ego_pose.rotation` 解析后呈 body-Y-up，而
  nuScenes/MapTR 与单位 `LIDAR_TOP` sensor-to-ego 预期 body-Z-up。
- 曾尝试按 location/轨迹自动补约 57° yaw；该方法只能抵消表象并会掩盖数据
  生成错误，已在本地和 4090_8 完整撤回，未进入 MapTR 提交。下一步只检查
  定位 topic、时间同步、四元数 `xyzw -> wxyz` 写入和 localization-to-ego
  轴变换，不增加场站专用投影分支。

### Deployment handoff artifact (2026-09-10)

- 已将 4090_8 上 decoder-GN 实验的 `epoch_12.pth` 与同目录 saved config
  复制（非移动/删除）到本地镜像目录：
  `work_dirs/shared_bev/westwell/mxg128_reference_one_stage/one_stage_exp_g_decoder_gn_od5cam_map3cam_od16_map1_group_lr_w1_0p12_0p04_24e_bs4_w4/`。
- `epoch_12.pth`：503,454,341 bytes，MD5
  `c5d0f80ca8228f91ee754813cc058237`。
- `bevfusion_maptr_shared_bev_mxg128_reference_one_stage_exp_g_decoder_gn_24e.py`：
  153,233 bytes，MD5 `ac747192ade3d96cb591413542f32ed4`。两端大小与
  MD5 均一致，服务器原文件保留。
- work_dir 下的 `.py` 是 MMCV 展开的配置快照，部署导出时只用于核对模型结构；
  不能直接作为可执行配置。后续应选择本地 repo 中与 decoder GN、相机数、BEV
  尺寸、decoder 层数和类别数一致的源 config，再开始 ONNX/TensorRT 导出。

## Verified facts

- OD 分片 `0bf177fb36e24a28ac1f30891d07b88f` 使用直接根目录结构（无中间
  `nusc/`），包含 972 个 sample；`log.location=mxvlkica`，地图文件为
  `maps/expansion/mxvlkica.json`。相机通道为前中/前中左/前中右和后上左/右
  5 路。该分片没有 `maps/basemap/mxvlkica.png`。GT-only 矢量投影工具虽然
  能生成三前视拼图，但原始结果的地图几何投影明显错误，因此“成功生成文件”
  不能作为投影正确性的验证；问题输出为
  `work_dirs/mxvlkica_map_gt_projection/0bf177fb36e24a28ac1f30891d07b88f_example/1776705899.999728_surround_view.jpg`。
- `mxvlkica` 现有 30 个 OD shard 的 `ego_pose.rotation` 均呈 Y-up 语义：
  `body-Y` 与 `world-Z` 的绝对点积中位数约 0.94--0.95，且每个 shard 的
  up-axis winner 都是 Y；但 `LIDAR_TOP` 的 `calibrated_sensor` 是单位
  lidar-to-ego，MapTR/nuScenes 需要 Z-up ego，二者语义不一致。地图 node 与
  ego translation 的全局范围相交，所以不是拿错场地地图。Jinke 样例是 Z-up，
  但其 ego-pose 来源有过 `gnss/odom` 与 `localization/odom` 的特殊修正，不能
  直接作为墨西哥数据的固定旋转模板。应优先修复/重生成 ego pose 来源或明确
  Y-up 到车辆 Z-up 的外参；单独调 `map_z` 无法解决该问题。
- Map 到 ego 再到 camera 的投影公式应跨场站保持一致。2026-09-10 曾验证过按
  location/轨迹自动附加 yaw 可以在单个 mxvlkica 样例上抵消约 57° 的表象，
  但该方案会掩盖 `ego_pose.rotation` 的生成错误，已完整撤回且未提交。后续
  应对齐原始定位四元数、nuScenes `wxyz` 写入和 localization-to-ego 轴变换，
  不在 Map 转换或可视化阶段增加场站专用旋转分支。
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
- 联合配置分别定义 `map_camera_slots` 和 `od_camera_slots`；历史 front3 pilot
  两者均为 3 路，当前 G/GN 已扩展为 OD 5 路、MapTR 3 路。
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
- `AlternatingTaskEpochBasedRunner` 新增 `object_steps_per_map`：在
  `epoch_size="object"` 下可按 N 次 OD 更新后做 1 次 Map 更新；每个 task batch
  仍各自执行一次 forward、backward 和 optimizer step，不是梯度累积。
- `data.task_samples_per_gpu` 可分别设置 OD/Map 的 batch size；只允许用于两个
  dataset 的 alternating training，并按 `[object, map]` 顺序解析。
- 实验 F 配置使用 OD:Map 更新数约 16:1、OD batch 8/卡、Map batch 4/卡；
  2680 个 OD step 对应 168 个 Map step 和 2848 个总 step。
- Stage1 E2 保持严格 OD:Map 1:1 独立更新，将学习率改为 `1e-4`、500 iter
  linear warmup 后单调 cosine 衰减，最低比例 0.01；它用于隔离旧 cyclic 峰值
  对 Map 指标下降的影响。
- Stage2 D-Frozen 继承 D 的 OD+Map+depth、严格 1:1、4 epoch 设置，唯一训练
  差异是冻结 `encoders.lidar`（包括其 BN eval 状态）；初始化 checkpoint 为
  mxg128 reference Stage1 epoch 18 best-object。
- `tools/3dod_maptr/train_shared_bev_experiment.sh` 将 config、GPU、验证开关、
  resume 和输出目录集中在可编辑区，并使用较短 `TMPDIR` 避免 AF_UNIX 路径过长。
- `tools/3dod_maptr/eval_shared_bev_checkpoint.sh` 可独立开关 OD/Map 的 8 卡评估，
  分别使用 `--task object --eval bbox` 和 `--task map --eval chamfer`。
- `tools/3dod_maptr/convert_log_to_tensorboard.py` 可把既有 MMCV `.log.json`
  转为 TensorBoard scalar event，并用同名 `.log` 恢复准确 epoch 长度/global
  step；指标按 OD、Map、depth、optimizer、time 和 system 分组。
- 直接运行环境里的 `tensorboard` 会动态加载 Open3D 插件，并因缺少 `plotly`
  启动失败；转换工具改为只加载 TensorBoard 内置插件，不修改 Open3D/训练环境。
- 重复转换曾在同一 run 中追加多份完整 event，导致 Scalar 曲线从末尾连回
  step 0、出现大斜线。现在每次转换只替换输出 run 下自己的
  `events.out.tfevents.*`，不会修改原始 `.log` 或 `.log.json`。
- `tools/3dod_maptr/visualize_training_log.sh` 集中设置 work dir、指定日志、输出
  目录、host/port 和 convert/serve 模式；默认以 `load_fast=false` 启动。

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
- 4090_8 上 `tests/test_alternating_task_schedule.py` 与
  `tests/test_alternating_task_dataloaders.py` 各 1 项通过，覆盖 16:1 task
  schedule 和 OD/Map 独立 batch size。
- 4090_8 上 TensorBoard 转换测试 9 项、shell wrapper 测试 2 项全部通过；
  覆盖真实 event 回读、global step、同名文本日志 epoch size、动态插件隔离、
  `load_fast=false` 和重复转换不产生重复 step。
- 当前 Stage2 D-Frozen 日志已成功转出 TensorBoard 数据；后端验证可见 run
  `20260904_125808` 和 35 个 scalar tags，`Scalars` 面板已有有效数据。
- Map Chamfer 评估在 0.5 m、1.0 m、1.5 m 三档阈值分别计算 AP；每类先对三档
  AP 求平均，最终再对配置中的全部类别求平均。
- 历史 Map-only epoch 22 的 0.6456 使用 7 类（包含 `stop_line`），历史
  Shared-BEV/G4 使用 6 类，因此不能直接比较；新的 G24 已采用独立七类数据和
  7 类 head 配置，不改写历史六类数据。
- One-stage G 4-epoch pilot 的 epoch 4 达到 OD mAP 0.5651、NDS 0.5791、Map
  mAP 0.4445；四轮内两个任务的指标均单调上升。
- MapTR 提交 `3b44a8d`，后续由 `e373368`、`84691ff`、`91b66ed` 完善的独立
  4-epoch 前视相机/权重 pilot：OD 与 Map 每个
  batch 都固定输入 3 路前视相机。两者共享左右相机，但中央源分别为
  `CAM_FRONT_MID` 与 `CAM_FRONT_TOP_MID`，所以跨任务共涉及 4 个物理相机名，
  不是单个 batch 输入 4 路。OD:Map 更新频率保持 16:1；最终外层 loss scale 为
  `object=1, vectormap=0.5, depth=0.5`，DepthLSS 内部权重仍为 3。Map 中央相机
  临时恢复 Map-only 的固定 stretch，关闭该相机的旋转、垂直平移和翻转。优化器
  base LR 为 `1e-4`，Camera backbone 为 `6e-5`、Map head 为 `6e-4`，其余模块
  为 `1e-4`；使用 500 iter warmup + cosine、min ratio `0.001`。配置解析和实际
  dummy optimizer 参数组验证通过；4 epochs、每 epoch 双任务评估及七类 Map PKL
  均正确。
- MapTR 提交 `11430bc` 为新的 G24 恢复 `stop_line`：converter 保留并抽取
  Westwell `line_token` stop line，离线数据集映射为 label 6，G24 head/coder 为
  7 类并指向独立 PKL 目录。4090_8 已同步，stop-line 两项单测和配置解析通过；
  七类 PKL 已生成并验证：4,212 train / 729 val、token 零重叠，stop-line 实例
  分别为 684/61，运行时 pipeline 能将其转换为 label 6。
- MapTR 提交 `51cc71e` 为 `maptr_visualize.py` 增加 `--task map|object`，可从
  联合配置的 `data.<split>.map/object` 中选择对应验证集，并让联合模型只运行所选
  推理头；脚本通过 `py_compile` 和 `git diff --check`。
- MapTR 提交 `0931d7e` 增加 `tools/3dod_maptr/visualize_shared_bev_checkpoint.sh`；
  默认可视化 G4 epoch 4 的 Map 三相机结果，checkpoint、任务、GPU、样本范围和
  输出目录集中在脚本顶部修改，且使用短 `TMPDIR` 避免 AF_UNIX 路径过长。
  后续提交 `49f5e00` 移除命令行环境变量覆盖；`TASK=map/object` 会分别设置 Map
  GT/阈值或 OD 框阈值，启动命令始终保持不变。
- 上述可视化 Python 和 shell 脚本已同步到 4090_8 的
  `/storage/disks/d0/lelin/maptr/tools/3dod_maptr/`；服务器端 `py_compile` 与
  `bash -n` 通过，本地/远端 SHA-256 完全一致。
- 2026-09-08 修正联合 checkpoint 的相机 Map 可视化：旧实现的 `--show-gt`
  只在 BEV/map 面板绘制 GT，`camera-*` 实际只有预测。提交 `e875088` 恢复
  Map-only `vis_mAP_epoch_22_val_raw_fixed` 的约定：原图上预测为同类实色实线、
  GT 为同类浅色虚线，二者共用 PKL 中原始 `lidar2img` 和 `map_z=0.0`；同时
  修正 OpenCV BGR 颜色并补齐 7 类颜色。默认 launcher 将完整 729 帧写入新的
  `vis_epoch_4_val_raw_fixed`，避免与旧错误目录混合。服务器端原始 GT 读取及
  虚线渲染 smoke test 通过，本地/远端脚本 SHA-256 一致。

## Decisions

- 保留 OD/Map 独立 batch 和每 batch 一次独立更新的语义；当前联合训练优先采用
  16:1 更新频率，不将两类样本拼入同一 batch。
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
- 训练日志可视化采用离线转换，不要求重新训练或提前启用
  `TensorboardLoggerHook`；重复运行必须保持同一 run 只有一个完整 event 快照。
- 当前多任务采样实验继续保持“一份 task batch 对应一次独立参数更新”的语义；
  调整 OD:Map 比例时不暗中改为两次 forward、一次 backward。
- 最新 G24 分组 LR 方案采用 `vectormap=0.12、depth=0.04`；保留原 G 的
  depth 强度，适度增加 Map 监督和私有头 LR。历史 front3 的 0.5/0.5 和
  Map head 6e-4 组合在前两轮表现不佳；多个变量同时改变，不能归因为单一参数。

## Open questions / handoff

- 官方 nuScenes 联合基线已在 MapTR 分支
  `bev_3dod_maptr_shared_bev_nuscenes` 配置完成：OD 保持 +/-54 m，Map range 为
  `[-30,-15,-2,30,15,2]`，MapTR decoder 6 层，六路相机、10 类 OD anchors、
  3 类官方 Map、shared decoder GN。官方数据同帧联合训练，不使用 16:1
  alternating runner；详见 `experiments.md` 的 official nuScenes 条目。
- 四相机部署的实际源相机名称、逻辑槽位和固定顺序尚待确认。
- 四相机 engine 落地时需清除 C++ runtime 示例中的 `num_camera=5` 硬编码。
- decoder-GN 长训练需继续每 2 epoch 用独立 OD/Map 验证集评估；重点观察
  epoch 10 以后 Map 是否再次降到 0.1x，同时确认 OD 是否保持 G 基线附近。
- 修复 compact logger 的 `eval/od_mAP` 后缀误匹配，并增加“训练 loss key 不得
  被识别成 eval key”的回归测试。
- 定位并修复 mxvlkica `ego_pose.rotation` 的生成链；在修复前，不用自动 yaw
  补偿生成新 Map PKL，也不把错误相机投影用于判断模型质量。
- TensorBoard `Scalars` 已验证；2.14 的 `Time Series` 页面曾显示 `No Runs`。
  已关闭实验性 fast data server，但重启后的 Time Series UI 结果仍待人工确认。
- 本地 MapTR 工作区截至 2026-09-10 仅有用户持有的
  `tools/3dod_maptr/maptr_visualize.py` 未提交修改；后续提交不得误带入。
