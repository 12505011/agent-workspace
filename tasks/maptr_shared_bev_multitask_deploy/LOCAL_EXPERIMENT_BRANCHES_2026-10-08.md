# 本地实验分支与纯LiDAR OD0.1重训

用户要求各实验保存到独立本地分支，不push；跳过云端短测。与今日比较记录配合使用。

## 分支

| 仓库 | 分支 | 本地提交 | 用途 |
|---|---|---|---|
| `/data/baize/baize-welldriver/code/bevfusion` | `exp/od-lidar-reference075` | `5f8bdf5` | 旧纯LiDAR单OD0.075、32卡参考 |
| 同上 | `exp/od-lidar-voxel01` | `0905ea4` | 纯LiDAR单OD0.1、8卡16轮，新正式任务 |
| `/data/baize/baize-welldriver/code/maptr` | `exp/mapod-reference075-od4map1` | `225f6a2` | 旧认可联合epoch11的0.075、4:1配方与权重身份 |
| 同上 | `exp/mapod-fusion-odinit-voxel01` | `df623ee` | 当前融合OD14初始化、0.1/1:1/4轮配方，已完成a83f |
| 同上 | `exp/mapod-lidar-odinit-voxel01` | `0158715` | 旧纯LiDAR OD16初始化的0.1/1:1/4轮准备配方，未提交 |

- 每个分支的 `raytrain/EXPERIMENT.md` 固定用途、配方、初始化及入口；公共驱动保留独立recipe，切分支不会改已提交云快照。不把保存配方的参考分支称为旧快照逐字节复原。
- 所有提交仅本地，无Git push；MapTR保存84个已积累的相关RayTrain源码/配置/回归，未提交部署导出和converter修改。BEVFusion保存16个RayTrain入口/配方/回归文件，未提交visualize/converter改动。未修改原业务分支指针，相关无关工作树改动仍保留。
- 独立审查发现custom PKL生成输出路径的未resolve前缀校验可越界；第三上下文修复为resolved strict descendant，新增..及symlink逃逸回归。该脚本本次训练不调用。31 BEVFusion、156 MapTR RayTrain本地测试通过，含实际SECOND/FPN CPU空间前向；不是CUDA/DDP短测。

## 新纯LiDAR正式任务

- `job-ceee66eddaf1452d678c609f`，名称 `od-lidar-voxel01-aligned-16e-8gpu-20261008`；已提交，首次核验PROVISIONING、Ray已启动，训练业务更新尚未确认。
- 用户要求先纯LiDAR OD0.1，不是已完成三相机融合OD de12；camera/Fuser/MAP均不构建，fresh训练，不加载父0.075pth、不resume。
- 基准 `job-85ea81db448753bc4c584a08` 实际config.py；本机make_config默认与保存配方一致，仅runtime路径/评估收集参数不同。运行时只读挂该任务精确目录用于 `--align-reference`，不会迁移checkpoint。
- 原BEVFusion镜像：`harbor.wellspiking.ai/guofeng.su/ray-train-bevfusion@sha256:66b906d062870131121b07e4455783dc5f2913e285b29fdbb2cf1decc100f553`；不是MapTR Torch2镜像。1×8GPU/48CPU192Gi/ray-ddp torchrun/normal，input=my-storage/workspace。
- 原四场地OD90558/8100和同PKL SHA、原BN/Anchor3DHead/类别/anchor/GT bottom-centre/点云增强/AdamW4e-4/cyclic LR/AMP，无CBGS，16轮每轮验证保存/MLflow。
- 改动：xy体素0.1；每卡batch8、累积4，名义有效batch256，保留原每卡BN单批样本数。世界数/采样补齐/微迭代与epoch边界累积不同，不宣称与32卡逐步等价。
- 无Fuser时 sparse1080→BEV135，原SECOND/FPN两路135/136无法拼接；CPU测试先复现失败再修正派生稀疏canvas为1088×1088×41→BEV136。物理范围[-54,-54,-1,54,54,7]与neck/anchor参数不变；anchor铺满原108m的136格间隔约0.794m，并非精确0.8m或旧0.6m。当前变更限于config几何，无新neck。
- 入口：`raytrain-bevfusion-prepare python3 raytrain/train_od.py --voxel-xy 0.1 --align-reference`。
- 输出：`/mnt/storage/me/runs/work_dirs/od_lidar_voxel01_aligned_nocbgs_16e_8gpu_20261008/job-ceee66eddaf1452d678c609f/`。epoch/best/SHA、config、日志和mlflow-status平铺沿用原driver。
- 从干净detached worktree `c0f3ff5` 提交（之后0905ea4只修正文档中的CLI选项），未将用户未提交的visualize/converter改动打包。临时源 `/tmp/od-lidar-voxel01-submit.JL5DTs/source`，先保留，当前训练快照不依赖本地后续切分支。
- 首次CLI带 `--max-failures 0` 被ray-ddp参数检查拒绝，未产生job；删除该不支持选项后成功提交上述唯一任务。没有升级CLI、没有云端短测或重复正式任务。

## 后续实际启动核验

- ceee已RUNNING；8个rank均OD_RANK_READY、全90558帧。`OD_REFERENCE_ALIGNMENT_VERIFIED` 与产物reference-alignment.json均PASS，旧保存config SHA `01bb50cb037a6b988d3a37521ce7cc3bc267b43d41e578bba779f6c56aedf189`，明确仅voxel/derived_sparse/world/accum变化，exact_stepwise_equivalence=False。
- 实际OD_TRAIN_CONTRACT world8/batch8/accum4/global256/16轮/.1、camera=False/map=False、90558/8100，与计划一致；原GradientCumulativeFp16OptimizerHook和CyclicLrUpdaterHook/CyclicMomentumUpdaterHook均已注册。
- MLflow run `39eccd4dbe37486581ae33d5ab2e305e`，产物params_reported=True/train_batches=1/validation_batches=0/errors={}，真实首个after_train_iter已执行；不是仅Ray启动。尚无首50步窗口或首轮验证，不据此宣称长期稳定/全程梯度有限/精度达标。

- 随后新正式任务epoch1[50/1415] loss6412.0787/grad_normNaN、[100/1415] loss1244.7456/grad_normNaN，memory6880MiB；不能宣称首步数值验收通过。只读复查旧job85也在epoch1[50/354] loss2153.0951/grad_normNaN，随后[100/354] loss2.2932/grad1.8431、[150]1.8898/2.1961正常。新组累积4的microstep与旧每步update不等同，日志平均窗口非有限值不能量化实际AMP跳过次数。未改变初始化、未取消/重启；稳定窗口及首轮验证仍待。
- 后续epoch1[200/1415] loss3.9127/gradNaN，[250/1415] loss2.4925/grad575.3139有限，memory6937MiB。支持起步非有限窗口之后恢复实际更新，不支持全程无溢出或长期稳定；未改初始化/重新提交/云短测，首轮验证尚待。用户随后转入4090_8官方与自定义数据的误检差异只读讨论。
