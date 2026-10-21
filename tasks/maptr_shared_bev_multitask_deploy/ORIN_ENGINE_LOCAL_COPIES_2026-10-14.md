# Orin engine 本地副本

2026-10-14 已从 98 Orin 下载两套完整 `build_orin_cuda114_trt8522_fp16` 目录。
源根目录为 `/data/code/all_ws/ws/ruicao/baize_ruicao/code/maptr/models/`。

本地位置：

- 无 neck / epoch24：`/data/baize/baize-welldriver/qth_map5_noneck_q40_epoch24_20261013/build_orin_cuda114_trt8522_fp16`
- ROI 后 neck / epoch20：`/data/baize/baize-welldriver/qth_map5_roi_neck_q40_epoch20_20261013/build_orin_cuda114_trt8522_fp16`

分别22、17个文件，全部与远端 SHA256 校验一致。包含五个 plan、LiDAR ONNX、
plugin、manifest 和现有构建/层信息日志。这些是 Orin 构建产物，不是 RTX3060 engine。
未修改任一端 profile 或启动播放；校验只证明传输一致，不新增模型精度验收结论。
