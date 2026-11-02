# PYNQ工程：AC820叶片识别

运行内容来源为用户新提供的 `pynq (1)(2).tar`（SHA256 `a407c3b0618fee8ec9c0b18020dccc587bcbd823aadd7281916e7ae9667bfe94`）。本工程可直接部署；只修改目录、大小写和入口引用，未调整模型数值逻辑、阈值、UI或硬件配对。完整原TAR的519份文件保存在 `src/runtime_snapshot.zip`。检查结论见 [pynq_review.md](report/pynq_review.md)。

| 目录 | 内容 |
| --- | --- |
| `src/` | Python模块、原TAR完整快照及恢复索引 |
| `sim/` | 原测试、文件改名回归、真实权重调度检查及报告 |
| `build/` | 本地诊断、Notebook生成、快照恢复与交付校验 |
| `board/` | 运行入口 `lanuch.py`、Notebook、bit/HWH、Linux外设配置 |
| `data/` | 106权重、模型清单、外设表、样本和采样输出 |
| `skill/` | `README.md` 与可复用 `skill.md` |
| `report/` | 本轮改动与验证、历史记录和原文档 |

## 1. 上板前

先从本工程根目录执行 `python -B build/check_project.py`。板卡需已有适配AC820的PYNQ 2.7镜像；不要用PYNQ-Z2镜像代替。此工程不是SD卡系统镜像，也无需因目录整理重新烧卡。

按板商说明核对启动模式、供电、LCD/相机排线与实际Bank电压。默认入口的PL电压选项为3.3V，仅用于已确认匹配的AC820；不能仅凭文件名推断电气连接。板上PS I2C、触摸pinctrl和CMA条件仍按 [Linux集成说明](board/linux/README.md) 核对。本文不自动更改设备树或开机服务。

将整个提交包解压后传至 `/home/xilinx/jupyter_notebooks/fpga_competition/`，使本工程位于其 `pynq/` 子目录。应复制所有子目录，不能仅上传Notebook或单个Python文件。下面的路径按实际复制位置调整。

## 2. 避免与旧应用同时运行

在板卡终端查看旧服务（不存在则无需停止）：

```bash
systemctl status ac820-ricevision
```

若确实存在且正在运行，先 `sudo systemctl stop ac820-ricevision`；若旧Notebook仍运行，则执行其正常清理并等待成功，再关闭该内核。只有一个程序可以占用PL/VDMA。更换目录后使用新内核/新Python进程，避免加载旧模块缓存。

原TAR文档提到已注册此服务，但没有提供对应unit文件；不能认为复制工程就会安装自启动。若原卡有服务，其ExecStart仍可能指向旧工程，应先核对，不在本次整理中重写服务。

## 3. 运行与停止

在板卡终端执行：

```bash
cd /home/xilinx/jupyter_notebooks/fpga_competition/pynq
sudo /usr/local/share/pynq-venv/bin/python3 -B board/lanuch.py --check
sudo /usr/local/share/pynq-venv/bin/python3 -B board/lanuch.py
```

`--check` 检查权重、位流元数据和触摸条件，不下载PL；通过后再执行第二条运行命令。若镜像的PYNQ Python安装位置不同，应使用实际PYNQ环境，不能切换到没有pynq模块的系统解释器。用Ctrl+C正常停止，等待清理完成。

也可以在已连通板卡网络的浏览器打开：

```text
http://<板卡实际IP>:9090/notebooks/fpga_competition/pynq/board/00_one_click_start.ipynb
```

一键Notebook自动查找本工程，按单元顺序运行即可。它导入 `board/lanuch.py`。启动后用 `app.status()` 查看状态，`app.request('detect')` 识别，`app.request('save')` 保存，`await app.stop()` 正常停止。LCD按钮含义与原TAR一致。Save保存的是点击时采样，不能默认等于前一次Detect帧。关机先停止程序、`sync`，再按Linux正常关机流程等待完成。

若DMA清理失败，应保留进程、锁和缓冲并排查，不能重复启动另一份程序。历史文档中的192.168.5.9等IP仅代表当时环境，读取当前板卡实际地址；本轮未修改板卡网络。

## 4. 主机回归与原包恢复

电脑需Python 3.8或以上、NumPy和Pillow。板上运行另需PYNQ及相机/触摸依赖。主机不连接硬件，输出目录必须全新且位于整个提交树外：

```bash
python -B sim/run_host_tests.py --output-dir /tmp/ricevision_host_check
```

Windows可将输出路径替换为 `E:/rice_check/pynq`。本次53项中51项通过、2项缺少外部旧源而跳过，见 [记录](sim/host_tests.json)。真实106权重与63次核调用回归使用模拟设备，不模拟HLS数值运算。

若需要对照原TAR，可额外恢复到全新外部目录；这不是本工程正常启动的必要步骤：

```bash
python -B build/restore_sources.py --group runtime --destination /tmp/pynq_tar_original
```

恢复树保留旧大小写、旧路径及旧文档，与本次小写可运行树分别对照。`report/input_file_mapping.json` 给出519份输入文件的保存位置、SHA256与内容是否改变。`report/original_docs/` 与 `report/from_tar/` 是历史记录，当前路径以本README为准。
