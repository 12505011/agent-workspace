# Environment notes

Add verified environment facts here: host aliases, non-sensitive paths, conda
environment names, and commands that have been tested.

Never add credentials, passwords, private keys, or access tokens.

## 4090_8 上的 MapTR CUDA 扩展

- `maptr` Conda 环境使用 Python 3.8、PyTorch 1.10.1 和 PyTorch CUDA
  11.3；该环境自身不提供 `nvcc`。
- 宿主机 `/usr/local/cuda` 与 `/usr/local/cuda-11` 实际指向 CUDA 11.8。
  因此直接在宿主机执行 `python setup.py build_ext --inplace` 会得到
  “PyTorch cu113 运行时 + CUDA 11.8/GCC 11 编译扩展”的混合环境。
- `/root/yihan/bevfusion` 使用的 Docker 容器具有匹配的 Python 3.8、
  PyTorch 1.10.1+cu113、CUDA toolkit 11.3、cuDNN 8.2 和 GCC 9.4。
- 已验证的做法是在该容器中挂载 MapTR 仓库，并执行
  `MAX_JOBS=8 python3 setup.py build_ext --inplace --force`。编译后的 13 个
  扩展可以由宿主机 `maptr` Conda 环境正常导入。
- 重新编译前必须检查 `torch.version.cuda`、`CUDA_HOME`、`nvcc --version`
  和编译器版本；不能仅凭 Conda 环境名或 PyTorch 显示的 CUDA 版本判断实际
  CUDA 扩展工具链。
