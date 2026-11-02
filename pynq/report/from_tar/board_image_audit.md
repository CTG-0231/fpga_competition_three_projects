# AC820 板商启动镜像的实际 FIT / DTB / 内核证据

核查日期：2026-10-23。只读解析主任务从镜像 FAT 分区提取的启动文件；没有挂载磁盘、修改原镜像/启动文件、写 SD 卡或连接开发板。

## 数据来源与复核方式

来源压缩包为板商 `AC820_ZYNQ_Pynq_Boot_img-2.7.0.zip`，包内 `ACZ820_ZYNQ-2.7.0.img`。本次只处理已提取的 `build/work/board_image/boot_files`。该工作区源数据不作为发布包内容；可交付证据为本报告、`report/board_image_fdt.json` 与 `build/inspect_fdt.py`。

| 项目 | 实际结果 |
| --- | --- |
| `image.ub` 长度 | 5,890,380 字节 |
| `image.ub` SHA256 | `b063e9f858a72875259832842d178b895ddfaae4100d0c2dec12bcf94a36b2d4` |
| FIT 描述 | U-Boot fitImage for PYNQ arm kernel |
| 默认配置 | `/configurations/conf@1`，选择 `kernel@0` 与 `fdt@0` |
| 内核 payload | 5,869,440 字节，FIT 属性 `compression=none`；内部是带 gzip 内容的 ARM 内核启动映像 |
| 系统 DTB | `/images/fdt@0`，19,123 字节、92 个节点 |
| 系统 DTB SHA256 | `28d656e6da69a652484d29210fe99ef990a105125d9d834666ca69736a427f2f` |
| FIT 内部校验 | 内核与 DTB 的原 SHA1 均与 payload 重算值一致；这只是原 FIT 完整性校验，不是厂商数字签名认证 |
| `REVISION` | Release / Board `2024_09_25 59515a9`，引用 Xilinx/PYNQ.git |

可复核命令（默认只输出 JSON；下例显式写报告）：

```bash
python3 build/inspect_fdt.py build/work/board_image/boot_files/image.ub \
  --output report/board_image_fdt.json
```

显式 `--export-dtb build/work/board_image/system.dtb` 可逐字节导出原 FIT 所选 DTB；本次已验证导出长度及 SHA256 与 FIT payload 相同。该脚本使用标准库解析，不调用 `dtc`、安装器或任何前台程序。截断 DTB 被拒绝；零值单元与字符串列表分别检查，避免把 `reg=<0 0x40000000>` 错判为字符串。

## 实际内核版本与配置

内核解压数据中识别到：

```text
Linux version 5.4.0-xilinx-v2020.2 (oe-user@oe-host)
(gcc version 9.2.0 (GCC))
#1 SMP PREEMPT Wed Sep 25 01:43:53 UTC 2024
```

找到 `IKCFG_ST` 标记后的原始 gzip 内核配置，解压为 159,701 字节，SHA256 为 `8894881d2063f60d81a1932af960d21480bccaba7d95364d745e2faf7457f4c6`。下列判断来自**实际内嵌配置**，不是从 DTB 推测：

| 配置 | 实际值 |
| --- | --- |
| `CONFIG_OF_OVERLAY` / `CONFIG_OF_CONFIGFS` / `CONFIG_CONFIGFS_FS` | 全部 `y` |
| `CONFIG_FPGA` / `CONFIG_FPGA_MGR_ZYNQ_FPGA` / `CONFIG_FPGA_REGION` | 全部 `y` |
| `CONFIG_I2C_CADENCE` / `CONFIG_I2C_CHARDEV` | 全部 `y` |
| `CONFIG_GPIO_ZYNQ` / `CONFIG_GPIO_SYSFS` / `CONFIG_PINCTRL_ZYNQ` | 全部 `y` |
| `CONFIG_CMA` / `CONFIG_DMA_CMA` | 全部 `y` |
| `CONFIG_CMA_SIZE_MBYTES` / `CONFIG_CMA_SIZE_SEL_MBYTES` | `128` / `y` |
| `CONFIG_IKCONFIG` / `CONFIG_IKCONFIG_PROC` | 全部 `y` |
| `CONFIG_INPUT_TOUCHSCREEN` | 未启用；不阻止本项目通过 i2c-dev 轮询 GT911 |
| `CONFIG_VIDEO_OV5640` | 未启用；不阻止本项目通过 i2c-dev 配置 OV5640 |

这证明镜像内核已包含所需 I2C/GPIO 与 DT overlay 基础支持，不能继续把“可能未编译内核驱动”当作既定阻碍。尚未检查 rootfs 中实际安装的 Python、PYNQ、XRT 版本，也未确认运行时 configfs 是否挂载。

## 真实系统 DTB

| 符号 / 路径 | phandle | 属性与结论 |
| --- | --- | --- |
| `i2c0` → `/amba/i2c@e0004000` | `0x18` | Cadence，`status=disabled`，寄存器 `e0004000/1000`；clock 为 clkc 的 38，即 `i2c0_aper`；无 `clock-frequency`、`pinctrl-*`、`resets` 属性 |
| `i2c1` → `/amba/i2c@e0005000` | `0x19` | Cadence，`status=disabled`，寄存器 `e0005000/1000`；clock 为 clkc 的 39，即 `i2c1_aper`；同样无频率、pinctrl、resets 属性 |
| `gpio0` → `/amba/gpio@e000a000` | `0x17` | Zynq GPIO 控制器，无 disabled 状态；clock 为 `gpio_aper`；无 `pinctrl-*` 属性 |
| `pinctrl0` → `/amba/slcr@f8000000/pinctrl@700` | `0x2b` | `xlnx,pinctrl-zynq`，`reg=<0x700 0x200>`，`syscon=<&slcr>`；**没有任何已有子状态** |
| `clkc` → `/amba/slcr@f8000000/clkc@100` | `0x1` | `xlnx,ps7-clkc`，`#clock-cells=1`，PS 输入时钟 33,333,333 Hz |
| `rstc` → `/amba/slcr@f8000000/rstc@200` | `0x2a` | 已有 reset provider；I2C 原节点并未声明 reset ID，候选不猜测添加 |

实际 `__symbols__` 确认上述 `i2c0/i2c1/gpio0/pinctrl0/clkc/rstc` 标签均存在，因此离线编译 overlay 可使用符号引用。不要把这些 phandle 数值写死到源码；它们只用于核查当前基底。

两路 I2C 的实际 disabled 状态直接解释了原镜像为什么不会自动满足 Notebook 的 LinuxI2C 发现条件。内核驱动存在与设备树启用是两个独立条件。

`/aliases` 只有 ethernet0、serial0、spi0，没有 I2C alias；继续按控制器寄存器地址识别总线，不能假设 i2c-N 编号。

`/chosen` 的 `stdout-path=serial0:115200n8`，serial0 对应 UART1 `e0001000`。bootargs 指向 `/dev/mmcblk0p2`、ext4、rootwait，并保留 `clk_ignore_unused`；未给出 `cma=`。`pynq_board` 为字符串 `None`，它不构成 AC820 型号或板上 PYNQ 包版本的验证。

`/memory` 为 `reg=<0 0x40000000>`，即 1 GiB；DTB 无 `/reserved-memory`，FDT memory reservation 表也为空。**内核默认 CMA 128 MiB 仅证明容量，不证明分配基址低于 512 MiB**。当前 VDMA 的地址检查应继续拒绝高地址；实际板上需读取 `/proc/iomem`、dmesg 与分配地址确认。本次不修改 bootargs、不设置 `mem=512M`、不减少可见 DDR。

## 可编译候选与验收方式

`board/linux/leaf_peripherals.dts` 新增候选，专门针对上表 SHA256 的原始 DTB：启用 I2C0（MIO50/51，300 kHz）、I2C1（EMIO，40 kHz），新增 MIO0 的 GPIO 默认 pinmux。已证实目标节点原先没有 pinctrl 状态，所以此基底上的新增不覆盖已有列表；其他基底必须重新检查。

候选只选择 mux，不猜测 IO 电压、内部上拉或 slew 设置。网络、SD、UART、DDR、clock/reset provider 的属性应保持原样。GPIO54 与 I2C1 EMIO 的物理输出仍要求原 PL/HWH 连接正确；DTB 不能创建这些硬件连线，也不能证明外设供电、电平和 pull-up 正确。

**本候选以离线合并后的启动期 DTB 为验收路径。** 虽然内核支持 configfs overlay，给已 probe 的 GPIO 控制器补 `pinctrl-0` 不等于它必然重新选择默认状态。因此不交付自动运行时加载器，不执行 GPIO unbind，也不把 MIO0 作为 I2C consumer 的 pinctrl 状态。

主任务已使用真实 `dtc -@` 编译，并调用官方 libfdt 通过具有二进制读写的 Windows 前端离线合入原始 DTB。`boot_dtb_validation.json` 验证只有10个目标属性变化和4个目标节点新增，其他所有原属性与内存 reservation 均保持。错误 bootargs 改动与截断 DTB 的负向检查均被拒绝。

已生成独立 `board/linux/boot_patch/image.ub`，SHA256 `39b17b17ff7f37becc800319801df628ae779c8490f97d5fea7427d453f05d6c`；新 FIT 仅改变默认 DTB payload 及其 hash，内核逐字节不变、所有 payload hash 正确，所选 DTB 与验证后的合并结果一致。原启动文件未覆盖；SD 替换与恢复步骤见 `board/linux/README.md`。尚未验证实际启动及板上 I2C/GPIO。

## 新 FIT 的后台重封装工具

`build/repack_fit.py` 已提供标准库解析与参数列表方式调用 `dtc` 的实现。输入为原 FIT、替换 DTB、`--dtc` 路径和 `--output-dir` 全新目录；不会调用 shell、运行安装器或接触物理磁盘。输出目录必须全新，且不能位于原 FIT/boot-files 目录内。中间 ITS 与原始 payload 只放 `build/work/fit_repack`，最终输出目录仅有 `image.ub` 和 `manifest.json`。

工具拒绝 signature 节点/签名元数据、外置 payload、不支持的 hash 算法及原 hash 损坏。它保留完整原树，使用 `/incbin/` 保留 kernel 原字节，只替换默认配置所选 fdt 的 data 与原有 payload hash。编译后再次解析，严格核对节点集合、每个属性、内存保留记录、boot CPU、版本以及所有 payload hash。load、entry、timestamp、其他配置和原内核都不得变更。

已经用真实 `build/work/dtc/bin/dtc.exe` 与**原始未修改 system.dtb**完成烟测：`property_changes=[]`，所有原节点/属性完全相同，kernel SHA256 保持 `cbd2d2ade6b3f187a1114f8eb60b7ae92fd0c1feca814856df184fa1c07573d9`，两 payload hash 均通过。新序列化 FIT 的 SHA256 为 `d53773712c9f0c077ac54a9e431b9c67618d6503927a580e51b604b1efd0925d`；结构 padding 可以不同，不把整文件字节相同作为要求。四项负向检查均拒绝签名、外置 data、未知算法与损坏 payload。简明证据位于 `report/fit_repack_smoke.json`。

这次烟测没有启用新 I2C 配置，也不代表已成功启动新 FIT。外设合并 DTB 的编译/重封装验收由主任务继续执行。

## 对应内核的官方驱动依据

[Xilinx xilinx-v2020.2 pinctrl-zynq.c](https://github.com/Xilinx/linux-xlnx/blob/xilinx-v2020.2/drivers/pinctrl/pinctrl-zynq.c) 中，`i2c0_10_pins` 明确是 MIO50/51，`gpio0_0_pins` 是 MIO0；相应 group 与 i2c0/gpio0 function 均注册。驱动使用 generic pinconf 的 DT 映射，支持 mux 子节点及 groups/function。候选不引入其他版本新增的电气属性。

本地实际 kernel 版本与公开 Xilinx release 对齐，但没有取得板商完整源码 commit，因此不能把公开 tag 视为已经证明板商没有任何私有补丁；最终以板上驱动行为与时序验证为准。
