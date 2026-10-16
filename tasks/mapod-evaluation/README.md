# Task: MapOD Automatic Evaluation

## Goal

Design and implement a reproducible automatic evaluation workflow for a joint
OD + MapTR checkpoint in `/data/baize/baize-welldriver/code/dl_bev_mapod`,
using `/data/baize/baize-welldriver/code/maptr` as the evaluator backend.
The workflow should evaluate the two tasks against their own validation data,
report their metrics independently, and make checkpoint selection/results
traceable. Implementation scope is not yet frozen.

## Existing implementation in `maptr_infer`

- Training validation hooks are registered in
  `mmdet3d/apis/train.py`. With `evaluation.tasks`, the code builds one
  validation dataset/dataloader per task and registers a `TaskDistEvalHook`;
  otherwise it uses the standard single-dataset `DistEvalHook`.
- `mmdet3d/apis/task_evaluation.py` resolves task-specific dataset and metric
  configs. Supported metrics are `chamfer`/`iou` for `map` and
  `bbox`/`object`/`3dod` for `object`. `TaskDistEvalHook` routes the model's
  evaluation mode per task and keeps best-score/checkpoint metadata separate.
- `tools/3dod_maptr/maptr_test.py` performs standalone inference and evaluation.
  For task-separated configs it requires `--task map` or `--task object`,
  chooses that task's validation dataset, then calls `dataset.evaluate()`.
- The current alternating Westwell config
  `configs/maptrv2/westwell/bevfusion_maptr_shared_bev_nuscenes_map_od_alternating.py`
  defines Map `chamfer` and Object `bbox`, but sets
  `evaluation.interval = total_epochs + 1`; its comment explicitly says inline
  validation is disabled for that run. So the existing standalone test path is
  available, while that config does not automatically validate during
  training.

### Where Map GT comes from

- The configured `ann_file` is the Map validation PKL. The nuScenes dataset
  loader reads `data["infos"]` into `self.data_infos`; in this Westwell
  converter, each info stores a vector-map `annotation` generated from the
  source map API and the sample's pose/location. `get_data_info()` passes that
  stored annotation to `vectormap_pipeline()`, which turns it into clipped,
  labeled LiDAR-frame vector instances for the sample.
- `map_ann_file` is a separate derived JSON cache, not the source of the map
  geometry when it is missing. `_format_gt()` checks whether it exists. If
  absent, it loops through `data_infos`, runs `vectormap_pipeline()` on each
  info's stored `annotation`, and writes `{ "GTs": [...] }` with sample tokens
  and vector points/classes. If it already exists, the code trusts it and does
  not regenerate or validate it against the PKL.
- During scoring, `_evaluate_single()` reads predictions from
  `nuscmap_results.json` and GT from `map_ann_file`. `format_res_gt_by_classes()`
  checks that prediction and GT list lengths match, then pairs entries by list
  position; it does not verify that their `sample_token` values match. This
  makes a stale or differently ordered GT JSON a serious silent-evaluation
  risk. An automatic evaluator should validate token equality/order and class
  coverage before reporting scores.
- For the current config, the expected paths are the Map validation PKL under
  `data/pkl_shared_bev_map_x0_54/` and its companion
  `nuscenes2_run_token_x0_54_yneg10_10_stopline_3cam_map_anns_val.json`.
  The source code/config were inspected; file existence/content on disk was not
  checked as part of this task.

### Where object-detection GT comes from

- The `object` validation dataset uses the separate OD validation PKL configured
  as `od_val_ann_file`. Each info contains `gt_boxes`, `gt_names`, and
  `num_lidar_pts`; these originate from the source sample annotations when the
  joint PKL is built. `NuScenesDataset.get_ann_info()` reads those fields,
  applies configured name mapping and point-count filtering, and returns 3D GT
  boxes/labels for the OD pipeline.
- Unlike Map scoring, this repository's `NuScenesDataset.evaluate()` does not
  need a separate OD GT JSON or reload GT from the nuScenes API. It loops over
  the validation dataset infos, builds GT `DetectionBox` records from
  `get_ann_info()`, converts model outputs into predicted boxes, and evaluates
  both using the project's nuScenes-style `DetectionEval`. It returns per-class
  AP/TP errors, `object/map`, and `object/nds`.
- The current Westwell config selects the object task's `bbox` metric and
  `save_best="object/map"`. The expected OD validation PKL is under
  `data/pkl_shared_bev_od_x0_54/`; its existence and contents were not checked
  during source inspection.

## Prior agent-work findings

The existing `task/maptr_shared_bev` branch is the relevant training/evaluation
reference; `task/maptr_shared_bev_multitask_deploy` is primarily runtime
deployment context.

- The joint model uses independent OD and Map validation datasets, task routing,
  metrics and best-checkpoint state. Map mAP and object mAP/NDS must be read
  independently; one task's score must not overwrite the other task's best
  checkpoint.
- The prior evaluation contract fixes Map evaluation to the configured class
  set (including zero-GT classes) and averages each class's AP over Chamfer
  thresholds 0.5 m, 1.0 m and 1.5 m before averaging across classes. Historical
  six-class and seven-class Map results are not directly comparable.
- A known compact-logger bug matched the suffix `map` too loosely and could
  report `loss/map` as `eval/od_mAP`. Do not trust that compact field as an
  evaluation result; prefer the task-specific evaluation logs and
  `od_metrics.json` until the parser is inspected/fixed.
- A previous Map evaluation failed while formatting offline GT because
  `_format_gt()` supplied an empty example and `gen_vectorized_samples()`
  accessed `img_metas` unconditionally when `pv_seg=True`. The fix guarded PV
  mask generation on `img_metas`; training PV supervision remained unchanged.

Source reference: `task/maptr_shared_bev`, especially
`tasks/maptr_shared_bev/README.md` (“Data and evaluation contract”, “Runtime and
tooling fixes”, and “Commands and validation”) and
`tasks/maptr_shared_bev/experiments.md` (the v14 offline-GT evaluation failure).
These notes are historical context; verify assumptions against the active
`maptr_infer` checkout before implementation.

## Initial implementation questions

- Should automatic evaluation run from a training hook at configured epochs,
  or as a separate checkpoint-watcher/launcher after checkpoints appear?
- Should the workflow evaluate every checkpoint or only selected/latest/best
  checkpoints, and should Map and OD run sequentially or concurrently?
- What is the required output contract: per-task JSON/CSV, a combined summary,
  visualization artifacts, and/or best-checkpoint copies?
- How should retries, partial task failure, duplicate evaluation, and resume
  be represented so results remain attributable to checkpoint/config/data?

The earlier source inspection did not run evaluation; current implementation
status is recorded below.

## Cross-repository integration reconnaissance (2026-10-16)

- At the start of this work, local `dl_bev_mapod` contained only Git metadata:
  no commit on `master`, no source files, and no remote heads. The user then
  asked to implement the evaluator there, so its files are new local work.
- The supplied `maptr` checkout is on `exp/mapod-cy-map-lidar075` and has
  unrelated existing working-tree changes. Treat it as read-only during this
  task unless implementation is explicitly requested; preserve those changes.
- `maptr` already has a direct implementation reference:
  `tools/3dod_maptr/maptr_test.py --task map|object` selects
  `cfg.data.val.map` or `.object`, loads one checkpoint, runs inference and
  calls that dataset's evaluator. Its task-separated config maps Map to
  `chamfer` and Object to `bbox`.
- `tools/3dod_maptr/eval_shared_bev_checkpoint.sh` is a sequential two-task
  launcher with per-task output pickle/log/metrics JSON and switches for
  running either task. Its current checked-in defaults are for a standalone
  Map-only config, so a OneModel implementation should use a task-separated
  joint config and enable both branches.
- The One-stage joint config uses a single model/checkpoint with independent
  Map and OD validation datasets. `TaskDistEvalHook` registers one hook per
  task and saves separate best checkpoint state. A reference config
  `bevfusion_maptr_shared_bev_mxg128_reference_one_stage_exp_g_joint_ratio16_4e.py`
  evaluates both every epoch; task inference may still invoke the shared model
  separately on each validation set.
- Likely initial design for `dl_bev_mapod`: orchestrate two isolated eval runs
  against the same checkpoint/config (Map PKL + GT JSON, OD PKL), preserve
  independent results and statuses, then write a combined checkpoint-level
  manifest. Before reporting success, verify each task's sample tokens, class
  set and GT contract. This direction is now implemented below.

## Local evaluator implementation (2026-10-16)

- Added `dl_bev_mapod/eval_one_model.py` and `README.md`. The script runs the
  existing `maptr_test.py` once per selected task against one config/checkpoint,
  writing separate `map/` and `od/` predictions, metrics, logs, and one
  `evaluation_manifest.json`. The task choices are `both`, `map`, and `od`.
- It reads the Map and OD validation PKLs independently, checks sample tokens,
  pose fields, OD GT fields and configured class coverage. It validates an
  existing Map GT JSON against PKL token order, or directs MapTR to generate a
  new JSON from the Map PKL under the output directory and validates it after
  evaluation. Input hashes and distinct ego pose counts go into the manifest.
- The current OD dataset config uses `object_classes` and `dataset_root`,
  whereas Map uses `map_classes` and `data_root`; the orchestrator handles these
  task-specific fields. It supports dry run, resume, worker count and GPU IDs.
- The CY Map joint source config retains placeholder validation PKL paths.
  No matching checkpoint or current validation PKLs were found in the local
  checkout during this work, so no full GPU evaluation was performed.
- The current QTH release name and validation filenames were verified in
  `raytrain/qth_cymap_joint_train.py`: Map 729 samples and OD 2106 samples.
  The documented platform release path is not mounted on this local host.
- Static AST parsing and `--help` succeeded. The local Python environment
  lacks `mmcv`, so dataset preflight and GPU evaluation require the MapTR
  runtime on the platform; these were not claimed as verified.
- Ego pose is read per LiDAR sample from the source `ego_pose` record in
  `westwell_joint_converter.py`, stored as `ego2global_*` in the PKL, and read
  per sample by `nuscenes_offlinemap_dataset.py`. The local Map ROI offset can
  be fixed relative to the vehicle; the global ego position is data driven.
  Actual variation in a target PKL remains to be checked when it is supplied.
- Checkpoint delivery is an interface. Both `maptr_infer` and active `maptr`
  `maptr_test.py` accept a positional checkpoint path and load that file at
  runtime. The older `eval_shared_bev_checkpoint.sh` hardcodes a CKPT path for
  one experiment, but does not embed the weight file. On RayTrain,
  `custom_joint_visualize.py` reads `PLATFORM_CHECKPOINT_PATH`, accepts an
  explicit checkpoint basename/epoch/hash, and verifies the mounted artifact;
  the QTH profile has no built-in default joint checkpoint. The new evaluator
  likewise accepts `--checkpoint`; its README now documents passing a
  manually uploaded or attached `.pth` from the platform mount.

## Bundled evaluator update (2026-10-16)

- Following the user's request to make `dl_bev_mapod` independent of the
  `maptr` checkout, copied the current `mmdet3d/`, `configs/`, standalone
  `maptr_test.py`, QTH/OD class contracts, native extensions, and extension
  build metadata into `dl_bev_mapod`. Its `SOURCE_SNAPSHOT.md` records the
  source branch/commit and that relevant uncommitted source changes were
  included. The original `maptr` checkout was left untouched.
- `eval_one_model.py` now defaults its MapTR root to its own repository. It
  reads PKL `metadata.path_links`, validates only the sensor aliases used by
  selected samples, and creates temporary runtime `data/` symlinks for QTH
  relative sensor paths. The bundled evaluator clears the training-only
  camera backbone `init_cfg` before loading a full joint checkpoint.
- In `conda maptr`, the copied model/dataset modules imported from the new
  repository, the current QTH CY Map config loaded with seven Map and eleven
  OD classes, and both CLI entry points launched their help pages. A
  synthetic two-task `--dry-run` initially exposed an `mmcv.load` call bug;
  after correction, it completed, selecting the bundled evaluator for both
  tasks. Full GPU scoring still awaits a real checkpoint and mounted QTH
  validation release.

## `maptr_infer` comparison (2026-10-16)

- `maptr_infer` has the same basic standalone task routing in
  `tools/3dod_maptr/maptr_test.py`: evaluate Map and OD separately against
  their configured validation datasets. It does not contain the current
  `CYMapTRv2Head`, MapQR modules, fused-BEV model changes, or the current QTH
  CY Map/LiDAR075 config, so it cannot directly instantiate the current joint
  checkpoint.
- The bundled evaluator uses the active `maptr` implementation. Its Map GT
  export disables auxiliary PV generation when constructing GT from PKL
  annotations, and its OD dataset supports the current name mapping and
  configurable minimum LiDAR point filters. The current OD config selects
  `detection_qth_od11`.
- `maptr_infer` has no locally compiled `mmdet3d` extension binaries. The
  bundled checkout includes 13 extensions built for the local `conda maptr`
  environment. Both still require a real checkpoint and validation PKLs for
  end-to-end GPU scoring; no comparative scores have been measured.
