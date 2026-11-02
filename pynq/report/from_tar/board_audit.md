# AC820 PYNQ 材料与原工程外设审计

审计日期：2026-10-23。只读检查原资料，未连接或操作开发板。大型镜像未完整解压，未写入 SD 卡。

## 本地证据

原资料目录：`E:\work\FPGA\小梅哥AC820型ZYNQ或安路FPSoC开发板资料\13_附赠应用\Pynq`。

| 文件 | 证据与用途 |
| --- | --- |
| `编译生成的镜像\AC820_ZYNQ_Pynq_Boot_img-2.7.0.zip` | ZIP 含 `ACZ820_ZYNQ-2.7.0.img`，解压大小 8,070,719,488 字节。文件名说明配套版本为 PYNQ 2.7.0；尚未运行该镜像验证。 |
| `Vivado_Project\PYNQ_Project.zip` | Vivado 2020.2 工程；`PYNQ_Project/PYNQ_Project/PYNQ_Project.xpr` 器件 `xc7z020clg484-2`。其 `system.hwh` 仅有 `processing_system7_0`；`base1.bit` 不是叶病识别加速器 overlay。 |
| `Vivado_Project\Pynq_Axi_Gpio.zip`、`Pynq_Ps_Gpio.zip` | 配套 GPIO 示例；不应覆盖本项目带 VDMA、摄像头、卷积核的 PL。 |
| `PYNQ_Base_Pack.tar.gz` | 2,418,158,150 字节。包含 `pynq-2.7.0.tar.gz`、`focal.arm.2.7.0_2021_11_17.tar.gz` 和 `PYNQ-image_v2.7/` 源码。小规模提取 `pynq/gpio.py`、`pynq/lib/video/dma.py`、Pynq-Z2 spec 和 DTS 供 API 核查；未展开根文件系统压缩包。 |

少量解压证据位于 `E:\work\FPGA\Qian\board_audit_tmp`。基础 HWH 的完整路径为：

`E:\work\FPGA\Qian\board_audit_tmp\PYNQ_Project\PYNQ_Project\PYNQ_Project.gen\sources_1\bd\system\hw_handoff\system.hwh`。

原 Vitis HWH 从 `E:\work\FPGA\Qian\original\vitis_trash\design_1_wrapper_3.3v.xsa` 提取，路径：

`E:\work\FPGA\Qian\board_audit_tmp\original\design_1.hwh`，其根节点记载 Vivado 2019.2。

## 基础 PYNQ 与原硬件差异

| 配置 | PYNQ 基础工程 | 原 3.3V Vitis XSA |
| --- | --- | --- |
| PS DDR 范围 | `0x00100000..0x3fffffff`，约 1 GiB | 原工程也为 Zynq-7020；视频 HP1/HP2 地址窗口只到 `0x1fffffff` |
| Ethernet0 | 启用，MIO16..27 | 禁用 |
| SD0 / UART1 | MIO40..45 / MIO48..49 | 相同 |
| I2C0 | 禁用 | 启用，MIO50..51；GT911 |
| I2C1 | 禁用 | 启用，EMIO；OV5640 |
| EMIO GPIO | 禁用 | 仅 1 位，PS GPIO54 / EMIO0；GT911 reset |
| GPIO MIO0 | 需核查启动 pinctrl | 原 `lcd.h` 指定触摸 INT 为 MIO0 |
| FCLK0 / FCLK1 | 50 MHz / 关闭 | 100 MHz / 约 32.727 MHz（参数名义值 33 MHz） |

加载 `.bit/.hwh` 不等于修改 Linux 启动的 PS MIO 复用和设备树。原 Vitis FSBL 也不能直接替换 PYNQ 的 BOOT.BIN：其 PS 配置禁用了网络。现已从实际板商 FIT 提取 DTB，编译外设配置并输出 `board/linux/boot_patch/image.ub`，离线确认内核与非目标属性保持不变；该新文件尚未验证板上启动。使用条件、备份恢复步骤和源码复现见 `board/linux/README.md`，实际内核证据见 `board_image_audit.md`。旧 `.dtsi` 仅作源码集成参考。

配套 tar 中 Pynq-Z2 `system-user.dtsi` 虽把两个 I2C 节点设为 okay，但未据此证明 AC820 当前运行镜像的 MIO pinctrl、EMIO 和时钟正确。驱动因此根据 Linux sysfs 的控制器地址确定 I2C 总线，而不猜测 `/dev/i2c-0` 与 `/dev/i2c-1`。原摄像头最终使用 40 kHz，总线频率未证实时拒绝初始化。

本次资料未提供已经核实的 AC820 镜像默认 IP、登录帐号或密码；不能把其他 PYNQ 板型的常见默认值写成此镜像的实测值。

## 原外设与迁移实现

源目录：`E:\work\FPGA\Qian\original\vitis_trash\Trash_LCD_OV5640\Lib`。

- `OV5640/OV5640.h`：255 组原寄存器初始化值；输出 224×224 RGB565，PL 转成 DDR BGR888。
- `OV5640/OV5640.c`：4077 字节原自动对焦固件，64 字节分块写入传感器 `0x8000`；这是摄像头内部固件地址，并非裸机 DDR 地址。保留原 AF 命令、状态轮询、2 秒超时、灯控制以及彩条测试。
- `LCD/lcd.c`：184 字节 GT911 配置；`LCD/font.h`：12/16/24/32 高度的 95 个 ASCII 字符字库。均自动提取，源文件和结果 SHA256 位于 `data/peripherals/manifest.json`。
- `LCD/lcd.h`：800×480、BGR888；默认 180 度旋转。触摸 reset 为 PS54，INT 为 MIO0；没有使用 PS55/56 的依据。
- 原触摸复位时 INT 拉高，但访问地址写为 `0x5d`。Linux 官方 goodix 驱动的地址选择规则为 INT 高对应 `0x14`，INT 低对应 `0x5d`。移植保留 `0x5d`，复位期间改为 INT 拉低，读取 `911` 产品 ID 后才继续。
- GT911 的配置更新 Fresh 字节必须为 1；它不应被当作“是否写持久化 NVM”的开关。保留 1。触摸采用用户态轮询，不复用裸机 GIC 中断代码；验证最多 5 点、清除 ready 标志、抬手清空旧坐标。

`src/trash_pynq/peripherals.py` 提供独立的 Linux I2C、OV5640、GT911、LCDFrame 与 VideoDMA。摄像头与 LCD 共用一个 AXI VDMA，但分别操作 S2MM 与 MM2S，禁止初始化一个通道时复位另一个。原 `C_NUM_FSTORES=1`；摄像头每次等待完整帧、停写并确认 halt 后才 invalidate 和复制，避免原裸机单缓冲边采边拷贝的撕裂。单缓冲 LCD 更新仍可能在扫描中出现撕裂，要完全消除需重建支持双缓冲的 PL/VDMA。

视频缓冲通过 `pynq.allocate` 分配，起始地址 8 字节对齐，整个缓冲必须低于 `0x20000000`。上半区 CMA 会被拒绝，不会改写裸机 `0x12000000/0x12300000`。Linux 应提供该窗口内的 CMA；是否应更改启动 CMA 配置需依据板上实际内存分布。对象通过全局强引用保留直到 `close()`，halt/reset 失败时继续保留，避免 Python 回收仍被 DMA 访问的内存。

## 验证范围

`sim/test_peripherals.py` 的 13 项主机测试通过，覆盖原 C 数据逐字节重提取、I2C combined transaction、ID/频率失败、自动对焦分块、触摸地址/校验和/按下抬手、MIO0/EMIO0 映射、BGR/旋转、VDMA 通道隔离、512 MiB 窗口，以及停机失败后内存保留。测试使用模拟 MMIO/I2C，不代表传感器、屏幕时序、板卡供电或 Linux 镜像已经实测通过。

板端仍需确认：镜像启动、PYNQ/XRT/CMA、设备树与 MIO 复用、实际 GPIO 独占、I2C 外设响应、摄像头完整帧、LCD 方向与触摸坐标、推理准确度和时延。不能将本次主机测试写成“已经完美上板”。

## LCD 界面与设计预览

`src/trash_pynq/ui.py` 的 `LeafUI` 在 800×480 逻辑坐标中生成浅绿背景、深绿操作按钮与深蓝结果卡。左侧 336×336 摄像头预览，右侧六类英文短标签、时延、保存数量和状态，底部三个 40 像素高触摸按钮。使用自动提取的原 ASCII 字库，无需板端 Pillow、OpenCV 或字体安装。

`sim/test_ui.py` 的 5 项主机测试通过，覆盖六类渲染、原帧不被修改、按钮边界、灯开关状态、旋转及非法输入。`ui.physical_frame()` 执行一次原 LCD 的 180 度旋转；GT911 默认已经把物理触摸坐标转换为逻辑坐标，不应再次翻转触摸。

设计图 `report/lcd_ui_preview.png` 为等待画面，`report/lcd_ui_preview_identified.png` 使用原始 `original/python_trash/Out.bin` 的 224×224 BGR 帧。该原帧本身偏绿且模糊，预览保持原像素。图中的 `Leaf blast`、128 ms 和已保存 12 张均是布局示例，状态明确标注 `UI preview - example result`，不代表该帧实测分类结果或实测速度。

## 官方技术依据

- [Linux i2c-dev 用户态接口](https://www.kernel.org/doc/html/latest/i2c/dev-interface.html)：总线编号动态分配；`I2C_RDWR` 支持 combined read；`I2C_SLAVE` 使用七位地址。
- [Linux Goodix 原厂衍生驱动](https://github.com/torvalds/linux/blob/master/drivers/input/touchscreen/goodix.c)：GT911 地址选择、产品识别与配置校验。
- [PYNQ GPIO 源码文档](https://pynq.readthedocs.io/en/v2.5/_modules/pynq/gpio.html)：PS GPIO 逻辑号到 Linux GPIO 号映射。实际实现另与本地配套 PYNQ 2.7 `pynq/gpio.py` 核对，确认 GPIO54 偏移及 `release()` API。
