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
  existing 40-vector/15-point epoch-22 checkpoint and its saved config. It
  runs FP16 and fake-INT8 Map and OD validation with separate result files.
- Local validation: two CPU contract tests passed; FP16 3x3x3 sparse-conv GPU
  smoke test passed on RTX 3060; the full model contains 21 sparse conv layers;
  script syntax, Python compilation, and Git whitespace checks passed.
- The full nuScenes comparison has **not** run. `4090_8` SSH access is
  intermittent (port 22 timeout), and no checkpoint is present locally.

## Handoff

When 4090_8 is reachable, verify its repository/working-tree status, saved
checkpoint/config, and GPU occupancy before syncing the QAT branch files or
running the eval script. Keep unrelated local/remote changes intact. Do not
conflate PyTorch fake-INT8 validation with deployable QAT until the SCN
export/INT8 builder path and Orin kernel selection are separately verified.
