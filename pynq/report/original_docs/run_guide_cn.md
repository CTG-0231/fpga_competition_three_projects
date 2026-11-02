# AC820 RiceVision 运行手册

适用版本：2026-10-24 的板上调试版本。当前开发板地址为 **192.168.5.9**，主机名为 `pynq`，系统为 AC820 的 PYNQ 2.7。工程在板上的目录是：

```text
/home/xilinx/jupyter_notebooks/pynq_port
```

当前实物已经确认 PL 使用 **3.3V** 位流；PS 的 MIO50/51 保持原工程 **1.8V** 配置。这两处属于不同 I/O Bank，不要一起改电压。

本运行包适用于当前已经完成 Linux I²C、GPIO 和 CMA 配置的 SD 卡系统，不是整张 SD 卡镜像。若重新烧录原始厂商系统，先按 `board/linux/README.md` 完成外设配置。复制到另一套系统后，启动器可以在启动时应用触摸修复；要让修复服务开机自启，按 `board/linux/touch_fix/README.md` 安装服务。

本次已完成摄像头、LCD 预览和触摸通信调试，用户确认触摸问题已修复。普通预览在当前链路上约 6 FPS；关闭网页图像编码的独立 LCD 测试约 7.5 FPS。点击识别会同步运行推理并更新结果，期间预览会有短暂停顿。

## 1. 开机后打开页面

1. 按现有连接接好 LCD、摄像头和网线，再给开发板上电。
2. 等待 Linux 启动。板上 `jupyter.service` 和 `pl_server.service` 会启动；已安装的 `ac820-touch-pinctrl.service` 会在它们之前恢复触摸引脚配置。
3. 在电脑浏览器打开 [Jupyter 文件列表](http://192.168.5.9:9090/tree)。如果 DHCP 后续又换地址，使用新 IP；也可在本地能解析主机名时访问 [pynq:9090](http://pynq:9090/tree)。
4. 输入当前 Jupyter 密码。密码由登录页面输入，不保存在启动代码中。
5. 打开 `pynq_port → board → 00_one_click_start.ipynb`，运行启动单元即可。

直接打开启动页：

[00_one_click_start.ipynb](http://192.168.5.9:9090/notebooks/pynq_port/board/00_one_click_start.ipynb)

启动顺序如下：

```text
开机 → Linux 服务/触摸引脚修复 → Jupyter 页面
     → lanuch.start() → 检查文件/取得硬件锁
     → 加载 3.3V Overlay → 摄像头/LCD/触摸
     → 加载 106 个权重 → 预览与按钮
```

页面服务开机自启，完整识别应用由启动单元启动。当前没有把摄像头推理应用设置为开机后自动运行。

## 2. 一键启动

本次检查未发现完整应用的一键入口，因此新增工程根目录的 **`lanuch.py`**，文件名按用户指定拼写。它复用已经在板上验证的分步 Notebook 代码，并统一管理启动、停止与硬件占用。

### 在 Jupyter 启动

推荐打开新的 `board/00_one_click_start.ipynb` 并运行唯一的启动代码单元。也可以在工程根目录下的 Notebook 中调用：

```python
import lanuch
app = lanuch.start()
```

从 `board/` 目录下的 Notebook 直接执行脚本：

```python
%run ../lanuch.py
```

默认启动摄像头、自动对焦、LCD、GT911 触摸、真实模型和网页预览。网页图像以独立的 2 FPS 更新，LCD 尽可能快地更新。

只调试摄像头和 LCD，暂不加载模型：

```python
import lanuch
app = lanuch.start(enable_model=False)
```

优先保证 LCD 速度，关闭网页图像编码：

```python
import lanuch
app = lanuch.start(browser_fps=0)
```

要更改启动参数，先停止已有实例，再重新 `start()`。重复调用 `start()` 会返回当前实例，不会再次加载位流。

### 从 SSH 启动 LCD 应用

在电脑终端连接开发板，密码由 SSH 交互输入：

```powershell
ssh xilinx@192.168.5.9
```

连接后运行这一条命令：

```bash
sudo /usr/local/share/pynq-venv/bin/python3 /home/xilinx/jupyter_notebooks/pynq_port/lanuch.py
```

该模式在 LCD 上运行相机预览和触摸操作，不把网页图像编码到 SSH 终端。保持终端进程运行；按 `Ctrl+C` 会正常停止并清理硬件。

以下参数可组合使用：

```bash
# 只读检查文件、阶段标签和当前触摸引脚配置，不下载位流
sudo /usr/local/share/pynq-venv/bin/python3 /home/xilinx/jupyter_notebooks/pynq_port/lanuch.py --check

# 不加载模型，运行摄像头/LCD/触摸
sudo /usr/local/share/pynq-venv/bin/python3 /home/xilinx/jupyter_notebooks/pynq_port/lanuch.py --no-model

# 有限时间运行，用于检查启动和清理
sudo /usr/local/share/pynq-venv/bin/python3 /home/xilinx/jupyter_notebooks/pynq_port/lanuch.py --duration 10
```

同一块 PL 和相机缓冲只能由一个运行实例管理。Jupyter 模式和 SSH 模式请先停止当前实例再切换。启动器与更新后的原分步 Notebook 共用文件锁，会拒绝另一个应用实例；运行底层独立脚本前仍须先停止并清理当前应用。

## 3. 操作与停止

| 操作 | LCD / 网页按钮 | Python 调用 |
| --- | --- | --- |
| 识别当前帧 | Detect | `app.request('detect')` |
| 切换补光灯 | Light | `app.request('light')` |
| 保存当前帧 | Save | `app.request('save')` |
| 停止并清理 | 网页 Stop；SSH 中 Ctrl+C | `await app.stop()` |
| 查看状态 | 网页状态栏 | `app.status()` |
| 获取当前实例 | — | `lanuch.get_app()` |

按钮动作在下一轮预览中执行。请求识别时，页面显示模型的原始六分类结果；分数不是经过校准的概率。

在 Jupyter 中停止：

```python
await app.stop()
# 也可使用模块级入口：
await lanuch.stop()
```

一键入口的 Stop 会统一执行资源清理。若使用旧分步 Notebook，仍须先按 Stop，再运行它最后的清理单元。

清理顺序会先结束预览，确认 DMA 停止，再释放摄像头和显示缓冲、触摸 GPIO、I²C、模型中间缓冲与权重。若 DMA 停止失败，代码会保留引用和硬件锁；此时按报错处理，保留内核并重启开发板恢复，避免直接强杀后让活动 DMA 访问已释放的内存。

## 4. 保存的文件

点击 Save 后，数据位于：

```text
data/captures/<时间戳>_bgr.bin   224×224×3 uint8，BGR888，150528 字节
data/captures/<时间戳>_q10.bin   RGB/CHW，little-endian int16 Q10，301056 字节
data/captures/<时间戳>.json      帧格式、绿色补偿和最近一次标签等信息
```

最近一次标签可能属于之前识别的帧，不应直接当成此次保存帧的标注；JSON 中明确保存了这一说明。

在板上的 Python 中读取：

```python
from pathlib import Path
import numpy as np

capture = Path('/home/xilinx/jupyter_notebooks/pynq_port/data/captures')
path = sorted(capture.glob('*_bgr.bin'))[-1]
frame_bgr = np.fromfile(str(path), dtype=np.uint8).reshape(224, 224, 3)
```

## 5. 分步调试入口

`board/01_bringup_and_demo_optimized.ipynb` 保留完整分步流程，便于单独检查：

| 阶段标签 | 内容 |
| --- | --- |
| `ricevision:setup` | 导入模块、确定工程目录与配置 |
| `ricevision:overlay` | 校验 bit/HWH 并下载位流 |
| `ricevision:peripherals` | 摄像头、VDMA、LCD 与触摸初始化 |
| `ricevision:model` | 权重与推理器初始化 |
| `ricevision:preview` | LCD / 网页预览与操作 |
| `ricevision:cleanup` | 停止 DMA 并释放资源 |

启动器按标签唯一查找这些代码阶段；标签缺失或重复会报错，不会猜测执行哪个单元。`build/make_notebook.py` 已同步生成这些标签和启动器目录注入支持。

## 6. Python 接口与完整源码

完整调用说明见 [API_REFERENCE_CN.md](API_REFERENCE_CN.md)。全部 Python 文件及其函数/方法索引见 [PYTHON_CODE_INDEX.md](PYTHON_CODE_INDEX.md)。工程包保留 `.py` 原始源码，便于查看完整实现。

| 文件 | 主要用途 |
| --- | --- |
| `lanuch.py` | 一键启动、停止、状态和按钮动作 |
| `src/trash_pynq/peripherals.py` | Linux I²C、OV5640、GT911、LCDFrame 和 VideoDMA |
| `src/trash_pynq/overlay.py` | bit/HWH/manifest 校验与加载 |
| `src/trash_pynq/model.py` | 六分类标签、预处理、权重、MobileNet 调度 |
| `src/trash_pynq/kernels.py` | HLS 核寄存器调用、超时与性能跟踪 |
| `src/trash_pynq/ui.py` | 800×480 界面、按钮命中、图像旋转 |
| `src/trash_pynq/preview.py` | 静态界面缓存配套的 LCD 局部更新 |
| `src/trash_pynq/reference.py` | 软件参考实现 |
| `board/infer_file.py` | 对保存的 BGR / Q10 文件执行固定输入推理 |
| `board/linux/touch_fix/` | 触摸 pinctrl 修复、开机服务与回退说明 |
| `build/` | 诊断、Notebook 生成、导出、打包和构建辅助代码 |

所有需要 PYNQ 的底层示例均在开发板上运行。单独写脚本调用工程模块时，先把源码目录加入路径：

```python
from pathlib import Path
import sys
ROOT = Path('/home/xilinx/jupyter_notebooks/pynq_port')
sys.path.insert(0, str(ROOT / 'src'))
```

### 对固定输入执行推理

先停止预览应用并清理硬件，再运行：

```bash
cd /home/xilinx/jupyter_notebooks/pynq_port
sudo /usr/local/share/pynq-venv/bin/python3 board/infer_file.py \
  --board ac820 --variant 3v3 --io-voltage 3.3 \
  --input data/samples/original_infer_q10.bin --input-format q10-bin \
  --repeat 10 --output report/board_run.json
```

把输入换成某个保存的 `*_bgr.bin` 时，使用 `--input-format bgr-bin`。该脚本的统计不包括摄像头采集和 LCD 显示，不能将其推理吞吐当作摄像头 FPS。

## 7. 触摸修复与系统服务

触摸问题来自 Linux 启动配置遗漏了强制三态的解除。当前配置为：MIO0=`0x0600`、MIO50/51=`0x1240`。GT911 地址为 `0x5d`，产品 ID 为 `911`；INT 地址选择和复位时序由原驱动负责。

在 SSH 中检查：

```bash
systemctl status ac820-touch-pinctrl.service --no-pager
sudo /usr/bin/python3 /usr/local/sbin/ac820-touch-pinctrl.py --check
systemctl status jupyter.service pl_server.service --no-pager
```

修复通过 Linux 设备树 overlay 和驱动重新绑定应用，不修改 `BOOT.BIN` 或 `image.ub`。本次服务已经启用并实际启动成功；没有为了验证该服务再次重启开发板。回退与重装步骤见 `board/linux/touch_fix/README.md`。

## 8. 常见问题

| 现象 | 处理 |
| --- | --- |
| 浏览器打不开 | 核对实际 IP、网线和 `jupyter.service`；SSH 正常时检查 `systemctl status jupyter.service` |
| 提示另一个实例占用 | 在原页面按 Stop 并清理，或在原 SSH 进程按 Ctrl+C；不要同时下载另一份位流 |
| 一键启动时检测到旧分步程序 | 回到旧 Notebook 按 Stop，再执行最后清理单元，然后重试 |
| `No Devices Found` | 使用上述 PYNQ 虚拟环境解释器；工程包导入会补齐该镜像的 XRT 默认路径 |
| 触摸 `EAGAIN` | 检查 `ac820-touch-pinctrl.service` 和只读 `--check`；旧内核中仍持有 GPIO 时先正常清理 |
| 画面慢 | `browser_fps=0` 优先保证 LCD；查看 `app.status()`；识别和状态变化时的整屏更新会短暂增加耗时 |
| 原分步初始化提示已有 `ol` | 先执行该 Notebook 的清理单元，不要直接重跑初始化 |
| DMA 停止或硬件重置失败 | 保留当前进程/内核，按错误提示重启开发板，再启动应用 |

## 9. 本次验证记录

摄像头、LCD 和触摸的历史测量分别位于 `report/camera_fps_optimized.json`、`report/touch_debug_status.json`。一键入口的实际验证结果记录在 `report/runtime_launch_validation.json`。性能数字对应具体采样方式，不代表分类准确率或整套硬件的理论最大帧率。
