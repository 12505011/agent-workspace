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
