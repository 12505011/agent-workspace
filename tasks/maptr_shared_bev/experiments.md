# Shared-BEV experiments and metric contract

本文只记录已经由配置、训练日志或评估日志验证的实验事实。不同数据划分、类别
集合、评估 pipeline 或代码版本得到的数字不得直接横向比较。

## Canonical datasets

- mxg128 OD 原始划分：39,933 train / 4,374 val，比例约 9.13:1。
- Map 原始划分：4,212 train / 729 val。
- OD 的 CBGS 重采样长度不是原始训练集大小，不能拿它描述 train/val 比例。
- 联合模型评估必须按任务选择独立数据集：OD 使用 4,374 帧 OD val，Map 使用
  729 帧 Map val。

## MAP metric contract

Map 使用对称 Chamfer 距离。开启
`eval_use_same_gt_sample_num_flag=True` 时，每条预测线和 GT 线均匀重采样到 100
个二维点。预测线 `P` 和 GT 线 `G` 的距离为：

```text
D(P,G) = 0.5 * (mean_p min_g ||p-g|| + mean_g min_p ||g-p||)
```

对每个类别和每个阈值 0.5 m、1.0 m、1.5 m，预测按置信度排序并在单帧内与 GT
贪心一对一匹配；同一个 GT 的重复匹配计为 FP。汇总整个验证集的 precision / 
recall 曲线后，用曲线下面积得到 AP。

每类最终 AP 是三档距离阈值 AP 的算术平均；最终
`NuscMap_chamfer/mAP` 再对配置的全部 Map 类别做算术平均。数据集最终汇总会让
零 GT 类以 AP=0 参与该平均，而单个阈值打印出来的表格 mAP 只对有 GT 类求平均，
两者不要混用。

### Historical Map-only epoch 22

来源：
`work_dirs/maptr_only/maptr_long_range_55m_crop24e_live_depth/20260820_202527.log`
中的 epoch 22。该历史配置使用 7 类：`divider`、`ped_crossing`、`boundary`、
`centerline`、`bar_markings`、`bar_markings_curve`、`stop_line`。

| Class | AP@0.5 | AP@1.0 | AP@1.5 | Three-threshold AP |
| --- | ---: | ---: | ---: | ---: |
| divider | 0.7200 | 0.9647 | 0.9778 | 0.8875 |
| ped_crossing | 0.7553 | 0.9184 | 0.9861 | 0.8866 |
| boundary | 0.6281 | 0.9235 | 0.9563 | 0.8360 |
| centerline | 0.9348 | 0.9896 | 0.9969 | 0.9738 |
| bar_markings | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| bar_markings_curve | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| stop_line | 0.8254 | 0.9900 | 0.9900 | 0.9351 |

最终结果的直接验算为：

```text
(0.8875 + 0.8866 + 0.8360 + 0.9738 + 0 + 0 + 0.9351) / 7
= 0.64557 -> 0.6456
```

历史 Shared-BEV 实验（包括 G4）只有前 6 类，不含 `stop_line`。如果只对
Map-only epoch 22 日志做六类重聚合，结果约为 0.5973；这只是统一类别分母后的
辅助比较，不是重新评估。新的 G24 配置改为 7 类，并使用独立重生成的 Map PKL，
以免破坏历史六类 checkpoint 的可复现性。

## Verified experiment results

以下 OD 数字为 mAP / NDS，Map 数字为 `NuscMap_chamfer/mAP`。

| Experiment | Initialization and schedule | Best/observed result | Conclusion |
| --- | --- | --- | --- |
| Stage1 OD-only LiDAR | OD-only，20 epoch | epoch 18: OD 0.6266 / 0.6128 | 当前 LiDAR-only OD 基线峰值 |
| Stage1 E | LiDAR OD+Map，严格 1:1，cyclic | epoch 6: OD 0.4621 / 0.4708，Map 0.3801；epoch 8 Map 0.1676 | 1:1 高频 Map 更新和激进 cyclic 组合不稳定 |
| Stage1 E2 | LiDAR OD+Map，严格 1:1，cosine | epoch 6: OD 0.3923 / 0.4263，Map 0.2246 | 仅换低峰值 cosine 没有解决 1:1 采样失衡 |
| Stage2 A | OD-only Stage1 e18 初始化，Stage2 OD-only，LiDAR 可训 | epoch 4: OD 约 0.6229 / 0.6126 | camera/fuser 本身不会必然破坏 OD |
| Stage2 D | OD-only Stage1 e18，OD+Map+depth 1:1，LiDAR 可训 | epoch 2: OD 0.5502 / 0.5626，Map 0.1170 | OD-only 表征直接加入高频 Map 更新时冲突明显 |
| Stage2 D frozen | 同 D，但冻结 LiDAR | epoch 2: OD 0.5512 / 0.5645，Map 0.0706 | 冻结 LiDAR 没有解决冲突，Map 更难适配 |
| Stage2 E | joint Stage1 初始化，分组 LR，OD 5 cam / Map 3 cam | epoch 2: OD 0.4700 / 0.4912，Map 0.4383 | joint 初始化能保留 Map，但 OD 上限仍低 |
| One-stage G | 从头端到端，OD:Map 更新 16:1，cosine，4 epoch | epoch 4: OD 0.5651 / 0.5791，Map 0.4445 | 当前最好的联合 Pareto 方案，两个任务从 e1 到 e4 均持续上升 |

## Decoder-GN G24 versus historical Map-only (2026-09-11)

同为七类 Map 主指标时，decoder-GN 联合实验的最佳 Map 为 epoch 16 的
`0.5852`，随后 epoch 18/20/22 分别降至 `0.5388/0.5170/0.5080`；对应 OD
mAP 在 epoch 20 达到 `0.6174`。历史 Map-only 在 epoch 22 达到 `0.6456`。
因此联合最佳相对 Map-only 低 0.0604，而不是拿末轮 0.5080 得出的 0.1376；
联合模型应按双任务 Pareto checkpoint 选择，不能默认取最后一轮。

两者 MapTR head 都是四层 decoder、40 vectors、每条 15 点、七类和相同的
cls/pts/dir/seg loss，但其余训练合同并不相同：

- Map-only 是 camera-only，Map head 内的 `LSSTransform` 直接产生 256-channel
  `17x46` BEV；联合模型先用外部 `DepthLSSTransform`，再与 LiDAR 融合并通过
  shared SECOND/SECONDFPN，Map head 接收裁剪后的 512-channel `34x90` BEV。
- Map-only 中央相机为 `CAM_FRONT_MID` 且使用 stretch；联合 Map 中央相机为
  `CAM_FRONT_TOP_MID` 且使用 528-pixel letterbox，并带轻量旋转/垂直平移增强。
  两者数据根目录与前向范围也分别为 Jinke x0--55 和 shared Map x0--54，验证
  GT 数量接近但并非完全一致。
- Map-only base/Map-head LR 为 `6e-4`，camera backbone 为 `6e-5`；联合模型
  camera backbone 同为 `6e-5`，但 Map head 为 `2e-4`，camera neck、DepthLSS、
  fuser 和 shared decoder 为 `1e-4`。联合 cosine 按全部 OD+Map global steps
  前进，而不是按 Map update 单独前进。
- Map-only 的 vectormap 外层 scale 为 1，depth 默认外层 scale 也是 1，内部
  depth 权重为 3；联合为 vectormap `0.12`、depth `0.04`，内部仍为 3。因此
  联合把 raw depth 相对 Map-head 的比例从约 3:1 改成约 1:1，并没有保持
  Map-only 的内部相对权重。
- Map-only loader 每 epoch 132 step；联合每 object-defined epoch 执行 362 个
  Map step。因此联合每个名义 epoch 约等于 2.75 个 Map 数据 epoch，epoch 8
  已约等于 Map-only 22 epoch 的 Map update 数，24 epoch 总计约 66 个 Map
  数据 epoch。epoch 16 后退化不能解释为 Map 更新次数不足。

该对比说明 decoder GN 消除了早期 0.1x 级崩坏，但剩余差距同时包含不同输入
表征/相机与数据、共享梯度冲突、Map-private LR 较低、depth 相对配比改变和后期
重复训练；不能把它单独归因于 Map 数据少或某一个 loss 权重。

## One-stage G update semantics

- `object_steps_per_map=16` 表示 16 次独立 OD 参数更新后做 1 次独立 Map 参数
  更新。
- 每个 iteration 都是一次 forward、一次 backward、一次 optimizer step；没有
  跨任务梯度累积，也不是“两次前向、一次反向”。
- batch size 为每卡 OD=4、Map=4，8 卡全局 batch 均为 32。
- 每个 object-defined epoch 为 5,788 个 OD step、362 个 Map step，共 6,150
  次参数更新。Map 每 epoch 约见到 11,584 个样本，相当于遍历 4,212 帧训练集
  约 2.75 次；4 epoch 合计约 11 次。
- loss 外层缩放为 OD=1.0、Map=0.06、depth=0.04；depth 模块内部再乘 3，因而
 有效 depth 比例为 0.12。
- 优化器为 AdamW，基础 LR `1e-4`，500 iter linear warmup，之后单调 cosine，
  `min_lr_ratio=0.01`。

## Current decisions

- 2026-09-09 decoder-GN G24 已从同目录 `epoch_2.pth` 配置为真正的
  `resume_from` 续训：恢复模型、optimizer、LR scheduler、epoch 和 global
  iteration，下一轮从 epoch 3 开始并保持原 24-epoch horizon、每 2 epoch
  评估。启动脚本仍保留 `ALLOW_EXISTING_RUN_DIR=0`；非空 `RESUME_FROM` 会显式
  允许复用同一 work_dir。4090_8 已确认 checkpoint 非空、配置总轮数 24、评估
  interval 2，shell 语法与相关 5 项测试通过；未由 agent 启动训练。
- 2026-09-09 为 alternating multi-task runner 增加按同一全局 iteration 窗口
  聚合的紧凑日志。旧 MMCV `LogBuffer.average(n)` 对稀疏 key 各自取最近 `n`
  次出现，在 16:1 调度下会把 50 个 OD batch 与约 850 个全局 step 内的 50 个
  Map batch 放在同一行，不能直接比较。新日志区分 `loss/overall`（真实调度加权
  目标）、`loss/task_balanced`（OD/Map 等权诊断值，不参与反传）、`loss/od`、
  `loss/map`、Map head/depth/main/aux、去除外层 scale 的 raw loss、实际任务占比
  和 grad norm；精确为零的聚合项不打印。Map 评估改为一张 AP@0.5/1.0/1.5
  表，同时明确 `mAP(active GT)` 与历史主指标 `mAP(all configured)`；测试脚本
  不再向终端倾倒完整 metrics dict，而是在结果目录保存 `od_metrics.json` 或
  `map_metrics.json`。4090_8 的 `maptr` 环境完整单测 46 项通过，新增核心测试
  6 项通过；本地/远端 8 个关键文件 SHA-256 一致。该改动只改变日志与展示，
  不改变 loss、反传、优化器更新或评估数值。
- 2026-09-09 新建 fresh decoder-GN 对照配置：只将共享 BEV decoder 的 SECOND
  与 SECONDFPN 归一化由 BN 改为 GN32（eps=1e-3）；camera、LiDAR sparse
  encoder、fuser 与任务头归一化保持参考配置。训练仍从头开始，继承 G24 的
  16:1、group LR、loss scale、24 epoch cosine 和每 2 epoch 评估设置。
- 2026-09-07 新建 G24 分组 LR 方案（待训练验证）：
  `bevfusion_maptr_shared_bev_mxg128_reference_one_stage_exp_g_joint_group_lr_24e.py`。
  shared/OD/LiDAR LR=1e-4，camera backbone=6e-5，Map head=2e-4；外层
  OD/Map/depth=1/0.12/0.04，depth 内部仍乘 3。16:1、OD 5cam/Map 3cam、
  Hybrid-A、七类 PKL 不变；seed=0，2000 全局 iter warmup，显式
  by_epoch=False cosine、min ratio=0.01；24 epochs、每 2 epochs 双任务验证。
  独立目录为 `one_stage_exp_g_od5cam_map3cam_od16_map1_group_lr_w1_0p12_0p04_24e_bs4_w4`。
  此选择加强 Map 私有头而保持旧 G depth 强度，不是声称 Map/depth 梯度已平衡。
  MapTR 提交 `77f9e77` 已推送；配置、sh、测试和 README 通过 rsync 同步至
  4090_8。本地 `python tests/test_shared_bev_g24_group_lr_config.py -v` 两项
  通过，验证真实 MMCV optimizer 参数组、调度上下界/连续衰减以及数据/模型继承；
  Python/shell 语法与 diff 检查通过。服务器 SSH 恢复后相同两项测试和 shell
  语法检查亦通过；新配置及训练 sh 的本地/远端 SHA-256 一致。
  未启动或停止任何训练。
- 审计纠正：OD-only `stage1_lidar_od_20e_bs8_w8_v3` 日志显示 cyclic LR
  从 1e-4 升到 1e-3（epoch 8/9），此前仅比较 optimizer.lr=1e-4 不充分。
  旧 G4 每个 epoch 的 LR 基本恒定，符合 MMCV `by_epoch=True` 默认；新方案
  明确为逐 iteration 调度。AdamW 下不得把 loss scale × LR 或累计 LR
  当作真实更新倍数/等效训练时长。front3 同时改变多项变量，失败根因仍未隔离。
- 联合训练优先继续验证 one-stage + OD:Map=16:1；不回到严格 1:1，也不回到会
  将 `1e-4` 基础 LR 放大到更高峰值的旧 cyclic 策略。
- 24 epoch 扩展实验每 2 epoch 保存并分别评估 OD 与 Map；先核对 epoch 2/4
  是否复现 4-epoch pilot 的轨迹，再决定是否持续到 24 epoch。
- 不能只看总 loss 判断任务是否训练良好；OD mAP/NDS 与 Map mAP 都必须独立
  监控。
- Map-only 7 类结果与 Shared-BEV 6 类结果必须标注类别集合，不能直接用一个
  mAP 数字下结论。
- 新的七类训练必须同时满足四项：converter 能抽取 Westwell `line_token` 形式的
  stop line、离线数据集将其映射为 label 6、Map head/coder 输出 7 类、train/val
  PKL 与验证 JSON 均重新生成。只改 config 会得到无 GT 的空类别。
