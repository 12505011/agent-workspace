# Technical decisions

Record a decision only after it is confirmed.

| Date | Decision | Rationale | Scope |
| --- | --- | --- | --- |
| 2026-08-29 | MapTR 的旧版 cu113 CUDA 扩展必须使用与 BEVFusion 一致的 CUDA 11.3/GCC 9.4 工具链编译，不能使用 4090_8 宿主机的 `/usr/local/cuda` | 宿主机软链接实际指向 CUDA 11.8；混合编译产物会导致 voxel 坐标损坏、spconv `N=0` 等非确定性错误 | 4090_8 上基于 PyTorch 1.10.1+cu113 的 MapTR/BEVFusion 扩展 |
| 2026-08-29 | 该旧版 PyTorch/cuDNN 栈的 8 卡 MapTR 评估固定使用 `cudnn_benchmark=False` | benchmark 开启时完整模型触发 `CUDNN_STATUS_INTERNAL_ERROR`/异步非法指令；关闭后 10854 样本完整通过 | 4090_8 上的 MapTR 多卡训练与评估 |
