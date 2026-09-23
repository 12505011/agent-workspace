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

## Handoff

No QAT code, checkpoint, engine, or device benchmark has been produced yet.
The next step is a read-only audit of the SCN export and third-party INT8
builder interface before deciding how to instrument/fine-tune the model.
