# MAP5 epoch24 local RTX3060 deployment

- User-selected checkpoint: `/data/Downloads/best_map_NuscMap_chamfer_mAP_epoch_24.pth`.
- Verified SHA256: `e70b6e0bd2b8dbd3fb3f87384fe0a5166942ae20f6cf53f6cf782e275d0e92e6`.
- Source job `job-13554ddb5e531c6a95c2f779` SUCCEEDED, 24 continuation epochs; MAP mAP 0.9669, AP@0.5 0.9187. OD mAP 0.6365/NDS0.6743 remained unchanged at all four validations. Frozen state audits passed.
- Source copied into local MapTR `work_dirs/checkpoints/qth_frozen_map5_epoch24_20261013/`.
- Bundle: `/data/baize/baize-welldriver/code/maptr/work_dirs/onnx_engines/qth_frozen_map5_epoch24_20261013/`.
- Engine subdir: `build_rtx3060_cuda114_trt8522_mixed`; local RTX3060, CUDA11.4, TensorRT8.5.2.2. MAP/fuser FP32 noTF32, camera/vtransform/OD FP16-enabled, external I/O FP16.
- All581 non-MAP checkpoint tensors are bitwise identical to parent epoch15. Reused its four dense engines and custom sparse LiDAR graph; rebuilt MAP engine only. No old bundle overwritten.
- Training5 classes `[ped_crossing, divider, boundary, centerline, stop_line]`, 50 vectors/20points/6layers, three cameras TOP_MID/MID_LEFT/MID_RIGHT.
- Existing wire protocol/palette is canonical7 slots. Export-only logits adapter maps trained classes to IDs `[1,0,2,3,6]`, pins unused marking slots4/5 to -10000. Thus runtime map_num_classes=7 refers to output layout, NOT7 trained classes. This avoids recompiling runtime or publishing wrong categories.
- Native5 ONNX retained. Export config reconstructed from parent config + verified continuation recipe; strict complete checkpoint load passed.
- Initial export failed due user-site protobuf contamination. PYTHONNOUSERSITE=1 uses correct conda dependencies without mutating them. Original partial ONNX kept as `.unfinalized.onnx`.
- ONNX/native synthetic check: points max error0.00079587; original1e-4 absolute check failed2/12000 points. Separate report bounds normalized coordinate error at0.001, does not conceal original failure.
- Five standard ONNX checker passes; five plan deserialize/execute smoke passes; SHA256SUMS passes. TRT/native MAP max errors: class0.00605536, bbox0.00086483, points0.00132385. See validation report. This is module validation, not vehicle acceptance.
- User-operated independent player: `/debug/runqfile/baize_player_map5_epoch24/qbaize_play.sh`. Model path points to new bundle; MAP threshold0.4 and old OD thresholds retained. Original epoch15 player unchanged.
- No playback, git commit or push performed. User must run packet test and assess outputs. RTX3060 engines cannot be used directly on Orin.
