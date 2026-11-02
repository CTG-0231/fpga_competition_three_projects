# AC820 Linux integration

当前状态：已提取实际板商启动文件，编译外设 DT overlay、离线合并并生成新 FIT；尚未连接板卡、未进行启动验证、未改写 SD 卡。

板商镜像为 `AC820_ZYNQ_Pynq_Boot_img-2.7.0.zip`。使用 AC820 专用镜像；PYNQ 框架可用在 AC820 上，但 PYNQ-Z2 的启动镜像、引脚和 bitstream 不能直接套用。

`leaf_peripherals.dtsi` 保留为完整镜像源码工程的参考片段。此次实际产物使用 `leaf_peripherals.dts` → `leaf_peripherals.dtbo` → 离线合并的系统 DTB → `boot_patch/image.ub`。启动时选择新默认 pinctrl，使 MIO0 的 GPIO 配置在驱动 probe 前生效；不使用运行时 configfs 自动加载，也不要把本片段命名为 `leaf.dtbo` 放到 bitstream 旁边。

## 仅用于已核对的板商镜像

先按主 README 把原 AC820 镜像写入明确识别的 SD 卡并校验。重新插卡后，启动分区原有 `BOOT.BIN`、`boot.scr`、`image.ub`；核对其中 **原 `image.ub`**：

```powershell
Get-FileHash -LiteralPath '实际SD启动分区路径\image.ub' -Algorithm SHA256
```

它必须为 `b063e9f858a72875259832842d178b895ddfaae4100d0c2dec12bcf94a36b2d4`。若不同，先停止替换并重新审查该镜像。将原 `image.ub` 备份到电脑，再把本包 `boot_patch/image.ub` 复制到已核对的启动分区并命名为 `image.ub`；复制后的 SHA256 应为 `39b17b17ff7f37becc800319801df628ae779c8490f97d5fea7427d453f05d6c`。安全弹出 SD 卡，再断电插卡启动并保存串口日志。恢复时将备份的原 `image.ub` 复制回来并核对原哈希。

本次没有选择盘符、执行这些 SD 操作或重启板卡。新 FIT 保留原内核、配置选择、load/entry、时间戳及其他原属性，只替换系统 DTB 数据与它的 SHA1；清单为 `boot_patch/manifest.json`。原镜像内核为 Linux 5.4.0-xilinx-v2020.2，所需 I2C/GPIO/pinctrl 驱动已从内嵌 IKCONFIG 确认。离线验证不证明供电、电平、启动成功或外设功能。

## 离线复现

下列命令在 `pynq_port` 根目录执行。Windows 工具来源和二进制读写修复见 `report/tool_dtc.md`；Linux 可使用正常的 `dtc` / `fdtoverlay`，无需这个 Windows 前端。

```bash
python3 build/inspect_boot_image.py /path/to/AC820_ZYNQ_Pynq_Boot_img-2.7.0.zip build/work/board_image
# 用 7-Zip 从 boot_partition.img 提取全部启动文件至 boot_files/
python3 build/inspect_fdt.py build/work/board_image/boot_files/image.ub --export-dtb build/work/board_image/system.dtb
dtc -@ -I dts -O dtb -o board/linux/leaf_peripherals.dtbo board/linux/leaf_peripherals.dts
fdtoverlay -i build/work/board_image/system.dtb -o build/work/board_image/system_leaf.dtb board/linux/leaf_peripherals.dtbo
python3 build/validate_boot_dtb.py build/work/board_image/system.dtb build/work/board_image/system_leaf.dtb
python3 build/repack_fit.py build/work/board_image/boot_files/image.ub build/work/board_image/system_leaf.dtb --dtc /path/to/dtc --output-dir build/work/new_boot_patch
```

Windows 的合并命令使用已验证的 `fdtoverlay_binary.exe` 替代官方包内有文本模式问题的 `fdtoverlay.exe`。复现脚本的输出目录必须全新，避免覆盖已有结果。已执行结果见 `report/boot_dtb_validation.json`：仅10个目标属性变化、4个目标节点新增，所有其他属性和内存 reservation 保持不变；新 FIT 所选 DTB 也与该合并结果逐字节相同。

| 内容 | 板商基础 HWH | 本项目 XSA | 移植处理 |
| --- | --- | --- | --- |
| ENET0 | MIO16..27 启用 | 禁用 | 保留 Linux 原启动平台的网络配置 |
| I2C0 | 禁用 | MIO50..51 | 用 Linux Cadence I2C 驱动与正确 pinctrl |
| I2C1 | 禁用 | EMIO | 用 Linux 驱动，PL 连接至 OV5640 |
| GPIO | EMIO 禁用 | EMIO0 一位 | 核对 HWH 后才使用 PS pin54，触摸 INT 为 MIO0 |
| PL clocks | FCLK0 50MHz | FCLK0 100MHz / FCLK1 32.727272MHz | PYNQ 从本项目 HWH 设置；板上读回验证 |
| HP ports | 基础设计未使用 | HP0..3 | PYNQ 会按 HWH 配置 AXI 宽度，需确认实际内核/PYNQ版本支持 |

不要把裸机 `ps7_init.tcl` 或裸机 FSBL 在正在运行的 Linux 上执行。它们配置的不只是 PL 时钟，还包含 DDR、MIO、复位和网络相关设置。

板上先运行：

```bash
python3 build/doctor.py --output report/board_doctor.json
cat /proc/meminfo | grep Cma
ls -l /dev/i2c-*
cat /sys/class/i2c-adapter/i2c-*/name
```

doctor 是只读盘点；本包已包含完整权重，正常情况下退出码应为 0。退出码 2 表示权重缺失或大小错误，应先检查目录是否复制完整。完整权重内容的 finite/range 校验在 `load_weights` 中执行。

I²C 不能依赖总线枚举序号。驱动按 sysfs 设备树的控制器物理地址辨认 PS I2C0 `e0004000` 和 I2C1 `e0005000`。只有 `/dev/i2c-N` 出现并且正确控制器已启用后才能初始化。不要用 `I2C_SLAVE_FORCE` 绕过已有内核驱动的占用。

触控使用七位地址 `0x5d`，复位期间 INT 拉低以选中该地址。原 C 代码的 INT 高电平与 `0x5d` 组合有冲突；迁移驱动按 Linux Goodix 驱动的地址选择方式修正。板上仍需确认实际模块型号、连线及坐标方向。

本工程 VDMA 的可寻址范围较神经网络窄：视频 MM2S/S2MM 地址必须完整落在 `0..0x1fffffff`，不能仅检查地址是32位。PYNQ CMA 若落在512MB以上，视频驱动应拒绝启动，需要在镜像中配置合适的 CMA 区域。

资料依据：本地板商 `PYNQ_Project.zip` 的 base1.hwh、本工程 XSA；[PYNQ Overlay API](https://pynq.readthedocs.io/en/v2.7.0/pynq_package/pynq.overlay.html)、[Xilinx Zynq pinctrl 源码](https://github.com/Xilinx/linux-xlnx/blob/master/drivers/pinctrl/pinctrl-zynq.c)、[Zynq Linux 设备树](https://github.com/Xilinx/linux-xlnx/blob/master/arch/arm/boot/dts/xilinx/zynq-7000.dtsi)。模板仍需用实际镜像工具链编译及上板核验。
