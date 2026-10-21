# 认可联合epoch11与新二阶段epoch3对比

## 身份与验证范围

- 用户复看确认旧好版本未见此前凭空误检；属于人工视觉反馈，不是认证零FP率。
- 旧可视化/完整评估 `job-fa6183a93a61a1b2b28e87a1`，父训练 `job-4eb88b7f2b38f52a3b329ea5` epoch11，checkpoint SHA `db2c5fc2b14acedbc316071eec1e9a130046f775aab67077936c45d568aa1517`。
- 新可视化 `job-15f55956ab3cbd57e09f4a30` 已SUCCEEDED，父训练 `job-a83f70fa7a1ada448e0d8395` MAP最佳epoch3，checkpoint SHA `2f68967fd8cd85ea53e4fff0d5d9e5adf2832b631185c14dd3f78cb599ac57c8`。
- 两版MAP729帧token集合相同、OD阈值.6/MAP.4；都完成BEV+三相机2916PNG，optimizer/calibration为0，推理模型及checkpoint不变。旧多卡分片导致文件编号不同，须按token后缀匹配，不按编号。
- 原OD/MAP train/val PKL与MAP GT内容SHA相同；旧OD训练为90496帧预算子集，新为90558帧全量（差62帧），MAP训练7533、MAP验证729、OD验证8100相同。相机裁切/验证pipeline、十类OD映射和anchor尺寸相同。

## 实际配置和成绩

| 项目 | 旧认可epoch11 | 新二阶段epoch3 |
|---|---|---|
| 初始化 | 旧纯LiDAR OD16部分迁移，camera neck/Fuser/MAP新建；R50预训练 | 新三相机+LiDAR融合OD最佳14完整迁移，仅MAP新建 |
| 体素xy/z | .075/.2 | .1/.2 |
| OD:MAP更新 | 4:1 | 1:1 |
| 联合阶段实际更新 | OD31097、MAP7777 | OD8490、MAP8490 |
| 联合轮数 | 11 OD-defined epoch | 3/4 OD-defined epoch；3轮约36次MAP采样遍历 |
| 卡数/每卡batch/globalbatch | 16/2/32 | 32/1/32 |
| 基础LR / MAP LR | 1e-4 / 2e-4 | 2e-5 / 1e-4 |
| OD mAP / NDS，8100验证帧 | 55.73% / 58.34% | 41.62% / 45.46% |
| MAP AP@.5，729验证帧 | 34.19% | 30.46% |
| MAP三距离均值 | 47.36% | 39.24% |

- 基础LR来自父保存实际config，旧组是1e-4，不是2e-4；旧MAP倍率2，新倍率5。
- 两者均无CBGS、共享原生BN、无MAP专用BN bank或额外校准、全部学习参数解冻、camera norm_eval=True、GN decoder/Anchor3DHead/MAP6层20点、静态loss权重object1/map.12/depth.04，无GradNorm/PCGrad。融合目标网格均180×180。
- 另有初始化差异：旧组未启用fresh MAP native init，新组启用；不据此主张旧初始化更正确。
- 旧epoch11有11次AMP跳过OD更新，非严格等预算；其完整独立评估已通过显式审计。新4轮训练日志有5个非finite梯度窗口，窗口数不能视为实际AMP跳过数。

## 同帧观察与边界

- 全729帧阈值以上OD框总数旧4643、新6468（+39.31%）；这不是FP计数。
- token `a7fb017f6144555187224b8d162d3e79`：旧12框、新36框。旧文件前缀000009，新000073；源run `map_jinke58_67d96d9d7072406981aa694c667c338f`。
- token `0809a38698dacbdec40fad304269d5e3`：旧8框、新29框。旧前缀000008，新000069；同源run。
- 人工抽看上述两对camera-0和BEV：新模型出现旧模型没有的道路区域Truck_head/Vehicle/Rtgc密集框，BEV同样存在，不只是相机投影或显示阈值变化。再抽看固定首/中/末帧，退化不是每帧都出现；不能据5帧认证全量FP率。
- camera绘框颜色部分不同，BEV类别配色与实际类别配置相同；不能仅靠蓝色判定类别或类别映射错位。

## 当前结论

- 旧共享BEV/共享BN双头模型存在用户认可且指标更好的结果，不能把共享BN本身认定为这次误检的充分或唯一根因。
- 当前二阶段不是旧稳定配方的单因素复刻：初始化、更新比例、LR、联合优化预算、体素、局部BN每卡batch均不同。较高MAP批次占比可能改变共享梯度和BN域统计，但目前只是候选解释，没有因果消融结论。
- 新MAP并非只训练了3遍：MAP更新8490次、比旧7777次多；不能简单归因于MAP epoch不足。也不能据联合OD更新更少宣称总OD预训练量更少。
- 本次只读比较既有产物并记录，没有改训练代码、提交云任务、续训、commit或push。

## 平台图片位置

- 旧好版：`/mnt/storage/me/runs/work_dirs/mapod_joint_epoch11_fullval_images_20261007/job-fa6183a93a61a1b2b28e87a1/validation/map/frames/`。
- 新版：`/mnt/storage/me/runs/work_dirs/stage2_epoch3_jinke_val729_od06_map04_images_20261008/job-15f55956ab3cbd57e09f4a30/joint_epoch_3/`。
- 两者子目录均有 `bev/camera-0/camera-1/camera-2`。
