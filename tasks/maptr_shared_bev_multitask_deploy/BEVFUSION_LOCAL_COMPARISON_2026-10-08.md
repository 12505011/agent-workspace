# Local BEVFusion MapTRv2 implementation comparison

Read-only inspection of `/home/westwell/bevfusion` (directory has no `.git`) on
2026-10-08. Default launcher uses
`configs/sparse_map/maptrv2_r50_joint_bev06_dilated_24ep.py`; source, not a verified
training-result claim. No model construction, training, edits or cloud jobs.
Our baseline: saved epoch11 `same_arch_actual.py` under local
`code/maptr/work_dirs/onnx_engines/mapod_samearch_joint_epoch11_20261008`, plus
verified job4eb88/fa618 notes and stage2 a83f comparison.

## Verified structural differences

- New repo `sparse_map/maptrv2.py:173–195` captures Fuser output256ch BEFORE
  original OD SECOND/FPN. OD keeps its own BN SECOND/FPN -> TransFusionHead.
  MAP uses independent BEVDilatedEncoder256ch, bottleneck64, dilations1/2/3/5,
  GroupNorm, then metricROI/grid_sample XY->YX -> MapTRv2. One Fuser/frontends
  pass; no second fusion, no native0.3 MAP branch.
- Our `bevfusion_maptr.py:455–489`: both consume shared GN SECOND/FPN512ch;
  MAP crops it, not a comparable independent spatial BEV neck. MAP head input
  projection should not be equated with the new dilated spatial encoder.
- Default new `freeze_lidar=True`; trainable-prefix whitelist excludes all
  LiDAR parameters. `joint.py:191` sets LiDAR eval and all pretrained non-MAP
  BatchNorm eval, preserving running statistics; trainable BN affine can update.
  Camera/Fuser/OD decoder/head still train. MAP gradients still reach shared
  Fuser/camera; separate neck does not eliminate every gradient conflict.
- Our approved11 and stage2 all learning parameters train; R50 norm_eval=True,
  GN shared decoder but other active pretrained BN statistics not universally
  frozen. Neither approved11 nor a83f uses MAP BN bank.

## Data and objective differences

- New JointDataset requires identical OD/MAP token sets, sensor images and
  calibration alignment; each microbatch computes OD+MAP loss, combined one
  backward/update. Official nuScenes train28130/val6019, six cameras256x704,
  current+9 LiDAR sweeps. Not equivalent to alternation1:1.
- Our custom data has separate OD90558(approved11 budget90496)/MAP7533 frames,
  valOD8100/MAP729, missing reliable opposite-task labels; three cameras256x704,
  alternating tasks4:1 approved11 or1:1 a83f. Cannot adopt JointDataset by
  pretending missing opposite-task labels are reliable empty scenes.
- New MAP6layers/P20,70 one2one +300 one2many, GT repeat6,4classes(no stop_line),
  max50 outputs, ROI[-15,-30,15,30],0.6m100x50. Ours6/P20,40one2one,one2many0,
  7classes(including stop_line),max40,ROI[0,-10,54,10],34x90.
- Both0.6m fusiongrid; new LiDARvoxel.075, our approved11.075/a83f.1(resampled
  native.8mLiDAR to180grid). Neither uses MAP temporal state; new explicitly
  temporal_map=False, ours queue1/prev_bev=None. Nine LiDAR sweeps not MAP history.
- New explicitlossOD1/MAP1, no depthaux; oursOD1/MAP.12/depth.04 (internaldepth3).
  Neither has GradNorm/PCGrad; new featuregradnorm/cosine probes ONLY measure.
- New pretrainedOD fullyloaded resnet50/bevfusion-det.pth; approved11 partial
  pureLiDAROD16 transfer plus freshcamera/fuser/MAP. a83f fullfusionOD14 transfer.
- New peakLR camera3e-5/adapters1e-5/sharedOD2e-5/MAP6e-4; joint24 nominalepochs,
  7GPU/batch2/accum4 global56,12072 jointupdates,eval6epochs. ODmAP/NDS2pp-drop
  budget controls best_balanced selection, NOT automaticstop(defaultFalse).
  Oursapproved11 LR1e-4/MAP2e-4; stage2shared2e-5/MAP1e-4,32globalbatch.
- New camera backbone BF16 autocast, remaining geometry/customBEV FP32 with
  activationcheckpoint; ours dynamicFP16 optimizer hooks. No runtime numerical
  or accuracy claim made from static inspection.

Consequence: useful design contrasts are pre-OD-decoder MAP branching, MAP GN
spatial adaptation, fixed pretrained BN statistics and frozen LiDAR. Cannot
infer any one resolves custom-data false positives without controlled tests.
