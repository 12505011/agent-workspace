# Frozen MAP5 continuation, 2026-10-13

- User requested 24 GPUs, five classes and MAP LR6e-4 aligned to
  `4090_8:/storage/disks/d0/lelin/sparseMap/jk_pth/config.py`, retaining three
  cameras/current34x90 grid and subsequently retaining50 main queries.
- Submitted `job-6369313dd8de72452863c5f9`,3x8GPU/ray-ddp/ray_train,
  same image digest3ea27c82..., normal/retry0. Parent best MAP epoch15 from
  `job-5a6a8495ac4370ff9c4c4669`, SHA256
  `ca20b8f68a7912cff99f1f5a96c6347e6cdc8a05c3810c902ca884f695ea976e`.
- Continue via load_from, fresh optimizer/scheduler; full shared/OD frozen,
  MAP neck/head train. Classes `[ped_crossing,divider,boundary,centerline,stop_line]`;
  classifier rows migrated `[1,0,2,3,6]`, all query/other tensors unchanged.
- 24epochs/globalbatch24/noaccum/CBGS, FP32, AdamW6e-4/betas.9,.999/WD.01,
  warmup122iterations(one current epoch), cosine/minratio.01, clip35,
  validation every6epochs, checkpoints everyepoch, activation checkpoint enabled.
- New tests plus previous frozen/OD recipe tests:12passed. Actual CPU model
  strict-load902states and trainable-prefix check passed; GPU checks pending.
- Input remains locked personal workspace PKL release2916MAPtrain/729val.
  Source snapshot `6c9ae23fb059261f49b037ed880a47ef14b031925652257ad47f5adddef244a6`.
- Output `my-runs/work_dirs/job-6369313dd8de72452863c5f9/qth_map5_ep15_frozen_map50_lr6e4_24e_24gpu_20261013/`.
- At11:25CST platform RUNNING, no business steps yet observed. NoGitcommit/push.
- After submission user asked whether to align PKLs too. Documentation lists
  public maptr_data/data/jinke/58/pkl_nuscenes2_x0_55_yneg10_10_stopline_3cam/.
  Existing comparison repo documentation says4212/729; frame identity,
  camera compatibility and actual public contents not yet verified. No switch
  or cancellation authorized/performed on that basis.

## Subsequent cancellation and original-data retry

- User authorized stopping636931 and aligning reference PKLs, then explicitly
  revoked the data change: retain the original2916/729 workspace PKLs.
- Cancel requested; final observed636931 FAILED/desiredCANCELED. It had already
  failed before first training step because the continued parent config carried
  the old `stage2_transfer` checksum hook. Fix removes that obsolete hook and
  keeps `map_continuation_transfer` + frozen audit; regression test added/passed.
- Public read-only audit `job-74962c21f128d25a4273b196` SUCCEEDED:4212/729,
  no scene overlap, all frames have five slots including the correct physical
  three front cameras. Original metadata55m; no public files modified.
  trainSHA0d80948a4fe7ba2cd049fd7b00045dff205b8ff6a040afec25503f06a57557c7,
  valSHA63c558c77cd631d16a1e211336f736de18948c5ed5f11892fd2ba83c339d3b1e.
  Server-side reference hash comparison not completed: SSH repeatedly timeout.
- New actual training `job-37c3e29db405eb15653d3287`, same24GPU/24e/LR6e-4,
  MAP5/50main/300aux, original workspacePKLs and parentepoch15.
  task `qth_map5_ep15_frozen_map50_lr6e4_24e_24gpu_r2_20261013`.
  Last checkedQUEUED/Suspended, no business step yet. Thirteen recipe/freeze
  tests total passed. NoGitcommit/push, no data or weights deleted.
- Extra read-only original-manifest inspection submission was rejected locally
  by platform GPU_QUOTA_EXCEEDED; no job created, no cancellation of37c3.
  New training manifest explicitly includes `map_split_run_counts` for exact
  original run membership/counts once source initialization starts.

## User-requested16GPU switch

- User said24GPUs exceed actual server capacity and requested16GPUs. Cancelled
  `job-37c3e29db405eb15653d3287`; desired/observedCANCELED verified before submit.
- Submitted `job-13554ddb5e531c6a95c2f779`:2x8GPU/32CPU128Gi perworker,
  ray-ddp/ray_train, normal/retry0; same image/input/parentbest15/24epochs/LR6e-4,
  MAP5/50main/300aux, shared/OD frozen, FP32, noCBGS/accumulation.
- Per-GPUbatch1 => global16,183MAPsteps/epoch and183warmupiterations(oneepoch).
  Four continuation tests passed including16/24 resource calculations.
- Source SHA66b17a603b948d2e801066ec6243b9f784cfa65cdd252fee858769648d253ae6.
- task`qth_map5_ep15_frozen_map50_lr6e4_24e_16gpu_20261013` under
  my-runs/work_dirs/job-13554ddb5e531c6a95c2f779/.
- First platform check RUNNING and exact2x8spec; business step still pending
  at this note. NoGitcommit/push or artifact deletion.
