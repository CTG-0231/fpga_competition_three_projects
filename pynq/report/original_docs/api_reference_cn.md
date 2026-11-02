# AC820 PYNQ Python API 完整索引

整理日期：2026-10-24（Asia/Shanghai）。适用板卡：AC820 / Zynq-7000 `xc7z020clg484-2`，当前地址 `192.168.5.9`，PYNQ 2.7，OV5640、GT911、800×480 LCD，用户已确认 PL I/O Bank 使用 3.3 V 版本。

本文件按源码 AST 和函数实现整理公共调用接口，覆盖 `src/trash_pynq/`、`board/infer_file.py`、`build/` 及触摸修复脚本内全部 Python 入口。以下路径均相对板上工程根目录 `/home/xilinx/jupyter_notebooks/pynq_port`；本机完整运行源码归档位于 `camera_debug/runtime_release/`，已核对其中全部 `src/trash_pynq/*.py` 与已部署优化版一致。

范围约定：名称不以 `_` 开头的模块函数、类和方法全部列出；构造函数及 I²C 上下文管理方法另列。内部 `_...` 实现细节不作为稳定公共接口。Notebook 中定义的控制函数和一键启动入口另列。

## 1. 导入与数据约定

在板上 Python / Jupyter 中：

```python
from pathlib import Path
import sys
ROOT = Path('/home/xilinx/jupyter_notebooks/pynq_port')
sys.path.insert(0, str(ROOT / 'src'))

from trash_pynq.overlay import inspect_overlay, load_overlay
from trash_pynq.peripherals import (
    PeripheralError, load_data, raw_mmio, discover_ps_i2c, LinuxI2C,
    OV5640, make_ps_gpio_factory, GT911, LCDFrame, VideoDMA,
)
from trash_pynq.model import (
    BlockConfig, CONFIGS, LABELS, INPUT_SHAPE, NUM_CLASSES,
    weight_specs, validate_weights, load_weights, preprocess_bgr, MobileNetRunner,
)
from trash_pynq.kernels import KernelTimeout, Kernels
from trash_pynq.ui import LeafUI
from trash_pynq.preview import PreviewPresenter
```

| 数据 | 精确约定 |
| --- | --- |
| 相机原始帧 | NumPy `uint8`，形状 `(224, 224, 3)`，BGR888；文件 150528 字节 |
| 模型输入 | `int16`，RGB、CHW，形状 `(3, 224, 224)`，或长度 150528 的一维数组；小端文件 301056 字节 |
| 模型输出 | 六个原始有符号 Q10 `int16` logits，按 `LABELS` 排列；文件 12 字节；它们不是概率 |
| LCD 逻辑画布 | `uint8`、BGR888，形状 `(480, 800, 3)`；触摸按钮使用这一坐标系 |
| LCD 物理帧 | 逻辑帧旋转 180°；使用 `LeafUI.physical_frame()` 或 Presenter 自动处理；只旋转一次 |
| 颜色常量 | Python 整数 `0xRRGGBB`，绘制时转成 BGR 通道 |
| 权重源文件 | 106 个硬件专用 folded float32 小端 `.bin`；乘 1024、向零截断转换为 Q10 `int16` |
| HLS DMA 数组 | 使用 `pynq.allocate` 分配的连续 `int16` 设备缓冲；普通 NumPy 数组没有 DMA 地址 |
| 相机/LCD DMA 数组 | VideoDMA 自行申请；8 字节对齐，全部位于物理地址 `0 < addr < 0x20000000` 范围内 |

`trash_pynq.__init__` 仅声明 `__version__ = '0.1.0'`；在发现 `/usr/lib/libxrt_core.so` 且环境未设置时补 `XILINX_XRT=/usr`，用于支持 `sudo` 后的 PYNQ XRT。该模块没有额外公共函数。

六类标签依次为：`healthy`、`bacterial_leaf_blight`、`brown_spot`、`leaf_blast`、`leaf_scald`、`narrow_brown`。显示类别使用 `LABELS[int(np.argmax(logits))]`。

## 2. Overlay：`trash_pynq.overlay`

| 签名 | 用途、返回值与依赖 |
| --- | --- |
| `inspect_overlay(directory)` | 不下载位流。读取 `manifest.json`，核验器件、`leaf.bit`/`leaf.hwh` SHA256、4 个 HLS IP 寄存器合同和 VDMA/VTC 地址；成功返回 manifest 字典。普通主机可运行，但需完整资源。 |
| `load_overlay(directory, board, io_voltage)` | 先执行完整性检查，再调用 PYNQ `Overlay` 下载 PL；`board='ac820'`，`io_voltage='3.3'` 或 `'1.8'` 必须与 manifest 和实际板卡一致；返回 PYNQ Overlay。**会改变硬件状态**。 |

公开常量 `EXPECTED_REGISTERS` 保存 `conv_0`、`fc_0`、`pwdwconv_0`、`shortcut_0` 的寄存器偏移合同。当前目录选择为 `ROOT / 'board/overlays/3v3'`。加载前应停止并清理同板上的其他预览/推理实例，不能与正在使用旧位流的程序并行。

```python
overlay_dir = ROOT / 'board/overlays/3v3'
manifest = inspect_overlay(overlay_dir)  # 仅验证文件
# 需要启动硬件时，在旧实例已清理后执行：
ol = load_overlay(overlay_dir, board='ac820', io_voltage='3.3')
```

## 3. 相机、触摸和 LCD：`trash_pynq.peripherals`

### 3.1 公共工具与异常

| 签名 | 用途、返回值与注意点 |
| --- | --- |
| `PeripheralError` | 外设合同、寄存器状态、设备标识或资源验证失败；继承 `RuntimeError`，没有自定义构造参数。 |
| `load_data(name, directory=None)` | 校验 `data/peripherals/manifest.json` 后返回文件 `bytes`；默认数据目录由包路径推导，校验失败抛 `PeripheralError`。 |
| `raw_mmio(overlay, name)` | 从 `overlay.ip_dict[name]` 建立 PYNQ MMIO 映射。VDMA 应用它，避开 PYNQ 默认 AxiVDMA 驱动对未连接中断的要求。仅板上可用。 |
| `discover_ps_i2c(controller, sysfs='/sys/class/i2c-dev')` | `controller` 只能 0/1；根据控制器物理地址匹配设备树，返回 `(Linux总线编号, 设备树时钟Hz或None)`；不硬编码 `/dev/i2c-N` 的编号。 |
| `make_ps_gpio_factory(hwh_path)` | 从 HWH 验证 MIO0 和恰好一个 EMIO GPIO，再返回 `factory(pin, direction)`；仅允许 `pin=0/54` 和 PYNQ GPIO 操作。GT911 使用 MIO0 为 INT、PS54 为 RESET。 |

### 3.2 `LinuxI2C`

| 签名 | 用途、返回值与注意点 |
| --- | --- |
| `LinuxI2C(bus, *, frequency_hz=None, dev_root='/dev')` | 打开 `/dev/i2c-<bus>`；仅 Linux。`frequency_hz` 是配置元信息，不会在用户态修改时钟。 |
| `LinuxI2C.for_ps_controller(controller, *, bus=None, sysfs='/sys/class/i2c-dev')` | 类方法；先自动发现 0/1 号 PS 控制器并读取时钟，再构造连接。可传 `bus` 验证用户指定编号与发现结果一致。 |
| `check_address(address)` | 使用非 FORCE 的 `I2C_SLAVE` 检查地址占用，防止绕过内核已绑定设备。 |
| `write_reg(address, register, payload)` | 7 位 I²C 地址、16 位寄存器地址（大端发出）；`payload` 接收单字节整数或 bytes 类对象；发送后返回空 `bytes`。 |
| `read_reg(address, register, length=1)` | 使用组合写地址/读数据事务读取，返回 `bytes`；`length >= 1`。 |
| `close()` | 关闭本连接的文件描述符；可重复调用。不会替所有者关闭外设对象。 |
| `__enter__()` / `__exit__(*args)` | 支持 `with LinuxI2C.for_ps_controller(...) as bus:`；退出时自动 `close()`。 |

PS I²C1（控制器 1）接 OV5640，设备树要求 **40000 Hz**；PS I²C0（控制器 0）接 GT911，当前系统配置 **300000 Hz**。设备地址为 OV5640 `0x3c`、GT911 `0x5d`。生产应用应让同一程序持有连接，并在退出时关闭。

```python
# 只读触摸产品 ID；应在没有其他程序并发访问该设备时执行。
with LinuxI2C.for_ps_controller(0) as bus:
    print(bus.read_reg(0x5d, 0x8140, 4))  # 已初始化/供电正常时通常 b'911\x00'
```

### 3.3 `OV5640`

| 签名 | 用途、返回值与注意点 |
| --- | --- |
| `OV5640(bus, *, data_dir=None, sleep=time.sleep, timeout=2.0)` | 构造传感器控制对象；`bus` 是 LinuxI2C 或兼容对象，构造本身不配置传感器。 |
| `initialize(*, autofocus=True)` | 验证 I²C1 为 40 kHz、资源校验和、芯片 ID `0x5640`，写相机寄存器表；默认加载 AF 固件并自动对焦；耗时操作。 |
| `initialize_autofocus()` | 已初始化相机后加载 `ov5640_af.bin` 并等待 AF 就绪；AF 已就绪时直接返回。 |
| `focus()` | 触发一次自动对焦并等待完成；要求 `af_ready=True`；超时抛 `TimeoutError`。 |
| `release_focus()` | 释放 AF 模式并等待回到就绪状态；要求 AF 已初始化。 |
| `set_light(enabled)` | 相机初始化后切换补光；`True/False`。退出时应主动设为 `False`。 |
| `set_test_pattern(pattern=0)` | `0` 正常画面，`1` 彩条，`2` 滚动彩条；用于链路诊断，正常运行恢复为 `0`。 |

公开状态：`initialized`、`af_ready`，常量 `ADDRESS=0x3c`。相机对象没有 `close()`；关闭它使用的 I²C 连接前先关闭补光。初始化不负责建立 VideoDMA，采集使用后面的驱动。

### 3.4 `GT911`

| 签名 | 用途、返回值与注意点 |
| --- | --- |
| `GT911(bus, gpio_factory, *, data_dir=None, flip=True, sleep=time.sleep)` | 创建触摸驱动，默认将物理坐标旋转 180°到 LCD 逻辑坐标。 |
| `initialize()` | 校验 184 字节配置，申请 GPIO、复位并用 INT 低电平选择 `0x5d`，核验产品 ID，写入配置。需要 Linux pinctrl 修复已应用。 |
| `poll()` | 轮询并确认新数据，返回 `[(x, y), ...]`，最多 5 点；同步维护 `points`、`pressed`、`just_pressed`；无新报告时保留上一次状态。只在 `just_pressed` 时触发按钮，可避免按住后反复操作。 |
| `close()` | 释放 INT/RESET GPIO 资源并将 `initialized=False`；I²C 连接由调用者另外关闭。 |

公开状态：`address`、`points`、`pressed`、`just_pressed`、`initialized`。默认 `flip=True` 的变换为 `(799-x, 479-y)`；坐标范围为 `0≤x<800`、`0≤y<480`。不要对 `poll()` 返回值再次旋转。

```python
touch_bus = LinuxI2C.for_ps_controller(0)
touch = GT911(touch_bus, make_ps_gpio_factory(overlay_dir / 'leaf.hwh'))
touch.initialize()
points = touch.poll()
if touch.just_pressed and len(points) == 1:
    print(ui.hit_test(*points[0]))  # 'detect' / 'light' / 'save' / None
# 正常退出：touch.close(); touch_bus.close()
```

触摸修复由板上 `ac820-touch-pinctrl.service` 提供，应用对应 DT overlay。当前运行状态已验证；不要在已有 GPIO 消费者的应用运行中重做解绑/绑定。详见运行文档与 `board/linux/touch_fix/`。

### 3.5 `LCDFrame`：基础画布

| 签名 | 用途、返回值与注意点 |
| --- | --- |
| `LCDFrame(*, flip=True, data_dir=None)` | 分配 CPU 端 `(480,800,3)` 黑色逻辑 BGR 画布。 |
| `clear(color=0)` | 原地填充整幅画布。 |
| `rectangle(x, y, width, height, color)` | 原地绘制实心矩形，超屏部分裁剪，宽高非正时无操作。 |
| `picture(frame_bgr, x=352, y=16, scale=2)` | 将 `HxWx3 uint8` 图像按正整数倍最近邻放大，写入指定位置；边界裁剪。 |
| `text(x, y, text, *, font=32, color=0x00ff00, background=0)` | 使用随包 ASCII 字体原地绘制；字体仅 12/16/24/32，支持 ASCII 32–126 与换行。 |
| `physical_frame()` | 返回连续的物理帧；`flip=True` 时旋转 180°。 |

公开像素数组为 `pixels`。这些绘图操作不需要 PYNQ 硬件；文字需要字体资源。此类是原始通用绘图工具；当前完整 Leaf Health 界面使用 `LeafUI`。

### 3.6 `VideoDMA`：相机采集与 LCD 输出

| 签名 | 用途、返回值与注意点 |
| --- | --- |
| `VideoDMA(mmio, parameters, *, allocator=None, timeout=2.0)` | 验证原设计 VDMA 参数，默认使用 PYNQ allocate。该驱动只支持原设计的单帧缓存、24 位输入/输出、32 位地址、非 SG 配置。 |
| `start_capture()` | 分配并复位 `(224,224,3)` 相机缓冲；它只准备资源，真正启动采集的是 `read_frame()`。 |
| `read_frame()` | 运行单帧采集，等待完整帧后停止 S2MM，invalidate 后返回独立的 CPU NumPy BGR 副本。首帧异常最多重试一次。 |
| `start_display(vtc_mmio)` | 分配 `(480,800,3)` LCD 缓冲，启动 MM2S/VTC；保留 HWH 中 800×480 时序。传 `ol.v_tc_0.mmio`。 |
| `write_display(frame_bgr)` | 将**物理朝向**的 `(480,800,3) uint8` BGR 帧写入并 flush；需先启动显示。 |
| `close()` | 分别停止采集和显示 DMA，确认停稳后释放缓冲。停止超时则抛异常并保留仍可能由 DMA 持有的内存。 |

公开成员：`capture_buffer`、`display_buffer`、`mmio`、`timeout`、`ERROR_MASK=0xff0`。`capture_buffer` 与 `display_buffer` 为驱动所有，调用者不应直接 `freebuffer()`。Presenter 使用 `display_buffer` 的部分更新通道，但仍通过驱动的 DMA 约束工作。

```python
camera_bus = LinuxI2C.for_ps_controller(1)
camera = OV5640(camera_bus)
camera.initialize(autofocus=True)
video = VideoDMA(raw_mmio(ol, 'axi_vdma_0'),
                 ol.ip_dict['axi_vdma_0']['parameters'])
video.start_capture()
video.start_display(ol.v_tc_0.mmio)
raw = video.read_frame()

# 基础绘图示例，与 LeafUI/Presenter 二选一使用：
canvas = LCDFrame()
canvas.clear(0xffffff)
canvas.picture(raw)
canvas.text(20, 20, 'Camera ready', font=24)
video.write_display(canvas.physical_frame())

# 仅在预览循环已经停止且无其他使用者时正常清理：
# video.close()   # 若它报停机超时，保留进程/引用，先处理硬件
# camera.set_light(False)
# camera_bus.close()
```

## 4. 优化界面与预览：`trash_pynq.ui` / `trash_pynq.preview`

### 4.1 `LeafUI`

| 签名 | 用途、返回值与注意点 |
| --- | --- |
| `LeafUI(data_dir=None)` | 校验并加载字体，预编译相机装饰 LUT，初始化固定上限的几何缓存；CPU 端运行。 |
| `hit_test(x, y)` | 使用逻辑坐标判断按钮，返回 `'detect'`、`'light'`、`'save'` 或 `None`。 |
| `render(frame_bgr=None, label=None, latency_ms=None, light=False, status='Ready', saved_count=0)` | 返回独立的 `(480,800,3) uint8` **逻辑方向** BGR 界面。相机帧必须为 224×224；label 必须为六类之一或 None；latency_ms 为非负有限数；saved_count 为非负整数。相同 UI 状态时只更新相机图块。 |
| `physical_frame(frame=None)` | 将指定逻辑帧或当前内部画布旋转 180°，返回连续物理帧；供 `video.write_display()` 使用。 |

模块公开常量 `BUTTONS`、`LABEL_TEXT`；类公开常量 `WIDTH=800`、`HEIGHT=480`、`BUTTONS` 及配色 `BG/WHITE/INK/NAVY/MUTED/GREEN/BORDER/PALE`。文本仅支持随包 ASCII 字体，状态字符串应使用英文/ASCII。

| 动作 | 逻辑矩形 `(x, y, width, height)` |
| --- | --- |
| detect | `(20, 432, 244, 40)` |
| light | `(278, 432, 244, 40)` |
| save | `(536, 432, 244, 40)` |

### 4.2 `PreviewPresenter`

| 签名 | 用途、返回值与注意点 |
| --- | --- |
| `PreviewPresenter(ui, video=None)` | 绑定 LeafUI；`video=None` 时只渲染，不写 LCD。提供公开 `fps` 运行采样值。 |
| `present(raw, **state)` | 调用 `ui.render(raw, **state)`，返回逻辑帧。绑定视频时检查显示已启动和 VDMA 错误位，状态不变只写 LCD 相机区域，状态改变写完整帧，并 flush。`**state` 对应 render 的 `label/latency_ms/light/status/saved_count`。 |

Presenter 内部处理旋转，调用时应传相机原始 BGR 和逻辑 UI 状态，不要预先 `physical_frame()`。`fps` 是每秒左右更新的提交帧率估计，初始为 0，不表示用光学设备实测的面板刷新率。

```python
ui = LeafUI()
presenter = PreviewPresenter(ui, video)
raw = video.read_frame()
logical = presenter.present(raw, status='Ready', saved_count=0)
print('LCD loop estimate:', presenter.fps)

# 无硬件预览/导出：
from PIL import Image
logical = LeafUI().render(raw, label='healthy', latency_ms=123,
                          light=False, status='Identified', saved_count=1)
Image.fromarray(logical[:, :, ::-1]).save('/tmp/leaf_ui.png')
```

## 5. 模型调度：`trash_pynq.model`

| 签名/常量 | 用途、返回值与注意点 |
| --- | --- |
| `BlockConfig(ch_in, ch_mid, ch_out, h, w, stride)` | NamedTuple 构造函数，字段均为 int；描述一个倒残差 block。继承 tuple 的常规方法可用。 |
| `CONFIGS` | 原网络 16 个倒残差 block 的固定配置 tuple。 |
| `LABELS` / `INPUT_SHAPE` / `NUM_CLASSES` | 六类标签 tuple、`(3,224,224)`、`6`。 |
| `weight_specs()` | 返回按原网络顺序排列的 `{文件名: float32元素个数}` 字典，共 106 项。 |
| `validate_weights(directory)` | CPU 端验证全部权重大小、有限性、Q10 转换范围；成功返回 None；失败给出累积错误清单；不分配设备内存。 |
| `load_weights(directory, allocator)` | 再次完整验证后分配、填充并 flush 所有 `int16` 设备权重；返回 `{文件名: 设备缓冲}`。`allocator` 通常为 `pynq.allocate`，须先下载 Overlay。**返回缓冲由调用者所有**。 |
| `preprocess_bgr(frame, green_gain_num=200, green_gain_den=256)` | 224×224 BGR uint8 → 连续 RGB CHW int16；绿通道默认乘 200/256，整数归一化范围 [-1024,1024]，负数按 C 向零截断。没有 resize/crop/gamma。增益必须是整数且 `0≤num≤den≤2147483647`、`den>0`。 |
| `MobileNetRunner(kernels, allocator, weights)` | 验证所有设备权重，分配可复用激活缓冲；权重仍归调用者。 |
| `MobileNetRunner.run(image_q)` | 串行运行原始 63 个 HLS 调用，返回 CPU 所有的六个 int16 logits 副本；输入形状为 CHW 或等长一维 int16。一个 runner 禁止并发使用。 |
| `MobileNetRunner.close(assume_hardware_stopped=False)` | 释放自己分配的激活缓冲；故障后只有先确认 PL 已重置/停止，才可显式用 `True`。该参数是对硬件状态的断言，不执行硬件复位。 |

硬件权重是专门导出的 folded 布局，不能将通用 MobileNet checkpoint 文件直接替换，也不要自行转置、重新排列。Runner 的异常可能发生在 AXI 访问已经启动之后；必须保留 runner、kernels、weights 引用，先停视频并成功重置 PL，之后才释放相关 CMA。

以下例子假设 `ol` 已独占下载，`raw` 已采集；结束时统一交给启动程序/Notebook 的清理流程：

```python
import numpy as np
from pynq import allocate
validate_weights(ROOT / 'data/trash_weight')
weights = load_weights(ROOT / 'data/trash_weight', allocate)
kernels = Kernels(ol, timeout=5.0)
runner = MobileNetRunner(kernels, allocate, weights)
logits = runner.run(preprocess_bgr(raw))
label = LABELS[int(np.argmax(logits))]
print(label, logits.tolist())

# 正常完成并停止所有使用者后：
# runner.close()
# for buffer in weights.values():
#     buffer.freebuffer()
# weights.clear()
```

## 6. HLS 底层接口：`trash_pynq.kernels`

通常由 MobileNetRunner 调用。高级用户可直接调用，但必须自行保证原 HLS packed 布局、缓冲长度、物理地址、层配置和内存生命周期；大小验证不是完整的数学布局验证。

| 签名 | 用途与长度要求（均按 int16 元素数） |
| --- | --- |
| `KernelTimeout` | 继承 `TimeoutError`。等待 HLS done 超时；此时 PL 可能仍访问 DMA，不能直接 freebuffer 或重启内核释放进程内存。 |
| `Kernels(overlay, timeout=5.0)` | 缓存四个 HLS IP 句柄；timeout 为正有限秒数；构造后公开 `faulted=False`、`trace=[]`。 |
| `Kernels.address(buffer)` | 静态方法；验证 int16 连续 PYNQ 设备数组和缓存同步方法，要求 8 字节对齐且整个缓冲位于原 HWH 的 1 GiB AXI 地址窗内，返回 DMA 地址整数。 |
| `conv(source, weight, bias, output)` | 固定 head 3×3 卷积；最少长度依次为 `3*224*224`、`32*3*3*3`、`32`、`32*112*112`。 |
| `pw(source, weight, bias, output, ch_in, ch_out, act, size)` | pointwise 卷积；输入 `ch_in*size²`，权重 `ch_in*ch_out`，bias `ch_out`，输出 `ch_out*size²`；`act` 为 0/1。 |
| `dw(source, weight, bias, output, channel, size, stride)` | depthwise 卷积；输入 `channel*size²`，权重 `channel*9`，bias `channel`，输出 `channel*(size/stride)²`；stride 只能 1/2 且整除 size。 |
| `shortcut(source1, source2, output, length)` | 残差相加；三个缓冲至少 length，length 为正；实际数据需匹配原四 lane 算法。 |
| `fc(source, weight, bias, output)` | 固定 1280×7×7 池化+六类 FC；最少长度 `1280*7*7`、`1280*6`、`6`、`6`；Runner 为输出预留 8 个元素以容纳完整总线 beat。 |

所有算子负责输入/输出缓存同步、检查 IP 是否忙、设置指针与标量、启动和轮询完成；成功返回 None，输出写入传入缓冲。`trace` 为 `{'ip': 名称, 'seconds': 耗时}` 的列表，可在每次推理前 `kernels.trace.clear()` 避免无限累计。故障后对象拒绝复用，需重置硬件并重建实例。此类没有 `close()`；自己管理其传入缓冲。

## 7. CPU 数值参考：`trash_pynq.reference`

这些函数不需要 PYNQ，可用于桌面测试。它们是原 HLS 的部分算子参考，并非完整 MobileNet CPU 推理实现。

| 签名 | 用途、输入与返回值 |
| --- | --- |
| `pack_chw(chw)` | 连续/非连续 CHW int16 → 一维 `[C/4,H,W,4]` packed int16；C 必须能被 4 整除，lane0 对应 AXI 最低 16 位。 |
| `unpack_chw(packed, channels, height, width)` | 按给定 C/H/W 将 packed int16 还原为独立连续 CHW 数组；校验大小和 C%4。 |
| `multiply_q10(left, right)` | Q10 乘法；四舍五入到最近，恰好半值朝正无穷，再饱和到 int16。支持 NumPy 广播。 |
| `mac_q10(accumulator, left, right)` | 一次原 HLS Q10 乘加赋值，按原规则舍入并在此次赋值饱和。 |
| `shortcut_q10(left, right)` | 同形状 int16 数组饱和相加；总元素数必须能被 4 整除。 |
| `avgpool_fc_q10(packed_input, weights, bias)` | 原 FC：packed 1280×7×7 输入、6×1280 int16 权重、6 个 int16 bias → 六个 int16 logits；保留每级饱和池化树、21/1024 量化倒数、bias-first 逐通道舍入。 |

```python
import numpy as np
from trash_pynq.reference import pack_chw, unpack_chw, shortcut_q10
x = np.arange(4*2*2, dtype=np.int16).reshape(4, 2, 2)
assert np.array_equal(unpack_chw(pack_chw(x), 4, 2, 2), x)
print(shortcut_q10(np.array([32760, -32760, 1, -1], np.int16),
                   np.array([100, -100, -1, 1], np.int16)))
# [32767, -32768, 0, 0]
```

## 8. 保存文件推理：`board/infer_file.py`

| 签名 | 用途与注意点 |
| --- | --- |
| `read_input(path, input_format)` | `bgr-bin` 要求 150528 字节，读取并调用 preprocess；`q10-bin` 要求 301056 字节，按小端 int16 CHW 读取。返回模型输入数组。命令行只允许这两种格式。 |
| `read_golden(path)` | 要求恰好 12 字节，读取六个小端 int16 logits，返回 NumPy 数组。 |
| `reset_on_fault(overlay)` | 调用 `overlay.download()` 复位 PL；若失败则保持进程存活并要求先断电，避免仍活动 AXI 主设备访问已归还内存。它不是日常停止按钮。 |
| `main()` | 解析命令行、预检查、加载硬件/权重、1 次 warm-up 后重复推理、记录实测 JSON；正常返回 0，golden 不一致返回 3；finally 中复位故障 PL 并释放设备内存。 |

```bash
cd /home/xilinx/jupyter_notebooks/pynq_port
# 先停止并清理实时应用，避免重加载 PL 冲突。
sudo python3 board/infer_file.py --board ac820 --variant 3v3 \
  --io-voltage 3.3 --input data/captures/某次采样_bgr.bin \
  --input-format bgr-bin --repeat 5 --output report/board_run.json
```

全部 CLI 参数：`--board ac820`（必填）、`--variant {3v3,1v8}` 或互斥的 `--overlay-dir`、`--io-voltage {3.3,1.8}`（必填）、`--weights`（默认 `data/trash_weight`）、`--input`（必填）、`--input-format {bgr-bin,q10-bin}`（必填）、`--golden`、`--repeat`（默认 5，范围 1–10000）、`--timeout`（默认 5 秒）、`--output`（默认 `report/board_run.json`）。测量范围含输入拷贝、MMIO、cache sync，不含相机采集/预处理/LCD 输出。

## 9. 优化 Notebook 的可调用控制函数

入口页面：`http://192.168.5.9:9090/notebooks/pynq_port/board/01_bringup_and_demo_optimized.ipynb`。这些函数依赖该 Notebook 按顺序初始化后的全局变量，不是独立 pip 包 API。

| 签名 | 用途与注意点 |
| --- | --- |
| `request_action(action)` | `action='stop'` 将 running 置 False；其他值写入单个 pending_action。预览循环识别 `'detect'`、`'light'`、`'save'`。单槽机制会以最后一次请求覆盖尚未执行的动作。 |
| `async preview_loop()` | 循环采集、读取触摸、执行动作、Presenter 更新 LCD、按 BROWSER_FPS 限频编码网页 JPEG，更新 metrics 并 await 让出事件循环；依赖 ol/video/camera/ui/presenter 等全局实例。 |

```python
request_action('detect')  # 对下一帧推理
request_action('light')   # 切换补光
request_action('save')    # 保存下一帧
request_action('stop')    # 只请求停止循环；之后还要执行 Notebook 清理单元
```

保存动作会生成 `<时间戳>_bgr.bin`、`<时间戳>_q10.bin`、`<时间戳>.json` 到 `data/captures/`。JSON 的 `last_label` 是最近一次推理结果，`last_label_is_from_this_frame=False` 表明它不一定来自当前保存帧。`BROWSER_FPS=0` 关闭网页图像编码更新，LCD 继续运行；页面状态文字仍可更新。执行循环前可设置 `LCD_TARGET_FPS` 和 `BROWSER_FPS`，实际帧率受采集和 CPU 绘制耗时限制。

## 10. 构建与离线维护脚本：全部公共入口

这一组主要用于工作站或离线维护，不是正常 LCD 运行的前置步骤。多数 CLI 可用 `python3 路径 --help` 查看参数；`make_notebook.py`、`package_release.py`、`test_host.py` 不是 argparse CLI，运行会直接生成相应文件。

### 10.1 `build/doctor.py`

| 签名 | 用途 |
| --- | --- |
| `main()` | 只读检查 Overlay 文件对、106 个权重文件大小、平台、I²C、CMA；可输出 JSON。返回 0 表示权重文件齐全且尺寸正确，2 表示缺失/尺寸错误；不代表已经执行板级推理。 |

CLI：`--variant {3v3,1v8}`（默认 3v3）、`--overlay-dir`、`--weights`、`--output`。示例：`python3 build/doctor.py --variant 3v3 --output report/doctor.json`。更严格的权重内容检查使用 `validate_weights()`。

### 10.2 `build/export_overlay.py`

| 签名 | 用途 |
| --- | --- |
| `sha256(data)` | 字节 SHA256 十六进制字符串。 |
| `bit_part(data)` | 解析 Xilinx `.bit` 文件头中的器件字段，返回字符串。 |
| `export(xsa, output, io_voltage=None)` | 从 XSA 中提取恰好一组 bit/HWH，校验器件及 HLS 寄存器，写 `leaf.bit`、`leaf.hwh`、`manifest.json`，有条件导出参考 BD Tcl；返回 manifest。它不综合硬件、不下载硬件。 |

CLI：`python3 build/export_overlay.py 输入.xsa 新输出目录 --io-voltage 3.3`。没有同名文件推断的已知原始 XSA 时必须明确传电压；输出目录内同名文件会写入。

### 10.3 `build/prepare_vivado.py`

| 签名 | 用途 |
| --- | --- |
| `digest(path)` | 文件 SHA256。 |
| `within(path, parent)` | Path.relative_to 方式判断路径包含关系，返回 bool；调用者应传预先 resolve 的 Path。 |
| `inspect_ip(root)` | 检查 conv/fc/pwdwconv/shortcut 四个原 packaged HLS IP 的 VLNV、版本、路径局部性及文件完整性；返回 `(IP信息字典, 最小pointwise_bias深度或None)`。 |
| `prepare(project_root, ip_root, output, timing_xdc=None, target_version='2025.2')` | 校验并逐字节复制 BD、RTL、约束和打包 IP 到全新且不重叠的输出目录，生成 prepare_manifest.json/config.tcl，返回 manifest。只准备，不运行 Vivado。target_version 支持 2019.2/2025.2。 |

CLI：`--project-root`、`--ip-root`、`--output`、`--timing-xdc`、`--target-version {2019.2,2025.2}`。

### 10.4 `build/inspect_fdt.py`

| 签名 | 用途 |
| --- | --- |
| `parse_fdt(blob)` | 从 bytes 解析 FIT/FDT，返回含 nodes、版本、大小、启动 CPU、内存保留表的字典；不挂载、不执行。 |
| `string(value)` | 去尾部 NUL 后按 UTF-8 解码，非法字符替换。 |
| `cells(value)` | 将长度可被 4 整除的 bytes 按大端 32 位 cell 解码为整数列表；否则返回空列表。 |
| `describe(value)` | 将 DT 属性 bytes 转为可 JSON 表示的字符串/bool/cell/hex/摘要。 |
| `summarize_tree(tree)` | 摘要输出 I²C/GPIO/pinctrl/内存/FPGA 等节点和 phandle/clock 解析。 |
| `decompress_candidate(payload, offset, algorithm)` | 从指定偏移按 gzip/xz/bzip2 解压内核候选，最多 128 MiB；返回解压 bytes。 |
| `inspect_kernel(payload, fit_compression)` | 搜索内核版本及嵌入 IKCONFIG，返回相关配置证据字典。未发现配置不等同于功能未启用。 |
| `inspect(path)` | Path 输入 FIT 或 DTB，返回 `(报告字典, 被选中的系统DTB字节)`；核验可识别的 payload hash。 |
| `main()` | CLI 入口。 |

CLI：`python3 build/inspect_fdt.py image.ub --output report/fit.json --export-dtb work/system.dtb`。无 output 时打印报告；只有显式 export-dtb 才导出原始所选 DTB。

### 10.5 `build/inspect_boot_image.py`

| 签名 | 用途 |
| --- | --- |
| `main()` | 读取 vendor ZIP 内唯一磁盘 img 的 MBR，离线导出唯一 FAT 启动分区（最大 512 MiB），写 boot_partition.img 和 partition_inventory.json；拒绝覆盖已有目标。不访问物理磁盘。 |

CLI：`python3 build/inspect_boot_image.py 厂商镜像.zip 全新输出目录`。

### 10.6 `build/validate_boot_dtb.py`

| 签名 | 用途 |
| --- | --- |
| `require(condition, message)` | 条件不成立抛 ValueError。 |
| `reservations(blob, tree)` | 解析 FDT 内存保留映射，返回 `[地址, 长度]` 列表。 |
| `validate(base, migrated)` | 传入两份 DTB bytes，严格核验已知厂商基准 SHA256、仅允许的 I²C/pinctrl 修改、频率、节点及保留映射，返回验证报告；不会应用 DTB 到硬件。 |
| `main()` | CLI 入口。 |

CLI：`python3 build/validate_boot_dtb.py 原始.dtb 迁移.dtb --output report/dtb_check.json`。此验证器针对历史基准设备树迁移，不等同于新增加的 GT911 pinctrl 修复服务验收。

### 10.7 `build/repack_fit.py`

| 签名 | 用途 |
| --- | --- |
| `sha256(data)` | 字节 SHA256。 |
| `require_cstring(value, description)` | 要求恰好一个 NUL 结尾 ASCII 字符串，返回去 NUL 字符串。 |
| `validate_fit(tree)` | 拒绝签名 FIT、外部 payload 和不支持 hash，验证所有内嵌 payload hash，返回每个图像的 hash 记录。 |
| `selected_images(tree)` | 验证默认 configuration 引用并返回 `(configuration路径, fdt路径, kernel路径)`。 |
| `write_its(tree, work_dir)` | 将树的原属性精确序列化为 ITS，内嵌 payload 写中间 bin，返回 `(ITS路径, payload记录列表)`。会写工作目录。 |
| `verify_properties(original, compiled, expected_changes)` | 验证节点、属性、保留内存、版本和 boot CPU 仅发生明确允许的变化，返回变化路径列表。 |
| `repack(source_fit, merged_dtb, dtc, output_dir, work_dir=None)` | 用 dtc 创建全新 FIT，仅替换默认 DTB 和其现有 hash，校验 kernel 字节保持一致，写 image.ub/manifest.json，返回 manifest。输出/工作目录必须新建且与输入隔离。 |
| `main()` | CLI 入口。 |

CLI：`python3 build/repack_fit.py 原始image.ub 替换.dtb --dtc /usr/bin/dtc --output-dir 全新输出目录 [--work-dir 全新中间目录]`。这只完成离线封装，不执行烧卡或部署。

### 10.8 Notebook 生成、打包和验证

| 文件/签名 | 用途与副作用 |
| --- | --- |
| `build/make_notebook.py: add(kind, source)` | 给全局 cells 追加 markdown/code cell；导入会构建内存中的 cells，不会写文件。作为 CLI 执行 `python3 build/make_notebook.py` 才会生成/覆盖分步 Notebook，供维护时使用。部署优化后应使用已同步优化的生成器。 |
| `build/package_release.py: selected_files()` | 迭代产生 `(文件Path, 相对Path)`，排除缓存、可执行/目标文件及多数工作目录；直接运行脚本生成 `../output/ac820_pynq_port.zip`、校验文件并执行 ZIP/hash 回读校验。 |
| `build/test_host.py` | 无公共函数；`python3 build/test_host.py` 发现并运行 `sim/` 测试，写 report/host_tests.log 与 host_tests.json，返回成功/失败退出码；只验证主机测试，不下载 PL。 |
| `build/reference/check_components.py: check(compiler, include)` | 使用供应商 ap_fixed.h 和 C++ 编译器编译原 FC/shortcut 组件，与 Python 数值参考比较；写组件可执行文件及 report/hls_component_reference.json，返回报告。不是完整网络或板级等价证明。 |

`check_components.py` CLI：`--compiler <g++可执行文件>`、`--include <含ap_fixed.h的目录>`。该脚本依赖完整原 HLS 源码和测试夹具，部分板上精简部署未携带，不属于日常运行必需资源。

## 11. 触摸持久化修复脚本

源文件：`board/linux/touch_fix/ac820-touch-pinctrl.py`；安装执行文件：`/usr/local/sbin/ac820-touch-pinctrl.py`。文件名含连字符，正常使用 CLI/systemd，无需把它 import 到预览进程。

| 签名 | 用途与注意点 |
| --- | --- |
| `read_mio()` | 通过只读 `/dev/mem` 映射读取 MIO0/50/51，返回 `{pin: 寄存器值}`；需要 root；不写 PS 寄存器。 |
| `format_mio(values)` | 将寄存器字典转为日志字符串。 |
| `overlay_status()` | 返回 configfs overlay status 字符串；目录不存在返回 None。 |
| `require_gpio_idle()` | 检查 debugfs GPIO 消费者和 sysfs export，无使用者才能返回；不能证明空闲则抛异常。 |
| `bound_drivers()` | 查找 I²C0/GPIO 平台驱动的 bind/unbind 接口，返回 `(driver Path, device name)` 列表。 |
| `rebind_all(detached)` | 按反序重绑定所有已解绑驱动，逐项尝试并返回失败字符串列表。 |
| `apply_fix(check_only=False)` | 正确配置已应用时无硬件副作用返回；否则检查空闲、通过 Linux DT overlay 及重新 probe 应用 pinctrl，再检查寄存器。`check_only=True` 只核验，状态不正确即抛错。 |
| `interrupted(signum, _frame)` | 信号处理函数，抛 RuntimeError 以进入清理路径。 |
| `main()` | 检查 root、加进程锁、安装信号处理并执行 apply/check；成功 0、失败 1。 |

```bash
# 只核验，无需中断正在正常工作的应用：
sudo python3 /usr/local/sbin/ac820-touch-pinctrl.py --check
sudo systemctl status ac820-touch-pinctrl.service --no-pager
```

正常应用 pinctrl 时优先由已安装服务在应用打开 GPIO/I²C 前执行。修复正确时重新调用走幂等路径；修复错误且有消费者时拒绝解绑，需先清理应用。该脚本不修改 BOOT.BIN、image.ub 或物理磁盘。

## 12. 一键启动：`lanuch.py`

文件名按用户指定保留为 **lanuch.py**。它读取 `board/01_bringup_and_demo_optimized.ipynb` 中唯一的 `ricevision:setup/overlay/peripherals/model/preview/cleanup` 标签单元，直接复用这些代码作为硬件流程；维护时继续以带标签的优化 Notebook 为唯一硬件流程来源。启动器另外负责参数、独占锁、进程内重复启动保护与自动清理。

| 签名 | 用途、返回值与注意点 |
| --- | --- |
| `start(io_voltage='3.3', enable_model=True, enable_touch=True, autofocus=True, browser_fps=2.0, root=None)` | 在**已运行的 asyncio 事件循环**中初始化并启动摄像头/LCD，返回 `Handle`。Jupyter 可直接调用。需要板上 root 和 PYNQ 环境；默认根目录为脚本所在目录。重复调用返回本进程现有 Handle；改变参数前先 `await app.stop()`。启用触摸时先应用/验证 pinctrl 修复。 |
| `get_app()` | 返回本进程当前 `Handle` 或 None；启动/清理故障且仍持有资源时也返回该 Handle，以便查询和重试停止。 |
| `async stop()` | 停止本进程当前应用并等待清理；无应用时无操作。 |
| `Handle(root, stages, lock)` | 启动器的资源所有者构造函数；root 为项目 Path、stages 为编译好的标签代码字典、lock 为已持有的文件锁。正常使用由 start 创建，不手工构造。 |
| `Handle.status()` | 返回 JSON 可序列化状态字典，读取本地缓存状态，不访问 PL；含 pid/root/running/stopping/stopped/io_voltage/browser_fps/model/touch/light/saved_count/last_label/last_ms/metrics/error/cleanup_error。 |
| `Handle.request(action)` | 请求 `'detect'`、`'light'`、`'save'` 或 `'stop'`；前三者排入预览单槽，stop 会安排完整停止清理。无效动作抛 ValueError；停止中的应用拒绝前三项。 |
| `async Handle.stop()` | 幂等停止并等待全部清理，调用者取消不会取消 DMA 清理任务；清理失败保留资源、应用引用和硬件锁，可处理故障后重试。 |
| `main(argv=None)` | 解析 CLI/%run 参数；Jupyter 返回 Handle/None，普通 CLI 返回退出码并通过 asyncio.run 管理完整生命周期。 |

推荐直接打开新增入口 `http://192.168.5.9:9090/notebooks/pynq_port/board/00_one_click_start.ipynb`；其中调用上述接口。也可以在项目内的 Jupyter 单元执行：

```python
%cd /home/xilinx/jupyter_notebooks/pynq_port
%run lanuch.py
# 生成全局 app；启动完成后可调用：
app.status()
app.request('detect')
app.request('save')
app.request('light')
# 结束时在后续单元执行：
await app.stop()
```

或直接 import：

```python
from lanuch import start, get_app, stop
app = start(browser_fps=0, enable_model=False)  # 只调相机/LCD/触摸
# …需要停止时：
await stop()
```

在 SSH 终端中运行，Ctrl+C 会停止并执行同一清理流程：

```bash
cd /home/xilinx/jupyter_notebooks/pynq_port
sudo /usr/local/share/pynq-venv/bin/python3 lanuch.py
# 可先做只读检查（不下载位流）：
sudo /usr/local/share/pynq-venv/bin/python3 lanuch.py --check
# 只运行预览 15 秒的联调：
sudo /usr/local/share/pynq-venv/bin/python3 lanuch.py --no-model --duration 15
```

全部 CLI 参数：`--io-voltage {3.3,1.8}`（默认 3.3）、`--no-model`、`--no-touch`、`--no-autofocus`、`--browser-fps N`（非负有限值；普通 SSH 默认 0，Jupyter/%run 默认 2）、`--check`、`--duration SECONDS`（正有限值，结束后清理）。`--check` 会验证 Notebook 标签、Overlay、可选权重及可选触摸 pinctrl 状态；需要 root 读取 MIO，状态不正确会失败，不会通过该选项修复硬件。

普通 Python 脚本中不要在事件循环外直接调用 start；使用 CLI，或在 `asyncio.run()` 执行的协程内调用并最终 `await app.stop()`。不要同时运行旧版 Notebook 硬件单元和启动器。启动器遇到当前内核残留 ol/video 会拒绝启动；跨进程的启动器和更新后的分步 Notebook 通过 `/run/lock/ac820-ricevision.lock` 互斥。正常关闭后才能启动另一实例，不应删除锁文件绕过占用。

## 13. 正确的资源停止顺序

1. 请求停止预览，等待异步任务确实结束。一键入口的 Stop 自动继续清理；原分步 Notebook 中仅设置 running=False 或点 Stop 后，仍须执行最后清理单元。
2. 调用 `video.close()`，必须确认采集与显示 DMA 都已停止；若它报错，不要直接重启 Python kernel、kill 进程或手动 freebuffer。
3. 关闭补光、`touch.close()` 释放 GPIO，随后关闭 camera_bus/touch_bus。
4. 正常推理结束调用 `runner.close()`；如果 HLS/runner 已故障，先在没有其他使用者时成功重新下载 Overlay，再 `runner.close(assume_hardware_stopped=True)`。
5. 最后逐个 `weights.values()` 的 `freebuffer()`，清空引用。权重不由 runner.close() 释放。

发生停机/硬件复位失败时，保留当前进程与缓冲引用，并先对开发板做受控重启/断电处理。不要通过释放 CMA 来尝试恢复 AXI。日常优先使用应用提供的停止/清理入口，由它统一管理生命周期。
