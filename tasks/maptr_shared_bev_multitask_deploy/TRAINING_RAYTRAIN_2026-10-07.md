# RayTrain MapOD：联合 epoch11 良好可视化及数值排查记录

日期：2026-10-07。归属 `task/maptr_shared_bev_multitask_deploy`。
这是实验和交接记录，不替换历史部署模型契约，也不等于批准新的部署、训练或分支操作。

## 已验证的任务及权重身份

| 用途 | job-id | 结果 |
| --- | --- | --- |
| 单 OD 预训练父模型 | `job-85ea81db448753bc4c584a08` | 已有最佳 epoch16，LiDAR-only / Anchor3DHead |
| 唯一完整初始化 | `job-4e7988f4802e012789ed0846` | 完整模型参数及 BN 缓冲区一次生成并校验，后续两组共用 |
| 联合训练 | `job-4eb88b7f2b38f52a3b329ea5` | 16 卡训练到 epoch11 并保存；最终更新计数验收失败，不是训练中途 CUDA 崩溃 |
| 联合 epoch11 全量评估/出图 | `job-fa6183a93a61a1b2b28e87a1` | MAP729 帧指标与全部四画布已验收；整体报告 STARTED，OD8100 阶段尚未最终验收 |

- 联合权重：`checkpoints/epoch_11.pth`，535156212 字节。
- 联合权重 SHA256：`db2c5fc2b14acedbc316071eec1e9a130046f775aab67077936c45d568aa1517`。
- 父训练目录：`my-runs/work_dirs/mapod_samearch_joint_mature11_16gpu_20261007/job-4eb88b7f2b38f52a3b329ea5/`。
- 单 OD epoch16 SHA256：`4234958c9633c011190b4dc4390a4b8e31994ba0882a23662ebd60a5b56ab146`。
- 完整初始化 pth SHA256：`faac311e19c08b9d0437bf2bcbc619a72657d99b85713af81115a31025950865`。
- 运行时完整初态 SHA256：`a394910069b5f332e7afaa2551691c5fbe04ded70fb120a59abc3693703ea92d`。
- 训练源码快照 SHA256：`00088f574b13cc1a5a0bb75eafb7cbc474f4d4d5eba4a32ea97143c99387b536`。
- 可视化源码快照 SHA256：`4661f43ac43274001e4d0ac0019739c57f067ea48880b6c67bbb710094a4cc43`。
- 专用镜像：`harbor.wellspiking.ai/guofeng.su/raytrain-maptr@sha256:3ea27c82e9606bb480c004a51b15478ea5d4017063c83b48f240365c12242f84`。

## 当前有效训练配方

- 独立入口：本地 `/data/baize/baize-welldriver/code/maptr/raytrain/same_arch_train.py`，`--group joint --epochs 11 --map-steps 707 --train-only`。
- 配置入口：`configs/maptrv2/westwell/bevfusion_maptr_shared_bev_raytrain_od4site_joint_mapbudget_16e.py`；driver 明确覆盖为 11 轮，不能根据配置文件名误报 16 轮。
- camera + LiDAR，共享 Fuser 和 GN decoder；OD 为 **Anchor3DHead，不是 TransFusionHead**；MAP 为 MapTRv2 六层 decoder、每条线 20 点、七类含 stop_line。
- 三相机，输入 256×704；LiDAR voxel `[0.075,0.075,0.2]`；MAP local-LiDAR 范围 `[0,-10,-10,54,10,10]`。
- 16 卡（2 Worker×8GPU），每卡 2 样本，全局 batch32，`ray-ddp/ray_train`。
- 全部学习参数不冻结；R50 `norm_eval=True` 的既有冻结 BN 行为保留，不将“参数不冻结”误解为所有 BN 都更新。
- OD:MAP 优化调度 **4:1**；每轮 2828 OD + 707 MAP 批次，计划累计 31108 OD / 7777 MAP 更新。
- 正常 MAP/depth 梯度进入共享参数；不是 shared-gradient-block 或 BN-restore 对照组。
- **无 MAP 专用 BN bank、无额外 BN 校准**。两任务推理使用同一正常训练获得的 BN 统计。
- 不开 CBGS；无新增 neck、多尺度 BEV 或 GradNorm；不重新生成 PKL、不改相机裁切来迎合结果。
- 完整初始化承接单 OD16 的 LiDAR/decoder/OD 权重及 ResNet50 相机初始化，统一新增模块初态，首批前重置 RNG；各 rank 校验所有参数及缓冲区。

## 数据和评估契约

- PKL 根目录（workspace 相对路径）：`nuscenes_mapod_pkl/od4site_mapod_nocbgs_20261004/`。
- OD 原训练 90558 帧，本组确定性选择 90496 帧；MAP 训练 7533 帧；OD 验证 8100 帧，MAP 验证 729 帧。
- OD-only 与联合长程对照训练成员 SHA256 相同：`5d7a6fe6df7ac6fe4a23b4b0194f77d649295af7f40c298bedc9d2794cf69978`。
- MAP 验证 PKL：`map/map_x0_54_3cam_val.pkl`，SHA256 `20e52c3c4af51cea147cb3760f206c4e176d2f9d1e3975031ec181cbbdf18fe1`。
- 本次评估从指定 epoch11 实体严格校验后加载；optimizer 步数 0、校准步数 0；不改原权重或父报告，不混用两头不同 epoch。
- 显示阈值 **OD=0.6 / MAP=0.4**，与此前同帧对照一致；不是通过提高阈值隐藏误检。
- MAP 验证帧同时输出两头并出图。MAP 帧缺少经独立认证的 OD GT，不从框数或看图反馈计算 OD FP 率。

## 结果和用户确认

本人复读平台 `same_arch_evaluation_report.json` 及 `validation/map/metrics.json`：

| MAP 指标 | 结果 |
| --- | ---: |
| 全部七个配置类别 mAP@0.5 | 0.3418626083 |
| 0.5/1.0/1.5 三距离阈值均值 mAP | 0.4736253896 |
| divider AP@0.5 | 0.6463374496 |
| boundary AP@0.5 | 0.6142901778 |
| centerline AP@0.5 | 0.7702913880 |
| stop_line AP@0.5 | 0.3280667067 |

- MAP 的 BEV、camera-0、camera-1、camera-2 各 729 张，合计 2916 张；报告已记录完整数量。
- 用户看 `job-fa6183a93a61a1b2b28e87a1` 图片后确认视觉结果非常好。这是人工效果反馈，不等于量化“零误检”或所有验证帧均已人工检查。
- 当前 OD 全量指标、全部 OD 图及最终整体 state 保护验收尚未确认；不要将任务 RUNNING / 报告 STARTED 写成整个评估完成。

图片根目录：

```text
/mnt/storage/me/runs/work_dirs/mapod_joint_epoch11_fullval_images_20261007/job-fa6183a93a61a1b2b28e87a1/validation/map/frames/
```

子目录：`bev`、`camera-0`、`camera-1`、`camera-2`。OD 验证域后续产物在同 job 的 `validation/object/frames/`。无视频、无 workspace 副本；用户从任务产物或个人 `runs/work_dirs` 查阅。

## 与此前严重误检实验的差别及因果边界

- 旧 BN-fix 联合父训练为 `job-ab0f055076fd311e4ba0b097`，epoch11 SHA256 `fb1d21d38d39e2e8e90ae7701aa692b70cd19c90cc6f91bb974d0f1818f38aa8`；旧联合 MAP 域可视化使用额外校准得到的 MAP BN bank。本组不用该 bank，也不在评估时校准 BN。
- 两者都承接单 OD16，都有 4:1 调度；**不能把 OD16 初始化或 4:1 说成相对该旧实验新增的独有修复**。
- 本组一次固化完整模型初态，再正常训练；旧严重误检实验为 32 卡/每卡1，本组16卡/每卡2。局部 BN 条件、随机初态/过程、训练计划等也不同，尚未通过单变量消融锁定唯一原因。
- 相对先前同初态的两短轮对照，本组还增加了训练量：覆盖接近完整 OD 集，共 11 轮、7777 MAP 更新；不能只比较 epoch 名称而忽略每轮实际更新数。
- 可复用结论：正常共享 BN 的联合训练已出现用户认可的双任务效果；现有证据不支持“多任务结构必然产生车道线误检”。不据此宣布 BN 是全部问题的唯一根因，也不自动追加结构改造。

## 训练 FAILED 的实际原因和 OD-only 未决事项

1. 联合 `job-4eb88...` 已到 epoch11，实际 OD 更新31097，比计划31108少11；MAP7777完整。日志11个 grad_norm=Inf 窗口与逐轮计数缺口一致，AMP 跳过11次OD更新。最终严格计数门禁失败，不能改写为无溢出、精确预算通过。出图通过显式 `--expected-skipped-od-updates 11` 审计恢复，不放宽默认门禁、不改父报告。
2. OD-only16卡 `job-677635e59066d63223a324db` epoch2 首个业务异常为 OD cls_score NaN；可恢复 epoch1 SHA256 `4c97a0017d9054a0a656647a0784994f50ff4b12f50482f5251bb98e16e5bafe`。
3. OD-only32卡恢复 `job-efff60c734bae54f1eb6d6cc` epoch2 再次失败，CUDA BCE 输入 `[0,1]` 断言，后续 decoder 栈可能是异步报错。相机 depth BCE 是候选，来源尚未证明；失败后的 GPU 探针受 CUDA context 污染未留下有效首因报告。
4. 有界同步诊断 `job-af741284df43c85e2730eef8`（32卡、原epoch1、原配置，最多600步）**已 FAILED**。复读日志确认首次错误在新增 `FailureProbe.begin()` 遍历 `metas=None`，`TypeError: 'NoneType' object is not iterable`；不是再现原模型数值异常，没有有效 `diagnosis_report.json`。后续须先修复探针 metadata 提取及 None 处理并回归，再决定是否重放。此次仅记录，未修改或重提诊断任务。

## 后续交接

- 良好结果的复用基准是本页明确的 epoch11/SHA、实际训练配置、native共享BN和验证PKL，而不是可视化job名字或当前随时可变的源码默认配置。
- 继续核验 `fa618...` OD8100 全量指标/图片、整体 COMPLETE 与推理前后 state 保护；MAP729阶段已完成。
- 保留用户人工判断与客观指标分开；未认证 OD GT 的 MAP 域不报告量化零误检。
- OD-only 数值根因仍未解决；不要盲目续训，也不影响或重跑已认可的联合权重。
- 本次只增加 agent-workspace 记录与索引；未 commit、未 push，未变更部署选择、模型或数据。

## 用户批准的下一轮：32卡正式联合16轮

- 用户要求停止另一OD-only组，使用本次认可配方重新训练16轮、32卡。提交前CLI实查仅有 `fa618...` 可视化 RUNNING，无运行/PROVISIONING的OD-only任务；失败的OD-only不再重提，当前可视化不停止。
- 正式任务 `job-0e53d752e031316d49cb4e91`，名称 `mapod-joint-nativebn-sharedinit-16e-32gpu-20261007`；已提交，平台初态SUBMITTED，不能据此宣称训练首步完成。
- 快照 SHA256 `6542da8f237b837d265805b6dc0b8d2b3deca0c8d4f38514caa85306dd199753`；镜像不变；4 Worker×8GPU，每Worker32CPU/128Gi，ray-ddp/ray_train，retry0。
- 从唯一完整初始化 `job-4e7988f4802e012789ed0846` 重新开始，**不加载联合epoch11续训**，不复用它的optimizer/scheduler。
- 指令：`python3 raytrain/same_arch_train.py --group joint --epochs 16 --map-steps 707 --train-only --formal-training`。
- 16轮OD:MAP=4:1，每轮2828OD/707MAP，计划45248OD/11312MAP优化批次；同90496OD训练成员及7533MAP训练帧，无CBGS/冻结/BN bank/校准，模型和损失不改。
- global batch仍32，32卡每卡1；认可的16卡每卡2。局部BN条件不同，已向用户明确，不能承诺逐步一致或把卡数变化当纯速度优化。
- 新 `--formal-training` 仅允许fresh joint：每轮完整OD8100/MAP729验证，MLflow报告和checkpoint保存；最终全量双头图片另走独立只读任务。`--train-only` 在该模式表示不在训练退出后串联整套最终出图，不表示禁用每轮验证。
- 仅新增正式训练验收/报告逻辑：逐批记录optimizer实际调用与AMP未调用，要求全部计划批次完成且 `实际更新+记录AMP跳过=计划批次`，非有限梯度跳过不计作成功更新。原对照的严格相等门禁保留；不变更loss/optimizer，不skip/clamp数据。最终只读评估验证完整正式报告及AMP账目。
- 模型、PKL、初态校验仍在Worker业务启动时逐rank执行；没有启用有bug的OD-only FailureProbe。新增配置/AMP验收/最终评估元数据测试先红后绿；语法、diff检查通过。
- 输出根目录：`/mnt/storage/me/runs/work_dirs/mapod_joint_nativebn_sharedinit_16e_32gpu_20261007/job-0e53d752e031316d49cb4e91/`，config、logs、metrics、checkpoints各有独立目录。
- CLI最初带 `--max-failures 0` 被本地校验拒绝（该flag限engine ray-train），未创建任务；移除该托管flag后唯一正式提交成功，返回spec retryPolicy.maxRetries=0。不切分支、不commit/push，不删除旧产物。
- 最后本地139项RayTrain回归全部通过（依赖库仍有既有弃用警告），语法/diff检查通过；CLI已到RUNNING、launcher确认4Worker×8GPU入口，尚待模型初态及首个实际loss证明。
- 随后业务验收通过：manifest确认world32/16轮/global32、模型SHA与训练成员SHA均和认可组一致；`training_control_report.json` STARTED且完整初态校验通过，state SHA仍 `a394910069b5f332e7afaa2551691c5fbe04ded70fb120a59abc3693703ea92d`，formal=true、BN bank=false、MAP更新共享参数=true。
- 日志实际到 `Epoch [1][50/3535]`，任务采样占比OD=.8/MAP=.2、loss/overall=6.8459、grad_norm=9.3327均有限；不能从首50步推断长期稳定或最终精度。MLflow run `3a4164e05d7848f893c80419a5a7a358` 已创建，MapTRMLflowHook挂载成功。

### 后续用户改变计划：先OD16，再联合1:1四轮

- 用户要求停止上述32卡联合任务，先训练0.1m体素单OD16轮，再进行OD:MAP=1:1的4轮联合训练。已取消精确 `job-0e53d752e031316d49cb4e91`；CLI复查终态CANCELED，未删除任何权重/日志/数据，未重启OD-only诊断。
- 新训练尚未提交：需确认第一阶段“单OD”指纯LiDAR，还是三相机+LiDAR只训练OD（推荐后者以直接复用完整融合特征链）。已向用户发送选择，不擅自把两种模型等同。
- 若联合阶段仍以完整OD集定义epoch、global batch32，1:1四轮约等价48次MAP训练集采样遍历，MAP预算接近4:1十六轮，不能误报为MAP仅4轮。第二阶段学习率及实际更新预算待确认；不自动串联或提前启动。

### 用户确认三相机：真实单OD第一阶段

- 用户已明确三相机+LiDAR，非纯LiDAR；第一阶段只OD、.1/.1/.2体素、16轮、32GPU、无CBGS。旧32卡joint任务仍CANCELED，产物保留。
- 独立opt-in配置 `configs/maptrv2/westwell/bevfusion_maptr_shared_bev_raytrain_od3cam_voxel01_16e.py`，入口 `raytrain/od_stage1_train.py`；单NuScenesDataset、EpochBasedRunner，仅Anchor3DHead。MAP头为None、不构建、不加载MAP PKL/批次；不使用之前MAP前向零loss的OD-only对照模式。
- 三路槽位MID/LEFT/RIGHT、256×704，裁切/标定/十类anchors/GT契约沿用四场地验证配方。OD完整90558/8100成员，PKL实体SHA绑定，不重新生成或裁切训练成员；global32每轮2830批次（sampler有8帧padding），16轮45280个计划批次，不等同于保证AMP实际更新45280次。
- voxel .1关联 sparse_shape [1080,1080,41]；Fuser仍目标180×180，共享GN decoder保持，不加neck/多尺度/BN bank。学习参数不冻结，R50 norm_eval=True仍保留。
- 第一阶段fresh只R50预训练，LiDAR/Fuser/decoder/OD重新训练，不加载旧.075 OD16或joint权重/optimizer。第二阶段再承接本次OD权重，MAP6/P20、1:1四轮；尚未提交第二阶段。
- 新配置与资源/三相机payload门禁测试先失败后实现通过；141项RayTrain回归通过（既有依赖弃用警告），旧默认joint配置.075未改变，无commit/push。
- 32卡短测 `job-370e0bfe525f248675a270e5` 已提交且RUNNING，4Worker×8GPU，每Worker32CPU/128Gi，ray-ddp/ray_train，专用MapTR镜像不变。源码快照SHA `8dd9fc7805a96984865c5317c8e0ba521c2cab20ce0b4a2cfdc0c140e2861a7c`。
- 入口 `python3 raytrain/od_stage1_train.py --smoke`，每rank4个OD训练批次，再32帧OD验证及checkpoint/MLflow持久化验收；输入my-storage/workspace，不挂旧checkpoint，输出 `work_dirs/od3cam_lidar_voxel01_32gpu_smoke_20261007`。当前只是启动状态，业务训练、短测终态/正式16轮待核验，不将RUNNING等同于首步或正式训练。

### Fresh OD头初始化门禁与第二次短测

- 上述370e短测平台SUCCEEDED，但四批分类loss约19880～51218，grad_norm前三批NaN/末批Inf；不能认为真实优化或数值稳定通过。OD验证32帧mAP/NDS均0，仅验证流程，不评价最终精度。epoch/best实体复制与SHA验证已完成；MLflow ea768ef295bd499091e381101af1fed9 FINISHED、4训练上报/1验证、errors={}。
- 代码确认父BEVFusion.init_weights只调用相机backbone，未执行Anchor3DHead native init_cfg；fresh头分类bias仍随机近0，而native要求bias_prob=.01、bias≈-4.595、Conv std=.01。CPU构建实际模型仅object头/两encoder，36520651参数，未构建MAP；不是误加载MAP训练批次。
- 增加本配方opt-in `initialize_fresh_od_head=True`，训练入口调用原生head.init_weights，不重写标准初始化。旧配置默认无影响；禁止load/resume同时启用，调用幂等，不重置未来承接的OD头。此项是已证实初始化遗漏，是否足以修复数值问题待同32卡短测，不宣称全部历史误检根因。
- 新smoke退出前严格核对4个JSON日志的loss/grad_norm全部有限；进程正常结束、MLflow或保存成功不能替代该门禁。2项新增测试先红后绿，累计143项RayTrain回归通过。
- 第二次短测 `job-8c8e81df780cb2887c2fc7c1` RUNNING，同32卡/input/image/数据样本/训练参数，仅增加native头初始化与验收门禁；新输出 `work_dirs/od3cam_lidar_voxel01_nativeinit_32gpu_smoke_20261007`，源码SHA `37d8cb5691b8e5526c85f1961d5979b1df93141adcfc62b9f2c9504cbb4f178b`。正式16轮仍未提交，不加载任何短测权重。

### 第二次短测通过，正式第一阶段已提交

- 8c8短测已SUCCEEDED；同32卡4批OD loss=6.2096/5.6526/5.6194/5.5660，grad_norm=33.9496/36.2726/31.2461/25.0513均有限，`smoke-gradient-check.json`复读PASS/4。对照首次高loss/Nan，在同输入/AMP/优化器下原生head初始化修复了此短测数值异常，不外推全部历史误检根因或长期稳定性。
- epoch1/best复制并复读SHA通过（epoch `436998f82e1f0ad796961845b4c88054c31e0fcb9bc6e612496e1ae968be14a9`），OD32验证通过；4步fresh模型mAP=0不是长期指标。MLflow `2225c110dfa6401484dcf2ee7468c475` FINISHED，4训练/1验证上报，errors={}。
- 正式新任务 `job-de12c931cdee027773ced801` 已提交SUBMITTED，名称 `od3cam-lidar-voxel01-nocbgs-16e-32gpu-20261007`；入口 `python3 raytrain/od_stage1_train.py`。4×8GPU，各32CPU/128Gi，ray-ddp/ray_train/retry0、专用MapTR镜像不变，input=my-storage/workspace，无checkpoint挂载，不承接短测pth或旧.075OD权重。
- 正式源码SHA `830a761f35cd644bbedc9a7cf1981db82790ffc5bd422036952babe19cc6ac48`，与已验收短测仅README说明补充，运行代码相同；去掉smoke后全量OD90558/8100、16轮/global32，每轮OD验证/权重/MLflow。
- 输出 `/mnt/storage/me/runs/work_dirs/od3cam_lidar_voxel01_nocbgs_16e_32gpu_20261007/job-de12c931cdee027773ced801/`，checkpoints/logs/config/metrics子目录。正式业务门禁与首loss待下一步核验，不把提交成功说成16轮完成。无commit/push，第二阶段未提交。
- 用户追问之前单OD输入：已从BEVFusion实际 `raytrain/train_od.py` 验证旧父 `job-85ea81db448753bc4c584a08` 16轮为encoder仅lidar/head仅object，camera=False/map=False，无Fuser；后续同结构OD-only对照则保留相机Fuser及MAP前向。新第一阶段是三相机+LiDAR Fuser仅OD，三者不能混称为同一基线。

### 正式第一阶段进度与独立中途可视化（2026-10-07晚）

- 实查 de12正式任务RUNNING、32卡不变，epoch11第800/2830步附近，最近loss=.1679/grad_norm=2.1723有限；不从单个日志窗口宣称全程无AMP跳过。OD8100验证epoch10 mAP=.4628/NDS=.4859/mATE=.4783/mASE=.3878/mAOE=.5603，目前10轮中最佳mAP，epoch9=.4473/epoch8=.4510。
- 用户要求另起中途可视化，不停止/恢复训练、不重训、不换当前模型。选定完整 `best_object_object_map_epoch_10.pth`，SHA `c0186b4a6b4584bcde20d466034bde78b2418eff524bc298d2732893732a9ea6`（日志+artifact列表确认431028689字节与侧车已保存）。读父实际 `config/od_stage1_actual.py`，不拿joint模型或不同体素config代替。
- 复用原 `custom_joint_visualize.py` 新增可参数化profile `odstage1`；仅准备已锁定MAP holdout/test pipeline用于展示，不增加模型MAP头或改变共享权重。原custom24/od4site16行为/默认选择不变。native模型strict载入、metadata epoch及所有tensor有限值核验；原三个相机真实标定/裁切/渲染配色/z约定保留，推理前后state/pth核验。
- 全量原729帧MAP验证PKL SHA仍20e52c3...；MAP线只GT，当前单OD模型没有MAP预测/指标。OD=.6，与历史同帧对照一致，不根据预测选择帧/提高阈值；生成BEV和三个相机共2916PNG，不生成视频、不额外复制workspace、不计算未认证OD GT的MAP域FP率。
- 两项新profile/config回归先红后绿，145项RayTrain测试通过（既有依赖弃用警告），语法/diff检查通过；未修改训练模型/数据/正在运行快照，未commit/push。
- 独立可视化 `job-6b9f060d8319ca0601582183` 已SUBMITTED，名称 `od3cam-epoch10-jinke-val729-od06-images-20261007`，1GPU/8CPU/32Gi、ray-ddp/single_gpu/retry0、同MapTR专用镜像；source SHA `abb56fd4a519e6410c27b70837f18126c64cdc9991217e51fefc7de5587708ff`。
- 只读checkpoint挂父精确 `work_dirs/od3cam_lidar_voxel01_nocbgs_16e_32gpu_20261007/job-de12c931cdee027773ced801`，input=my-storage/workspace。入口 `python3 raytrain/custom_joint_visualize.py --profile odstage1 --parent-job job-de12c931cdee027773ced801 --epoch 10 --checkpoint best_object_object_map_epoch_10.pth --checkpoint-sha256 c0186b4a6b4584bcde20d466034bde78b2418eff524bc298d2732893732a9ea6 --all --bbox-score 0.6`。
- 图片根目录 `/mnt/storage/me/runs/work_dirs/od3cam_epoch10_jinke_val729_od06_images_20261007/job-6b9f060d8319ca0601582183/od_epoch_10/`，子目录bev/camera-0/1/2；原预测 `od_predictions.pkl`、actual_config.py、父级visualization_report.json。当前图片及最终state/完整性尚待业务日志核验，不把SUBMITTED说成出图完成。
- 后续可视化RUNNING，日志VISUALIZATION_START已核对epoch10/父实体SHA/原729帧PKL SHA/OD=.6，严格载入通过并出现实际图片。artifact API复读bev/camera-0/1/2各已有26张，首张均为 `000000_map_jinke58_67d96d9d7072406981aa694c667c338f::a54a09cb61cb8e6241e07d979556faf8.png`，与此前固定首帧一致；不是仅平台启动。完整729/2916PNG、推理state终检和最终报告仍待结束，不宣称全量已完成。
- 最后训练已到epoch11第1850/2830，loss=.1597、grad_norm2.1556；1800窗口曾grad_norm=Inf，后续恢复，未中断。597个已记录训练窗口中8个非有限梯度窗口，不能等同8次实际AMP跳过（日志每50步平均），不能报告“全程无溢出”。可视化日志已到sample47（至少48帧完成），完整输出/state终检仍待后续。

### 第一阶段收尾与二阶段代码准备（未正式启动）

### 二阶段短测通过、正式4轮已提交

#### 2026-10-08复读最终结果

#### 2026-10-08二阶段MAP最佳轮全量联合可视化

后续15f已RUNNING且真实出图。VISUALIZATION_START复读确认epoch3、精确best-map3 SHA、原729 PKL SHA、阈值OD .6/MAP .4；四画布artifact各已有5张，首名与历史固定首帧 `000000_map_jinke58_67d96d9d7072406981aa694c667c338f::a54a09cb61cb8e6241e07d979556faf8.png` 一致。只读API抽看首帧BEV/前中原图：MAP预测线有输出，OD远处停放车辆区域框密集且类别重叠，不能凭这一帧认证重复/误分类或凭空误检；当前前景路面未见连续密集框模式，非全量零误检结论。完整729/2916PNG、最终state/checkpoint不变和报告待结束；未另起视频/续训。

- 用户要求看可视化；选择同一个MAP最优epoch3，同时出OD和MAP，不拼不同epoch。父a83f实际 `config/od4site_joint_actual.py`，精确best-map3实体SHA `2f68967fd8cd85ea53e4fff0d5d9e5adf2832b631185c14dd3f78cb599ac57c8`；原729精科MAP验证PKL SHA20e52c3...、原3cam MID/LEFT/RIGHT、OD=.6/MAP=.4、bevfusion绘框z和local-lidar地图投影不变；GT虚线/预测实线，无视频/workspace副本。
- 原可复用driver只新增 `--profile odstage2`：四场地原链接/holdout和保存配置，体素.1；须显式parent/epoch/file/SHA，不设隐式默认新权重。新增profile启用strict checkpoint/metaepoch/finite所有权重检查，逐帧OD+MAP结果有限值和推理前后state/checkpoint不变、四画布全量解码核验。不改模型/训练/标定/裁切/渲染算法/默认旧profile。1项新测试先红后绿，总151项RayTrain回归通过，无commit/push。
- 独立任务 `job-15f55956ab3cbd57e09f4a30` 已PROVISIONING，1GPU/8CPU32Gi/ray-ddp single_gpu/retry0/同MapTR镜像；input=my-storage/workspace，只读checkpoint挂a83f精确输出根。source SHA `3609b4882dc32a4b1d69c4df81488e588761b18f4b9b37f7a912619bbc011710`。
- 入口 `python3 raytrain/custom_joint_visualize.py --profile odstage2 --parent-job job-a83f70fa7a1ada448e0d8395 --epoch 3 --checkpoint best_map_NuscMap_chamfer_mAP_epoch_3.pth --checkpoint-sha256 2f68967fd8cd85ea53e4fff0d5d9e5adf2832b631185c14dd3f78cb599ac57c8 --all --bbox-score 0.6 --map-score 0.4`。
- 产物根 `/mnt/storage/me/runs/work_dirs/stage2_epoch3_jinke_val729_od06_map04_images_20261008/job-15f55956ab3cbd57e09f4a30/joint_epoch_3/`，bev/camera-0/1/2各预计729PNG、joint_predictions.pkl/actual_config.py/preview，父visualization_report.json。当前未确认出图或误检结果，不能从提交宣称全量已完成。

- 正式a83f已SUCCEEDED，4轮/22640iter完成，每轮OD8100+MAP729验证；MLflow d170bf3cd99541b3aa8758a4c651386c FINISHED/errors={}，validation_batches4（合并两任务）、11321训练上报。日志末尾Ray SIGTERM draining错误发生Job succeeded之后，是收尾警告，不据此说训练失败。
- epoch1 OD mAP=.4154/NDS=.4551，MAP均值=.3499/AP@.5=.2754；epoch2=.4225/.4789、MAP=.3376/.2545；epoch3=.4162/.4546、MAP=.3924/.3046；epoch4=.4392/.4897、MAP=.3708/.2834。原始JSON/文本日志与checkpoint artifact列表交叉核验。
- MAP最好epoch3：`best_map_NuscMap_chamfer_mAP_epoch_3.pth` SHA `2f68967fd8cd85ea53e4fff0d5d9e5adf2832b631185c14dd3f78cb599ac57c8`；同epoch OD mAP41.62%。联合阶段OD最好epoch4：`best_object_object_map_epoch_4.pth` SHA `fcac27a58208f2638d3da7607c4dad0f18d4dfd49d8eb9babd04bf5cddb2ecae`；普通epoch4 SHA `b9188e19600cc51e8d86919d974c1e3536ba3fb87cfa189656f4cde653ba0ade`。实体/SHA侧车存在，不说已本地下载。
- 相比父OD14 mAP49.06%/NDS52.62%，联合最优OD4 mAP43.92%/NDS48.97%，下降5.14/3.65百分点；MAP3至4 AP@.5下降2.12百分点。MAP明显学习，不支持“只差更多epoch就够”结论；OD指标退化真实，但是否重现凭空误检须同帧全量可视化，当前未新开出图/续训任务。
- 最后训练MAP scaledloss≈1.48（首窗≈26.98），OD≈.155，训练JSON452窗口中5个非finite梯度窗口，末窗口4.3112有限；窗口计数不是AMP实际跳过次数，不能宣称全程无溢出。仅记录结果，无模型/配置变更、无commit/push。

正式后续已RUNNING并实际更新：a83f日志epoch1[50/5660]，OD/MAP批次占比各.5，loss/od=.1430、loss/map=26.9768、loss/overall13.5599、grad_norm4.5563，首50步窗口有限；不能以窗口平均值代替逐步AMP跳过统计。正式迁移artifact复读PASS/581 tensors/父OD14 SHA/32rank state digest与短测一致；全量90558/7533、验证8100/729，max4轮及无CBGS已由PREPARED日志再次核实。日志ETA约7h52仅初期估计。metrics/mlflow-status.json仅epoch后镜像，因此首步artifact404正常，短测已验收FINISHED/errors={}，正式后续每轮仍需复查。无commit/push。

- a1eb短测SUCCEEDED：迁移检查PASS/581非MAPtensor/32rank完整state一致（digest `6168375d25c149e004397ce27318d9f9bcad15df3ecb0589948d1929005854f5`），父best14实体SHA与metaepoch通过，新optimizer未恢复、step0。32批JSON梯度门禁PASS：OD16/MAP16全finite；首OD loss=.1455/grad2.6148，首MAP loss29.7483/grad7.8439，末MAP26.9870/7.2920。短测数值稳定不保证长期无梯度溢出或无视觉误检。
- 两任务各32帧验证已完成：OD mAP=.4392/NDS=.4403、MAP均值=.0153/AP@.5=0；MAP只更新16批，不拿它当正式收敛指标，也不拿OD小样本指标同8100全量比较。MLflow c42eddab64a14d0a9f42e16180759ae8 FINISHED、errors={}、32训练上报、validation_batches=1（每epoch合并两任务验证上报一次，不是缺少一项评估）。epoch1实体SHA `4a0d2f7498ee6b74d5a8f928b940e8e7ce2536e678c5cf4abddf9175dd4f5f27`，不用于正式初始化。
- 正式 `job-a83f70fa7a1ada448e0d8395` SUBMITTED，名称 `stage2-od1map1-3cam-voxel01-4e-32gpu-20261007`，同4×8GPU/32CPU128Gi每Worker/专用镜像/ray-ddp ray_train/retry0、同输入和OD14只读parent；入口完全同短测但去掉--smoke，不改运行代码。sourceSHA仍 `8cdd318094237f09f17ec565986ab07369aaeb9c2e22a90a8e2383bccd2eb952`。
- 正式输出 `/mnt/storage/me/runs/work_dirs/stage2_od1map1_3cam_voxel01_4e_32gpu_20261007/job-a83f70fa7a1ada448e0d8395/`。原全量OD90558/MAP7533、验证8100/729，1:1/global32/4OD轮，581共享tensor和OD按父14承接，仅MAP初始化；不加载smokepth。每轮两任务评估/保存/MLflow。首实际业务仍待核验，不能把SUBMITTED说成已更新或训完。未commit/push。

后续完成核验：de12已SUCCEEDED，16次OD8100验证完整结束；epoch16 mAP=.4836/NDS=.5034/mATE=.4590/mASE=.4088/mAOE=.5229，最终最佳OD mAP仍epoch14=.4906/NDS=.5262，NDS最佳epoch15=.5283。二阶段明确按mAP用完整epoch14，不默认最后epoch16。MLflow `3f4a3bc61afe4c5698aaebbc74444c4c` FINISHED、errors={}、validation_batches16、iterations45280、906次训练上报。epoch16实体SHA `f1fdf4947f3a14b5d70933912cda4850db6908fa81afbcd1a589d0fe5fc502e0`，best14实体/SHA侧车列表及日志核验通过。

OD释放资源后已提交32卡stage2短测 `job-a1ebbd88ea905be8d167d686`，4×8GPU、每Worker32CPU128Gi、专用MapTR镜像/ray-ddp ray_train/retry0、input=my-storage/workspace、readonly parent=de12精确输出根；sourceSHA `8cdd318094237f09f17ec565986ab07369aaeb9c2e22a90a8e2383bccd2eb952`。入口 `python3 raytrain/od4site_joint_train.py --recipe stage2 --initialize stage1 --parent-job job-de12c931cdee027773ced801 --epoch 14 --checkpoint best_object_object_map_epoch_14.pth --checkpoint-sha256 2a1ec3d1c01017b9b9bf8dc6916e52a7dc18f41b6b0146806502d67f31835123 --smoke`。输出 `work_dirs/stage2_od1map1_voxel01_32gpu_smoke_od14_20261007/job-a1ebbd88ea905be8d167d686`，当前PROVISIONING，业务验收/正式4轮尚待，不加载smoke权重。再次150项RayTrain回归通过；未commit/push。

- 用户补充OD尚未结束，先准备代码，不截断第一阶段。de12仍RUNNING，最后复读epoch16第2150/2830，loss=.1332、grad_norm1.8591。已完成epoch14 mAP=.4906/NDS=.5262；epoch15 mAP=.4885/NDS=.5283。按OD mAP选最佳，不能在epoch16结束前把epoch14称为最终最佳。
- 6b9独立epoch10全量可视化已SUCCEEDED：729帧、BEV+三相机共2916PNG，推理state及checkpoint实体不变，无optimizer/校准/视频。抽查第0/364帧组合图未见此前沿车道连续凭空框模式；不等同全量零误检证明，用户最终视觉判断仍保留。
- 新配置 `configs/maptrv2/westwell/bevfusion_maptr_shared_bev_raytrain_stage2_od1map1_voxel01_4e.py`：三相机/.1体素原融合链/GN decoder/Anchor3DHead，新增原MAP6/P20，所有学习参数解冻；R50 norm_eval统计策略不变，无CBGS/BN bank/校准/新增neck。原四场地OD90558/8100、MAP7533/729及PKL SHA不变。
- 二阶段1:1/global32，4个OD-defined epoch，22640总批/11320 MAP批≈48.09 MAP采样遍历（含padding），不是4次MAP遍历。新optimizer/load_from，不resume；共享基础LR2e-5、camera沿用.6倍率、新MAP头5倍=1e-4；原静态loss权重不变，无GradNorm/PCGrad。
- `od4site_joint_train.py --recipe stage2 --initialize stage1`四个显式身份参数锁定父OD任务/epoch/文件/SHA，比较父已保存实际config的完整共享架构与OD头；平台API复读de12父 `config/od_stage1_actual.py`，全部encoders/Fuser/decoder/目标网格/OD头与新配置相同（仅去掉camera的init_cfg路径），父MAP头None。
- 新 `stage2_transfer.py` 启动before_run严格核对父实体SHA/metaepoch、所有非MAP键/shape/有限值/实际载入tensor值（允许AMP dtype转换）、各rank完整初始state一致、新epoch/iter/optimizer空状态；报告 `config/stage2-transfer-check.json`。新MAP头仅opt-in调用其native init_weights，前景prior.01，原OD头不重置；旧配置默认关闭，不影响正在运行快照。
- 新增5项回归先红后绿，总150项RayTrain本地测试通过。短测结束还要求JSON日志16 OD+16 MAP批均finite loss/grad_norm且任务身份正确，报告 `config/smoke-gradient-check.json`；进程exit0不能替代数值门禁。尚未通过平台Torch2/cu121/32卡短测，不宣称生产启动成功。
- 首次32卡smoke提交被平台 `GPU_QUOTA_EXCEEDED` 拒绝，无新job；现32卡被de12占用，未停任何旧任务。拟父候选 `best_object_object_map_epoch_14.pth` SHA `2a1ec3d1c01017b9b9bf8dc6916e52a7dc18f41b6b0146806502d67f31835123` 仅用于候选短测，正式必须等16轮完成后复查最佳/完整权重/MLflow。无commit/push。

### 2026-10-08同帧比较结论

详见 [COMPARISON_2026-10-08.md](COMPARISON_2026-10-08.md)。新15f全729/2916PNG已SUCCEEDED且state/checkpoint不变；旧fa618亦完成OD8100+MAP729。相同token/PKL/阈值下新模型道路区域框明显增多，不能解释为仅投影差异；框总数4643→6468不是FP计数。旧/新OD mAP55.73%/41.62%，MAP AP@.5 34.19%/30.46%。两版均共享BN，体素、初始化、任务比例、LR和每卡batch同时不同，尚未锁定唯一根因；本次无新训练或代码改动。
