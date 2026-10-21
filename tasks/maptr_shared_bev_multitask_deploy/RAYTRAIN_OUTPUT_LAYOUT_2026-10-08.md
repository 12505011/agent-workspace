# RayTrain 输出层级（2026-10-08）

## 2026-10-09 联合第12轮独立续训

- epoch4可视化`job-fdc7f93c68aef7a66543a0b4`已SUCCEEDED并通过联合输出/图像验收：BEV与三个相机各648张；输出`my-runs/val/job-fdc7f93c68aef7a66543a0b4/mapod_new3val1_epoch4_od06_map04_fullval_20261009/joint_epoch_4/`，无视频。本地两张SHA校验过的第0/324帧合成预览在`/data/Downloads/raytrain/visualizations/new3val1_epoch4_od06_map04_20261009/`，均已实际查看；全量误检判读交由用户，数量摘要不代表误检指标。
- epoch4全量新MAP验证run的OD+MAP联合可视化已启动：`job-fdc7f93c68aef7a66543a0b4`，1GPU、OD0.6/MAP0.4、648帧、无视频。输出`my-runs/val/job-fdc7f93c68aef7a66543a0b4/mapod_new3val1_epoch4_od06_map04_fullval_20261009/joint_epoch_4/`。通用入口新增`--map-split new3_holdout1 --all`，按父训练manifest重建PKL并校验SHA，日志确认子PKL SHA`d1920a8133d86d2613887ecdbc50be78b54379fd90123b5b1cef191b6f680154`、checkpoint epoch4及阈值，已读取出图133/648帧；完成验收待查。
- 恢复任务`job-c77579e797cc526c98eadfc2`已SUCCEEDED并完成8轮。最佳MAP为epoch4：MAP@0.5 46.89%、MAP均值58.08%、OD mAP54.29%/NDS57.72%；最终epoch8为43.32%/54.42%/57.97%（MAP@0.5/OD mAP/OD NDS）。epoch4完整checkpoint持久目录为上述任务`checkpoints/epoch_4.pth`，SHA`b330b7f0d412d079995b2cd7e8bf464740603675e8ccbdde2c76a02fa14b9820`；新MAP验证仍是父模型已见run，不能作独立泛化结论。
- `job-4953ad2ca434fbe9abfb9fe6` 完成第1轮后在第2轮读MAP相机图片遭遇共享存储`Errno 5`，终态FAILED；其持久目录内有`checkpoints/epoch_1.pth`和SHA标记。新的32卡任务`job-c77579e797cc526c98eadfc2`只读挂载该失败任务checkpoint并从第1轮恢复，输出`my-runs/work_dirs/job-c77579e797cc526c98eadfc2/od4site_joint_e12_new3_val1_resume1_8e_32gpu_20261009/`。提交SHA`4998771c6e4a78bef3ec23257bc42511d9c59a9166e313f90bf6371e4e04a5a5`；已核实RUNNING，日志`resumed epoch 1, iter 3184`与`Epoch [2][50/3184]`有限loss。只读单卡探针确认该图片后来可重复读取、checkpoint及SHA标记存在；仍需监控存储稳定性。
- 用户最终指定沿用已训练联合epoch12。新32卡 `job-4953ad2ca434fbe9abfb9fe6` 已提交，结果 `my-runs/work_dirs/job-4953ad2ca434fbe9abfb9fe6/od4site_joint_e12_new3_val1_8e_32gpu_20261009/`，提交快照SHA `df9e91dafd04bda1dcd95194c9c1f3a19eb42a9cf6e93cfb7d06268f3bbe3aec`。只用四条新MAP run，三条训练2673、一条`0aaa...`验证648；该父权重已见验证run，报告标记非独立验证。平台最近状态PROVISIONING，首step待核验。OD原90558/8100不变。

- 用户纠正MAP只用四个新run、三训一验。上述 `job-ebcc97483f8dd1e69204c473` 随即停止并核实 CANCELED；旧新混合MAP设置不再使用。候选留出为此前诊断验证过的完整`0aaa1e56d62346adb3f8a8f05a6471b3` run；三训一验为2673/648帧。第12轮父checkpoint曾训练该run，独立验证语义无效；等待用户在纯OD父重新联合训练与已见数据诊断性续训之间选择。未提交替代任务。

- 用户指定停止8卡并改用32卡。`job-10fec67877afb291c7203441` 已核实 CANCELED；新的 `job-ebcc97483f8dd1e69204c473` 已核实 RUNNING，4×8 GPU。结果目录 `my-runs/work_dirs/job-ebcc97483f8dd1e69204c473/od4site_joint_e12_ft8r8_8e_32gpu_20261009/`，源码快照SHA `fb8fd8e8addb1372bd364efd4049ea35dc28fff4476865cec783e708eb9fa5d8`。
- 源checkpoint为已完成联合训练 `job-a255f5faaafda979688669a4` 的完整双头 `epoch_12.pth`，SHA `15f3189f8c924302bcd39a10e4b776c2fc7feafb8159b59681dec9c58ca964f3`。新8轮配方保留同一PKL、模型、0.075m体素及OD1/MAP0.12/depth0.04；改OD:MAP为8:1、基础LR5e-5，新优化器。入口SHA/结构及full-joint权重覆盖已通过；首100个训练step与有限loss/grad已观察，验证尚待。详情在 `/data/Downloads/raytrain/MapOD任务台账.md` 顶部。

## 清理核验更新

- 用户要求按明确目录清单批量执行，减少逐文件查询和重复进度汇报。后续 `val` 固定为 `val/<job-id>/<任务名>/`，与训练目录使用同款任务命名。
- 单卡清理 `job-c774d611f75ce1d779b10138` 已 SUCCEEDED，完整删除 `mapod_samearch_bnrestore_ep2_fullvis_recovery_20261006`。
- 单卡批量清理 `job-0bbfeda40c5edc85191496f0` 已 SUCCEEDED，日志 `VISUAL_CLEANUP_COMPLETE 8`：删除 fa618 全量图目录及剩余7个 samearch 历史可视化根目录。任务退出后的 Ray GCS 超时发生在清理完成后，不改变已核验成功结果。删除没有恢复保证；训练权重和数据不属于该清理清单。
- 输出层级4项、迁移3项、清理4项 unittest 均通过。历史目录迁移未全部完成；正式32卡训练尚未重新启动。

- 用户确定新层级为 `job-<id>/<任务名>`。训练根为 `my-runs/work_dirs/`；可视化根为与其平级的 `my-runs/val/`。平台将 `--output-path work_dirs` 或 `val` 先扩成 `<根>/<job-id>`，入口通过 `--task-name` 建子目录。旧平台任务输出路径不能中途改写。
- 旧正式联合任务 `job-1b6c3122f54c21c59484c80b` 在第1轮约600/3066步时按用户要求取消，状态已核实 `CANCELED`，未取得完整epoch checkpoint。旧输出暂不删除。
- 同配方第一版新目录任务 `job-f12b48cdc72b6549d0a109de` 曾核实 `RUNNING`，个人空间对应 `my-runs/work_dirs/job-f12b48cdc72b6549d0a109de/ceee_mapod_od12map1_lowodlr_24e_32gpu_20261008/`，并观察到第1轮约150/3066步真实且有限的loss。该任务因同一对象挂载上的大目录迁移阻塞而请求取消，最新平台状态 `DELETING`；没有已核实的完整epoch权重。
- 替代任务 `job-5dca542d856a9057162dd2f7` 已提交，4×8 GPU、24 OD-defined epochs、OD:MAP=12:1、global batch32、无CBGS，从 `job-ceee66eddaf1452d678c609f` 的最佳OD epoch15重新初始化。输出为 `my-runs/work_dirs/job-5dca542d856a9057162dd2f7/ceee_mapod_od12map1_lowodlr_24e_32gpu_20261008/`；截至最近核验仍为 `PROVISIONING`，Ray节点初始化日志已出现，但尚未核实训练step。
- 2026-10-08盘点个人 `runs/work_dirs` 有83个一级目录，其中24组明确为历史可视化。新 `runs/val` 已创建；25个历史可视化实体的迁移预演通过。已核实前10个实体移动或修复旧链接；第11个 `mapod_joint_epoch11_fullval_images_20261007/job-fa6183a93a61a1b2b28e87a1` 的大目录 `os.rename` 在对象挂载上进入不可中断的D状态，源/目标最终状态待存储恢复后核查。迁移脚本已改为执行时必须显式指定根目录，嵌套大目录还需额外确认参数；不与正式训练并行搬迁。历史旧路径保留软链接的方案在前10个实体已核实。不能宣称全部迁移完成。
- 代表性OD父权重 `job-ceee66eddaf1452d678c609f`、当前活跃训练目录及其祖先依赖不得按低价值短测清理。对旧 smoke/失败任务的权重瘦身须先排除所有下游引用，并保留配置、日志、结论；未核实前不删。
