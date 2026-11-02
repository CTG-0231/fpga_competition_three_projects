# Vivado 工程恢复与 2025.2 升级准备

核对日期：2026-10-23（Asia/Shanghai）。本文件区分附件中已有的历史构建结果、本次已完成的文件准备，以及尚未执行的 2025.2 构建。用户后续补充了 `trash.7z` 与 HLS 工程，并明确原工程已正常上板、保留 HLS、升级工具到 2025.2。本次不修改原始 HLS 算法、打包 RTL 或已有 bitstream。

## 已恢复的构建输入

原工程入口为 `original/trash/trash.xpr`，器件 `xc7z020clg484-2`，工具版本 2019.2，顶层 `design_1_wrapper`。XPR 的工程路径仍指向原机器 `D:/fpga/2019.2/trash/trash.xpr`；IP 库路径为 `$PPRDIR/../orign_refence/trash_mobilenet_v2/hls`，在当前目录中无对应原路径。

XPR 的四项设计/约束输入均已找到：

| 输入 | 本地原始路径 | 处理 |
| --- | --- | --- |
| Block Design | `original/trash/trash.srcs/sources_1/bd/design_1/design_1.bd` | 复制原 JSON；新工程自行生成输出产品 |
| 模块引用 RTL | `original/trash/trash.srcs/sources_1/new/RGB888toRGB565.v` | 字节不变，副本文件名为 `rgb888_to_rgb565.v` |
| 原顶层 wrapper | `original/trash/trash.srcs/sources_1/bd/design_1/hdl/design_1_wrapper.v` | 原文件保留，新工程以 `make_wrapper` 重新生成 |
| 引脚与 I/O 约束 | `original/trash/trash.srcs/constrs_1/new/Trash.xdc` | 字节不变；不臆造传感器时序或修改 I/O 电压 |

BD 中无需要修补的绝对源文件路径，包含四个 `xilinx.com:hls:*:0.0` 核和模块引用 `rgb888torgb565`；其余是 PS7、AXI 互连、VDMA、CDMA、视频接口、VTC、复位等系统 IP。

四个 HLS 打包库可从 `original/hls` 完整恢复：

| IP | component.xml 所在目录 | 文件组引用条目 / 去重后文件数 |
| --- | --- | ---: |
| conv | `conv/solution1/impl/ip` | 134 / 72 |
| fc | `avgpool_fc/solution1/impl/ip` | 74 / 42 |
| pwdwconv | `pwdwconv/pwdwconv/solution1/impl/ip` | 206 / 108 |
| shortcut | `shortcut/solution1/impl/ip` | 34 / 22 |

合计 448 个文件组引用条目，去重后 244 个文件；每一项均已离线确认存在，引用中无绝对路径。准备目录包含 244 个 IP 文件、4 个 component.xml 和 3 个 BD/RTL/XDC 输入，共 **251 个被记录并核对 SHA-256 的文件**，另有生成的配置和清单。未复制历史 `.runs`、DCP、缓存、临时日志作为新综合结果。

原 XDC 所列 I/O 均使用 LVCMOS33。因此这条源码重建路线对应原 3.3 V 设计；已有 1.8 V XSA 可继续独立留存，但不能据此声称这份 XDC 已能重建 1.8 V 版本。

## 与已经恢复的 Overlay 的配对

历史实现 bitstream：`original/trash/trash.runs/impl_1/design_1_wrapper.bit`。

- SHA-256：`22c3d981440b32a197cef94d61f2de6cc62610ae0f7cb7fc633f62e90a744a1e`，与当前 `board/overlays/3v3/leaf.bit` 完全一致。
- 原工程 `hw_handoff/design_1.hwh` 的 SHA-256 为 `443d9dfca798825c6a2ad817e8a0d0dab8bb47f388213a1ae1e53bfbada09ec4`，与当前 3v3 HWH 完全一致。
- 当前 1v8 bitstream SHA-256 为 `65a3258f77962381583c65474dce849b5cf5187f2067476d47d9f96087572659`，与上述 3v3 实现不同，不能混配。

这些哈希建立了“附件中历史 Vivado 实现 -> 3v3 Overlay”的文件配对关系；不代表本次已经在 PYNQ 上实测，也不保证新工具综合会产生相同位流。

## 历史实现报告

报告位于 `original/trash/trash.runs/impl_1/`，工具 Vivado 2019.2，日期 2026-10-18；这些是用户附件中的原有报告，不是本次新运行的结果。

| 资源 | 已用 / 可用 | 比例 |
| --- | ---: | ---: |
| Slice LUTs | 43014 / 53200 | 80.85% |
| Slice Registers | 56250 / 106400 | 52.87% |
| Block RAM Tile | 137 / 140 | 97.86% |
| DSP | 143 / 220 | 65.00% |

来源：`design_1_wrapper_utilization_placed.rpt`。资源接近上限的是 BRAM；2025.2 系统 IP 更新后应重新比较资源和布线，不沿用此表作为新结果。

`design_1_wrapper_timing_summary_routed.rpt` 给出 WNS `+0.207 ns`、TNS `0`、WHS `+0.040 ns`、THS `0`。其中 `clk_fpga_0` 为核心时钟路径，原 HWH 为 100 MHz；另有视频时钟。正 WNS 只覆盖已约束路径，不能将这份报告描述成全部外设时序已覆盖：

- `OV5640_PCLK` 根时钟未定义，143 个寄存器/锁存器时钟引脚无时钟。
- 260 个内部引脚无最大延迟约束。
- 10 个输入端口无输入延迟、20 个输出端口无输出延迟。
- `design_1_wrapper_methodology_drc_routed.rpt` 中有 143 项 `TIMING-17 Critical Warning`，另有 `TIMING-18` 等警告。

标准 `design_1_wrapper_drc_routed.rpt` 摘要记录 66 条违规/提示，包含 DSP 流水、非专用摄像头时钟放置、BRAM 异步控制等类别，并有规则条目数量上限提示。bitgen 日志的最后一次 DRC 显示 0 Errors、61 Warnings、4 Advisories；最终 `write_bitstream completed successfully`，进程于 2026-10-18 17:43:45 退出。不同阶段的计数口径和限制不同，不应合并成“无任何警告”。

这些静态时序覆盖缺口不推翻用户报告的既有功能正常现象；迁移和 2025.2 重建后仍应对摄像头/LCD实际时序重新核验。当前保留原 XDC，通过可选 `--timing-xdc` 接入经实际器件时序确认的补充约束，不猜测 PCLK 周期、输入/输出延迟，也不以大范围 false path 隐藏问题。

## HLS 静态观察与用户约束

原 `pwconv.h` 含 `MAX_LEN=1024`，Tail 主机调度输出通道为 1280；BD 缓存和打包库的 `pwconv_bias_buff_tde.v` 均显示 `MEM_SIZE=64`、`AWIDTH=6`，二者逐字节相同。该静态维度疑点已记录，需结合实际参数、输入和黄金输出理解其影响。

用户明确原工程已上板正常，要求保留 HLS。本次因此不更改该常量、不替换算法、不修改现有 HLS RTL、不以此静态观察阻断原位流使用，也不声称已通过该观察否定真实板上结果。PYNQ 侧继续保持原始量化、布局、寄存器和调用顺序，后续用相同输入/权重做输出比对。

## 本次新增的可复现入口

`build/prepare_vivado.py` 负责依赖检查与准备：

```powershell
python build/prepare_vivado.py --target-version 2025.2 --output build/work/prepared
```

默认读取相邻 `original/trash` 和 `original/hls`。显式参数 `--project-root`、`--ip-root` 可调整源位置；输出必须是新目录并与原始输入不重叠。脚本检查 component.xml 每项引用并生成 `prepare_manifest.json`；输出配置均相对准备目录解析，可移动到另一机器。原始目录不写入。

`build/rebuild_from_project.tcl` 为 **2025.2 新工程升级与构建入口，尚未在该版本执行**：

```powershell
& '<vivado_2025_2_install>/bin/vivado.bat' -mode batch -source build/rebuild_from_project.tcl -tclargs build/work/prepared build/work/vivado_2025_2
```

入口先要求全新的输出目录，并拒绝它与准备目录相互嵌套；随后将准备目录的 `inputs/`、`ip_repo/`、配置和清单复制到**本轮输出目录的 `workspace/`**。只加载该副本中的配置，并检查 BD、RTL、XDC、IP 库等所有路径均落在本轮工作区内。`upgrade_ip`、`save_bd_design`、`generate_target` 产生的修改与输出因此只进入本轮副本，`build/work/prepared` 保持原 SHA-256，可供下一轮独立构建使用。新工程位于本轮输出的 `project/`；不引用历史 runs/DCP 缓存。

入口核对实际版本必须与准备目标一致；禁止误用已发现的 2018.3。它仅对 `xilinx.com:ip:*` 的内建系统单元显式执行升级；四个 `xilinx.com:hls:*:0.0` 保持原身份和打包 RTL。升级前后保存 `ip_before.tsv`、`ip_after.tsv`、`address_before.tsv`、`address_after.tsv`、IP 状态报告和 `system_ip_upgrade.log`，随后验证 BD、生成 wrapper、综合、实现、生成位流和 XSA，并导出资源、完整时序、DRC、方法学和 CDC 报告。未配置自动地址重分配。

该方式依据 AMD [UG835 2025.2 upgrade_ip](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/upgrade_ip) 支持对 BD 单元升级的接口；命令不以 `-quiet` 隐藏升级失败。内建 IP 跨版本可能改变参数或接口，因此保留前后记录并在上板前复核地址、PS 外设、时钟、复位和视频行为。HLS 源码不需重综合；使用已有打包 RTL。

## 工具与验证状态

本次在限定的常见软件目录中定位到 `D:/software/X/Vivado/2018.3/bin/vivado.bat`；原日志的 `D:/xlinx/Vivado/2019.2` 在本机不存在，未找到已安装的 2019.2 或 2025.2。2025.2 安装/下载由主代理继续处理，本文件不提前记录下载或安装成功。

已经完成：原工程与 IP 依赖审计、历史报告读取、bit/HWH 配对、准备脚本执行、251 个副本哈希核对、原 XPR 哈希未变的核验。已经准备 `build/work/prepared` 作为 2025.2 输入；较早的来源审计副本保留于 `prepared_2019_2`。

已追加构建副本隔离的离线验证：用 Python 的 Tcl 解释器运行真实入口，仅模拟 `version` 和 `create_project`，在创建工程边界向本轮 BD 与 IP 的 component.xml 写入测试标记后中止，不调用 Vivado。结果确认配置中的根目录、BD、RTL、XDC、IP 库均指向本轮 `workspace/`；所有 **253 个准备文件**（251 个输入文件加配置与清单）的 SHA-256 前后完全相同。另确认已有输出目录、嵌套于准备目录的输出、错误的 2018.3 版本均被拒绝。测试副本位于 `build/work` 临时子目录，验证后清除。该验证证明复制隔离和路径重定位，不代表 2025.2 的 IP 升级、综合或实现已经执行。

尚未完成：2025.2 实际导入/升级、综合/实现/位流生成、新版本资源与时序结果、PYNQ 板级验证。历史报告和脚本静态检查不能代替这些步骤。准备工作通过只表示输入文件可定位，不表示 Vivado 或 PYNQ 已运行成功。
