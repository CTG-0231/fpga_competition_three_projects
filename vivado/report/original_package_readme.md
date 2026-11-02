# FPGA_COMPETION 项目总介绍

> **AC820 RiceVision：基于 Zynq-7000 与 MobileNetV2 的水稻叶片六分类系统**  
> 本文依据 `FPGA_COMPETION.rar` 内的源码、硬件配置及运行记录整理。下文路径均相对于解压后的 `FPGA_COMPETION/` 根目录；验证结果为包内记录，本次文档整理未重新执行编译或板级测试。

## 1. 项目概述

本项目面向水稻叶片图像分类，在 AC820 开发板上实现了从摄像头采集、图像预处理、FPGA 神经网络推理到触摸屏交互的完整流程。用户可以通过 LCD 查看画面，点击按钮识别当前图像、切换补光灯或保存采集数据。PYNQ 版本还支持通过 Jupyter 查看预览和操作应用。

系统采用 Zynq 的 PS／PL 协同架构：ARM 处理器负责外设控制、数据准备、网络调度和界面；FPGA 逻辑执行卷积、残差相加、全局平均池化与全连接等计算。模型采用折叠后的 MobileNetV2 结构，使用 16 位定点数据完成推理。

压缩包包含两套软件实现：

| 实现 | 运行环境 | 主要用途 | 主要入口 |
| --- | --- | --- | --- |
| `pynq_port/` | AC820 PYNQ 2.7、Linux、Python／Jupyter | 现有系统演示、外设调试、固定输入测试与 Python 开发 | `board/00_one_click_start.ipynb`、`lanuch.py` |
| `vitis/` | Vitis 裸机 C 程序 | 独立启动、驱动与界面开发、嵌入式软件构建 | `board/vitis_2025_2/app_src/src/main.c` |

两套实现沿用原 HLS 加速核及模型接口。`trash`、`trash_pynq`、`trash_weight` 等名称是历史工程标识，当前源码中的实际应用是**水稻叶片分类**。这些文件名仍参与脚本、导入和参数加载，整理目录时应保留。

## 2. 主要功能

- **图像采集与预览**：通过 OV5640 采集图像，在 800×480 LCD 上显示，PYNQ 版可同时输出浏览器预览。
- **六分类识别**：点击 Detect，对当前帧运行一次完整网络，显示分类结果与推理耗时。识别同步执行，期间预览会短暂停顿。
- **触摸与补光**：通过 GT911 触摸屏操作界面，控制相机补光功能。
- **数据保存**：PYNQ 版保存原始 BGR、Q10 输入和元数据；新版 Vitis 裸机版每次保存一张 BMP 图片。
- **调试与复现**：提供分步 Notebook、固定文件推理入口、主机侧测试、板级运行记录及构建检查脚本。

分类结果的索引顺序固定如下，标签拼写与源码保持一致：

| 索引 | 标签 |
| --- | --- |
| 0 | `healthy` |
| 1 | `bacterial_leaf_blight` |
| 2 | `brown_spot` |
| 3 | `leaf_blast` |
| 4 | `leaf_scald` |
| 5 | `narrow_brown` |

网络输出是六个原始定点分数，程序取最大值对应的类别。当前功能是整幅输入图像分类，未实现病斑定位、目标检测框或分割；原始分数也不能直接解释为经过校准的概率。

## 3. 硬件与系统架构

### 3.1 平台组成

| 项目 | 配置 |
| --- | --- |
| 开发板 | AC820 |
| FPGA 器件 | Zynq-7000，`xc7z020clg484-2` |
| PS 处理器 | ARM Cortex-A9 |
| 板载 DDR | 约 1 GiB |
| 相机 | OV5640 |
| 显示与触摸 | 800×480 LCD、GT911 触摸控制器 |
| 视频传输 | AXI VDMA、视频输入／输出及 VTC 等模块 |
| 推理控制与数据访问 | AXI-Lite 控制寄存器、AXI Master／PS HP 端口访问 DDR |
| 当前 PYNQ 运行记录 | PYNQ 2.7.0，使用配套的 3.3 V PL Overlay |
| 裸机软件适配 | Vitis 2025.2；所复用的硬件输出来自 Vivado 2019.2 |

AC820 使用 PYNQ 软件框架，并不意味着其引脚、镜像或外设配置与 PYNQ-Z2 通用。当前板级配置中，PL 使用 3.3 V Overlay，触摸涉及的 PS MIO50/51 仍为 1.8 V，二者属于不同 I/O Bank，应按配套配置使用。

### 3.2 数据流

```text
OV5640 摄像头
    │
    ▼
224×224 BGR888 图像 ───────────────► LCD／浏览器预览
    │
    ▼
PS 预处理：BGR→RGB、CHW 排列、归一化与 Q10 转换
    │
    ▼
DDR：输入、模型参数、中间特征缓冲
    ▲                         │
    │      AXI 数据访问       ▼
    └──────── PL HLS 加速核 ──┘
              ▲
              │ PS 按层配置寄存器并启动
              ▼
       六个原始分数 → argmax → 类别与耗时显示
```

PS 按网络顺序反复调度四类 HLS IP，层间特征经 DDR 缓冲传递。硬件并非为每一层分别配置一个独立计算核，也不是整网层间全流水实现。

| HLS 核 | 作用 |
| --- | --- |
| `conv` | 首层标准卷积 |
| `pwdwconv` | 复用执行逐点卷积（PW）和深度卷积（DW） |
| `shortcut` | 倒残差结构中的残差相加 |
| `fc` | 尾部全局平均池化与六分类全连接 |

## 4. 模型与数据约定

网络由 **Head → 16 个倒残差块 → Tail** 组成。倒残差块执行逐点扩展、深度卷积与逐点投影，尺寸满足条件时执行残差相加；尾部将特征扩展到 1280 通道，再完成全局平均池化和分类。

一次完整推理共有 **63 次核调用**：1 次标准卷积、34 次 PW、17 次 DW、10 次残差相加、1 次 FC。PW 与 DW 共用同一个硬件 IP。

| 数据 | 格式与说明 |
| --- | --- |
| 相机原始帧 | `224×224×3`，交错 BGR888，`uint8`，150,528 字节 |
| 网络输入 | RGB、CHW，16 位有符号 Q10，301,056 字节 |
| 磁盘权重 | 106 个小端 `float32` 参数文件，共 8,858,008 字节 |
| 权重加载 | 浮点值乘 1024，向零截断并转为 `int16` |
| HLS 运算类型 | `ap_fixed<16,6,AP_RND,AP_SAT>`，含 10 位小数 |
| 中间特征 | 四通道打包，布局为 `[C/4,H,W,4]`，不能当作普通 CHW 直接重排 |
| 分类输出 | 6 个 `int16` 原始分数 |

像素归一化的核心表达式为：

```text
q = trunc((pixel × 2048 − 255 × 1024) / 255)
```

它将像素的 0～255 映射到约 −1024～1024。相机路径还保留了原工程的绿色通道 `200/256` 衰减，因此相机输入与普通离线图片的处理配置需要区分。预处理、类别顺序、参数文件名以及定点转换共同构成模型接口，修改其中任一项都需要重新核对输出。

## 5. 目录导航

以下仅列出主要维护入口，省略生成工作区、缓存和大量中间产物。

```text
FPGA_COMPETION/
├─ pynq_port/                         # PYNQ / Python 运行分支
│  ├─ README.md
│  ├─ RUN_GUIDE_CN.md                  # 当前使用与启动手册
│  ├─ API_REFERENCE_CN.md              # Python API 说明
│  ├─ PYTHON_CODE_INDEX.md             # 代码阅读索引
│  ├─ lanuch.py                       # 一键启动器，保留现有拼写
│  ├─ board/
│  │  ├─ 00_one_click_start.ipynb       # 推荐演示入口
│  │  ├─ 01_bringup_and_demo_optimized.ipynb
│  │  ├─ infer_file.py                 # 固定 BGR / Q10 文件推理
│  │  ├─ overlays/                    # 配套 bit、HWH、manifest
│  │  └─ linux/                       # Linux 外设配置与触摸修复
│  ├─ src/trash_pynq/                 # 模型、硬件控制、外设与 UI
│  ├─ data/trash_weight/              # 106 个模型参数文件
│  ├─ build/                          # 硬件准备与辅助构建脚本
│  ├─ sim/                            # 数据契约、模型、外设与 UI 软件测试
│  ├─ tests/                          # 启动器生命周期等测试
│  └─ report/                         # 运行、性能与审计记录
└─ vitis/                             # 裸机软件及原硬件工程
   ├─ board/vitis_2025_2/
   │  ├─ README.md                    # 软件迁移、构建与验证说明
   │  ├─ app_src/                     # 新版裸机源码维护入口
   │  ├─ hardware/                    # 复用的 XSA 等硬件输入
   │  ├─ artifacts/                   # ELF、BOOT.BIN 及构建记录
   │  ├─ tests/                       # MMIO、LCD、SD 等回归测试
   │  └─ run_build.ps1                # 软件构建入口
   └─ src/
      ├─ trash/                      # 原 Vivado 工程及 Block Design
      └─ hls/                        # 原 HLS 源码与工程
```

PYNQ 分支中，`model.py` 负责模型与数据格式，`kernels.py` 负责 HLS 寄存器调用和缓存同步，`peripherals.py` 负责摄像头、触摸与视频外设，`ui.py`／`preview.py` 负责界面与预览，`overlay.py` 负责硬件文件及接口检查。这些文件均位于 `src/trash_pynq/`。

裸机分支中，`app_src/src/main.c` 负责初始化和事件循环，`camera_detection.c` 连接检测流程，`mess.c` 负责页面与交互，`app_src/Lib/Net/` 保存推理调度、层操作、PL 调用和参数读取逻辑。

## 6. PYNQ 运行方法

### 6.1 环境准备

使用与 AC820 配套的 PYNQ 系统，并将完整的 `pynq_port/` 放入板上工程目录。包内现有运行路径为：

```text
/home/xilinx/jupyter_notebooks/pynq_port
```

当前运行包依赖已配置的 Linux I²C、GPIO、CMA 和触摸引脚环境，并非完整 SD 卡系统镜像。若重新制作系统，先阅读 `board/linux/README.md` 及 `board/linux/touch_fix/README.md`。

### 6.2 Jupyter 一键启动

浏览器访问 `http://<开发板实际IP>:9090/tree`，打开 `pynq_port/board/00_one_click_start.ipynb`，运行启动单元。包内曾使用的地址为 `192.168.5.9`，实际部署以当前板卡地址为准。

也可以在工程根目录下的 Notebook 中执行：

```python
import lanuch

app = lanuch.start()
```

启动器完成文件检查、硬件占用检查、触摸修复、Overlay 加载、外设初始化与权重加载，并复用分步 Notebook 中的实现。

| 操作 | Python 调用 |
| --- | --- |
| 识别当前帧 | `app.request('detect')` |
| 切换补光 | `app.request('light')` |
| 保存当前帧 | `app.request('save')` |
| 查看状态 | `app.status()` |
| 停止并释放资源 | `await app.stop()` |

仅调试外设时使用 `lanuch.start(enable_model=False)`；希望关闭浏览器图像编码时使用 `lanuch.start(browser_fps=0)`。更改启动参数前先停止已有实例。

### 6.3 SSH 启动

在现有板上目录和虚拟环境配置下执行：

```bash
sudo /usr/local/share/pynq-venv/bin/python3 \
  /home/xilinx/jupyter_notebooks/pynq_port/lanuch.py
```

SSH 模式在 LCD 上显示应用，按 `Ctrl+C` 停止。Jupyter、SSH 和底层独立调试程序应依次使用，切换前先停止当前实例，以确保 DMA、缓冲区和硬件状态正确释放。页面服务可开机启动，完整识别应用仍需通过入口主动启动。

### 6.4 保存的数据

PYNQ 版保存到 `data/captures/`，每次产生同一时间戳的三类文件：

- `_bgr.bin`：原始 BGR888 图像。
- `_q10.bin`：可供推理复现的 RGB／CHW 小端 `int16` 输入。
- `.json`：格式、预处理配置和运行状态等元数据。

元数据中的“上次识别类别”可能来自此前的检测，不能直接当作本次保存图像的真实标签。需要固定输入复测时，使用 `board/infer_file.py`，参数和计时范围见运行手册。

## 7. Vitis 裸机版本开发

新版维护目录为 `vitis/board/vitis_2025_2/`，修改应用时以 `app_src/` 为准。构建脚本会将其同步到生成的应用工作区，因此 IDE 内的修改应先保存回 `app_src/`。

先按该目录 README 核对本机 Vitis、工作区和 XSA 路径，再在该目录执行：

```powershell
.\run_build.ps1 -Stage all
python .\verify_build.py
python .\tests\run_host_tests.py
python .\package_boot.py
```

仅修改应用时可使用 `-Stage app`。原脚本配置的工具入口为 `D:/AMD/2025.2/Vitis/bin/vitis.bat`，迁移到其他电脑时需要按实际安装位置调整。

打包顺序为 **新 FSBL → 原 2019.2 PL bitstream → 新应用 ELF**，主要产物为 `artifacts/trash_app.elf` 和 `artifacts/BOOT.BIN`。这部分完成的是 Vitis 2025.2 软件／BSP 适配，不能据此认定 Vivado 硬件已在 2025.2 中重新综合和实现。

裸机 SD 启动还需要根目录下的 `trash_weight/` 参数文件；压缩包中的参数可在 `pynq_port/data/trash_weight/` 找到，部署时需保持 106 个文件的名称与浮点格式。参数不由编译流程生成。新版保存按钮将图片写入 `Test/IMG00001.BMP` 等文件，并自动跳过已有文件。

裸机 `BOOT.BIN` 与 PYNQ 的 Linux 启动环境属于两条部署路线，使用时按对应分支说明准备启动介质。

如需重新构建 PL，先阅读原 Vivado／HLS 工程。`pynq_port/build/prepare_vivado.py` 的默认输入仍引用旧的 `original/trash` 和 `original/hls` 布局；当前压缩包对应源码位于 `vitis/src/trash`、`vitis/src/hls`，应显式核对输入路径，不能直接按旧默认目录运行。

## 8. 已有验证与性能记录

包内较新的运行手册和记录表明，PYNQ 分支已完成摄像头、LCD、触摸及完整应用的板上联调；Vitis 2025.2 分支则记录了软件构建和回归结果，仍将新版裸机上板验证标记为未完成。

| 项目 | 包内记录 | 主要依据 |
| --- | --- | --- |
| PYNQ 完整应用 | Jupyter／SSH 启动，Detect、Save、Light、停止、重启和竞争实例拒绝通过 | `pynq_port/report/runtime_launch_validation.json` |
| 固定输入推理 | 同一 Q10 输入重复 10 次，输出一致；中位约 **278.6 ms**，P95 约 **279.9 ms** | `pynq_port/report/board_run.json` |
| 相机／LCD 预览 | 独立 LCD 模式约 **7.50 FPS**；同时提供 2 FPS 网页图像时，LCD 循环约 **5.97 FPS** | `pynq_port/report/camera_fps_optimized.json` |
| GT911 触摸 | 连续通信读取及实际触摸操作记录，修复服务已启用 | `pynq_port/report/touch_debug_status.json` |
| PYNQ 主机侧测试 | 41 项，0 失败、0 错误、2 跳过 | `pynq_port/report/host_tests.json` |
| Vitis 软件构建 | 平台、BSP、FSBL、应用编译及 Bootgen 打包通过；`hardware_tested` 为 `false` | `vitis/board/vitis_2025_2/verification.json`、`artifacts/manifest.json` |

固定输入推理时间包含输入复制、MMIO 调用和缓存同步，排除摄像头采集、图像预处理与显示。预览 FPS 反映相机／显示循环速度，不能当作完整识别帧率；交互应用中的检测耗时也可能因计时范围不同而更长。

目前包内尚未提供完整数据集分类精度、CPU 加速比、功耗，或同一输入下 PYNQ 与 Vitis 全网输出位精确一致的完整报告。现有运行记录可以说明链路已运行，不能代替上述指标的测量。

## 9. 后续阅读与维护建议

| 目的 | 优先阅读 |
| --- | --- |
| 运行现有演示 | `pynq_port/RUN_GUIDE_CN.md` |
| 查 Python API 和文件职责 | `pynq_port/API_REFERENCE_CN.md`、`pynq_port/PYTHON_CODE_INDEX.md` |
| 理解网络调度和数据格式 | `pynq_port/src/trash_pynq/model.py`、`pynq_port/report/application_audit.md` |
| 修改裸机程序和重新打包 | `vitis/board/vitis_2025_2/README.md`、`app_src/` |
| 理解 PL 结构与 HLS 算法 | `vitis/src/trash/trash.xpr`、`vitis/src/hls/` |
| 查已有结果及其测试范围 | `pynq_port/report/`、`vitis/board/vitis_2025_2/verification.json` |

阅读时注意版本时间：PYNQ README 顶部及 `RUN_GUIDE_CN.md` 已更新到 2026-10-24，而部分旧审计文档仍保留 10 月 23 日“待板测”的历史状态；原 Vivado 工程说明也有旧任务名称。遇到冲突时，应结合当前源码、硬件配置和对应测试记录判断。

后续可优先补充固定数据集精度评估、两套软件的同输入输出对比及完整端到端耗时测量。在这些基础上，再评估更改定点位宽、调整 HLS 核或重新构建硬件带来的收益。
