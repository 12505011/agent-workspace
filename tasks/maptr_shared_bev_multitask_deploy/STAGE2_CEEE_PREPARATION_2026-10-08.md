# ceee pure-LiDAR OD completed; stage2 preparation pending scope decision

User asks to prepare stage2 after ceee completion and keep OD learning rate
small, considering newly inspected `/home/westwell/bevfusion`. No cloud training
submitted/canceled, no training repository edit/commit/push in this inspection.
Async question asks whether retain shared GN architecture or add independent
MAP spatial neck; no answer yet at record time. Do not silently migrate all
new repo architecture, LiDAR freeze/BN policy, loss weights or joint-label logic.

Verified live CLI status `job-ceee66eddaf1452d678c609f` SUCCEEDED, 8GPUs,
ray-ddp/torchrun,16epochs, BEVFusion image66b906... . Artifacts API lists all16
epoch files and best15 (89766549bytes). CLI full logs have16mAP/NDS pairs:
epoch14 .5003/.5439, best15 .5070/.5512, final16 .5055/.5305.
Published best15 SHA256 in full log:
`7b7539e19f4f1684418f0f9fde070813bd3e5eb9a2370c77fffaaacee8315358`.
This is logged publisher digest + artifact existence, not newly downloaded
entity verification; sha256 sidecar preview/download endpoint returns415.
Parentpath `/mnt/storage/me/runs/work_dirs/od_lidar_voxel01_aligned_nocbgs_16e_8gpu_20261008/job-ceee66eddaf1452d678c609f/`,
best filename `best_object_map_epoch_15.pth` (flat, not checkpoints/).

Artifact mlflow-status FINISHED/errors={},453training/16validation reports,
run39eccd4dbe37486581ae33d5ab2e305e. reference-alignment.json PASS: old85config
checked, changesvoxel/grid/world/accum only, cameraFalse/mapFalse/noCBGS,
batch8/world8/accum4/effective256. Live config.py confirms voxel[.1,.1,.2],
range[-54,-54,-1,54,54,7], sparse_shape1088x1088x41,
original SECOND/FPN decoder BN (eps.001/momentum.01).

Important preparation gates: existing maptr lidarinit recipe locks OLD85
best16 digest, not ceee. Never bypass by swapping file under legacyfilename.
Existing shared GN joint config uses1080 sparsegrid/fuseralignment180 and GN
decoder; ceee uses1088grid/native136 and BN. Tensor-shape load alone is not
strict OD behavioral continuity. Must explicitly decide preserved/changed
architecture, verify selected parent config, keys/values/metaepoch/SHA, initial
OD assessment and fresh optimizer before formal joint updates. Frozen stats
or independentMAPneck are distinct options, not authorized defaults.

User explicit decision: small OD-side LR. Proposed (NOT applied/approved) start
ODhead/pretraineddecoder1e-5, LiDAR5e-6 ifunfrozen; freshMAP2e-4. FreshFuser
has no transferred weights and needs its own LR; preservingODheadLRalone
cannot protectODagainst changed upstreamfeatures. Ratios/epochs/newneck/BN
freeze still require final recipe scope. Preparation only, no formaljob.

## 2026-10-08 已确认的后续决定与本地准备

用户确认保留原联合模型结构，只参考低OD侧学习率；OD与MAP外层loss系数1:1。最终选择32GPU、全局batch32、OD:MAP批次12:1，24个OD定义的epoch。OD每epoch 2830批次，MAP每epoch236批次；MAP共5664批次、181248帧次，按7533帧训练集折算约24.0605个MAP epoch（包括分布式补齐/重复采样）。此前16:1/24轮仅约18.05个MAP epoch，32个OD epoch虽能到24.06个MAP epoch，已被用户用12:1替换。

本地未提交配方 `configs/maptrv2/westwell/bevfusion_maptr_shared_bev_raytrain_ceee_lidarinit_lowod_24e.py`，入口`raytrain/od4site_joint_train.py --recipe ceee_lowod --initialize ceee`。父身份锁`job-ceee66eddaf1452d678c609f`/best epoch15/发布SHA；实际启动时校验权重实体、sidecar、checkpoint meta epoch、迁移张量、多rank初态和新optimizer。父实际config.py通过独立对比门禁，允许且记录BN→GN和sparse_shape1088→1080；OD assign_per_class均为False。相机R50、camera neck/Fuser/MAP按既有初始化，保持现有三相机、PKL、0.1m体素、范围、MAP6层/P20、不额外冻结。OD LiDAR LR5e-6、decoder/OD头1e-5，相机backbone3e-5、camera neck/vtransform/Fuser5e-5、MAP2e-4。仅本地配置和测试，尚未提交云端训练。

本地`tests/test_raytrain_ceee_lowod_joint.py` 5项通过；现有RayTrain joint回归35项通过。父实际配置从平台只读artifact preview校验通过。尚未做新配方GPU短测或正式训练，不把本地验证当作平台通过。

随后新配方1GPU短测已提交：`job-6ea5c4117515b25750b2d29f`，MapTR镜像digest `3ea27c82...c12242f84`，ray-ddp/single_gpu，输入`my-storage/workspace`，父精确目录 `my-runs/work_dirs/od_lidar_voxel01_aligned_nocbgs_16e_8gpu_20261008/job-ceee66eddaf1452d678c609f`，输出 `my-runs/work_dirs/ceee_mapod_od12map1_lowodlr_24e_smoke_20261008/job-6ea5c4117515b25750b2d29f`。最近查询状态PROVISIONING；实际训练/验证/梯度和权重回传未验收。前段“尚未做短测”指提交前状态。

短测随后SUCCEEDED：实际16OD+2MAP，梯度均有限；父实体SHA/metaepoch与153项LiDAR/decoder/OD参数迁移PASS，新optimizer，双任务各32样本验证，epoch1和best checkpoint已回传。MAP两次原始loss约235/255，远高于OD4–6；小样本指标不用于判断正式精度。正式32GPU任务 `job-1b6c3122f54c21c59484c80b` 随后已提交，4Worker×8GPU/ray-ddp/ray_train，MapTR同digest镜像、同父精确挂载与PKL，输出 `my-runs/work_dirs/ceee_mapod_od12map1_lowodlr_24e_32gpu_20261008/job-1b6c3122f54c21c59484c80b`。提交时QUEUED；尚未确认真实训练step。

短测MLflow status artifact: run ae2e9d6105534d16829e8ba5fe9552de, FINISHED, params_reported=true, loss_batches=18, lr_batches=18, validation_batches=1, errors={}.

后续真实状态RUNNING，runner确认每个OD epoch有2830 OD批、236 MAP批、3066总迭代；父153项迁移PASS、32rank初态一致。epoch1[50/3066]日志loss/overall17.9974、OD3.8136、MAP240.2115、grad_norm16.6810有限，窗口任务分数OD.94/MAP.06（前50步边界效应）；ETA当时19h22m，仅实时估计。完整验证/最佳权重/最终状态待确认。没有做Git提交或push。
