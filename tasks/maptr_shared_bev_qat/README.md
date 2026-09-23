# Task: maptr_shared_bev_qat

## Goal

Evaluate whether quantization-aware training can reduce Orin latency for the
shared-BEV OD + MapTR model without unacceptable OD or Map accuracy loss.

## Branches and baseline (2026-09-23)

- MapTR code branch: `bev_3dod_maptr_shared_bev_nuscenes_qat`, created from
  `bev_3dod_maptr_shared_bev_nuscenes` at `079a4dc06a26fbeeea7432f45138238017d9db59`.
- This agent-workspace branch: `task/maptr_shared_bev_qat`, created from
  `task/maptr_shared_bev` at `0501707cc69fafdbd8b6116f076499a9a37790cc`.
- Branch creation did not modify model code or start a QAT run. The MapTR
  working tree had pre-existing uncommitted edits; they were preserved.

## Verified model and deployment context

- `configs/maptrv2/bevfusion_maptr_shared_bev_common.py` configures a LiDAR
  `SparseEncoder` with voxel size `[0.075, 0.075, 0.2]`, camera encoder,
  `ConvFuser`, shared BEV decoder, Anchor3D OD head, and MapTR vector head.
- The current training configuration uses mixed-precision FP16, not QAT.
- Earlier Orin measurement isolated `scn.spconv_forward` at approximately
  45 ms in the measured deployment setup. The SCN implementation is supplied
  by third-party `libspconv_q.so`, not by MapTR training code.
- Prior trace analysis found continuous GPU work during measured SCN windows;
  CPU synchronization time alone must not be treated as removable latency.

## Initial scope and open gates

- Investigate LiDAR SCN INT8 first; keep camera, fuser, OD, and Map heads at
  FP16 for the first controlled comparison. This is a proposed experiment,
  not a validated performance improvement.
- Before a full QAT run, verify that the third-party SCN exporter/builder can
  consume QAT quantization parameters and build an engine that actually uses
  INT8 kernels. PyTorch fake quantization by itself does not establish this.
- Compare a QAT candidate against its FP16 starting checkpoint using the
  same model architecture, validation data, and Orin playback for OD, Map,
  `scn.spconv_forward`, `core_wall`, and end-to-end processing time.
- nuScenes can validate the training/export flow. Westwell OT128 production
  accuracy and latency require representative Westwell data on Orin; nuScenes
  results alone cannot establish either.

## Precision-probe implementation (2026-09-23)

- MapTR commit `048ec35` on `bev_3dod_maptr_shared_bev_nuscenes_qat` adds a
  reversible SCN-only fake-INT8 PyTorch probe. This is an accuracy experiment,
  **not QAT fine-tuning or evidence of Orin INT8 acceleration**.
- The probe uses per-output-channel symmetric 8-bit fake quantization for each
  sparse convolution weight and per-tensor symmetric 8-bit fake quantization
  for its input features. Activation scales come from 128 training samples by
  default; camera, fuser, shared decoder, OD head, and Map head are unchanged.
- `tools/3dod_maptr/eval_scn_fake_quant_nuscenes.sh` is configured for the
  existing 40-vector/15-point epoch-22 checkpoint and the new executable
  probe config. It runs FP16 and fake-INT8 Map and OD validation with separate
  result files. The training-run `.py` is only a dictionary text snapshot,
  not directly executable by MMCV. On 4090_8 the probe config's complete
  `model` and train/val/test `data` sections were verified equal to that
  snapshot after parsing it as a literal dictionary.
- Local validation: two CPU contract tests passed; FP16 3x3x3 sparse-conv GPU
  smoke test passed on RTX 3060; the full model contains 21 sparse conv layers;
  script syntax, Python compilation, and Git whitespace checks passed.
- The same two CPU contract tests and script/Python syntax checks passed on
  4090_8. SHA-256 for the synced `maptr_test.py`, controller, and eval script
  matched the local files.
- MapTR commit `17fc557` restored `workers_per_gpu=2` and made the eval script
  compare the runnable probe config against the specified 40x15 run's saved
  config snapshot before launching. On 4090_8, `model`, complete `data`,
  optimizer, optimizer_config, lr_config, runner, evaluation, fp16, seed, and
  cudnn_benchmark all matched. The runner also resets the random seed after
  calibration, before either validation arm. The three updated files' hashes
  matched between local and 4090_8 after sync.
- The full nuScenes comparison has **not** run. `4090_8` SSH access is
  intermittent; an existing training job had occupied all eight GPUs at the
  previous check, so the probe was not started.
  The checkpoint and required official-nuScenes annotation files exist on
  4090_8; the five probe files were synced there and syntax-checked.

## Handoff

The 4090_8 code directory has no `.git`; the five probe files were copied
explicitly after verifying its previous `maptr_test.py` matched the local
pre-change SHA-256. Run the eval script only after checking that its selected
GPU is free; do not interrupt the existing 8-GPU training job without user
direction. Do not conflate PyTorch fake-INT8 validation with deployable QAT
until the SCN export/INT8 builder path and Orin kernel selection are
separately verified.
