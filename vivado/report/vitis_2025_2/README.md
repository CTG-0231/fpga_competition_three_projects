# 新 PL 配套 Vitis 2025.2 构建记录

本文为历史构建记录，其中“本次”及 PYNQ 配对描述指当时的迁移包，不指当前并列 PYNQ 工程。新的复现按 [Vivado 工程 README](../../README.md) 从 `.bin` 对象恢复工程并重新生成 XSA，再按其第 7 步构建裸机软件。

最终有效构建来自外部目录 `vitis_migration_final_retry2`。Vitis 2025.2 已真实生成新平台、standalone BSP、FSBL、ARM 应用 ELF 和 Bootgen 启动镜像；四个阶段均以退出码 0 和对应完成标记通过。未进行实体板启动、裸机应用完整推理或数据集精度测试。

本次 CPU 软件使用最终重建的 **新 2025.2 PL XSA**，不沿用旧 2019.2 PL。XSA SHA256 为 `2b111cec0c83827a454aad4f890a42f251c392a8ac87c3f58691216f94408892`；同一文件已保留为 [hardware.xsa](../../board/standalone_2025_2/hardware.xsa)。

## 实际阶段

| 阶段 | 退出码 | 完成判据 | 耗时秒 |
|---|---:|---|---:|
| platform | 0 | BSP/FSBL 真实构建完成，3 份 LFN 配置头和 3 份库分别同 SHA | 85.835 |
| app | 0 | 新平台/BSP 下应用实际编译、链接，ELF 存在 | 17.721 |
| verify | 0 | ARM ELF、内存、SDT 中断、LFN、四核寄存器契约校验通过 | 0.218 |
| package | 0 | Bootgen 2025.2 报告成功，启动镜像存在并记录 SHA | 0.854 |

原始状态和命令日志在 [logs](logs/)，实际应用校验结果见 [verification.json](verification.json)。独立二次核对见 [independent_review.json](independent_review.json)。

## 配对与内存核对

- 原 XSA、平台输入 XSA、随包 `hardware.xsa` 三者 SHA256 相同。
- XSA 内位流、`artifacts/pl.bit`、发布的 `pl.bit` 和 PYNQ 默认 3.3 V `leaf.bit` 逐字节相同，SHA256 为 `b0a00f0051148a356884ab19ae8281fb6308dae3108e2e538f40f3f321bd0557`。
- 本次实际 FSBL、应用 ELF 与打包输入逐字节相同；`boot.bif` 顺序为 FSBL → PL → 应用。
- 两份 ELF 均为 little-endian ELF32 ARM；FSBL 入口为 `0x0`，应用入口为 `0x00100000`。
- 应用内存结束地址 `0x11340550` 低于视频保留起点 `0x12100000`，间隔 14416560 字节；堆为 256 MiB、栈为 2 MiB，见 ELF/linker 校验。
- UART1/IIC0/IIC1/GPIO 的 SDT 中断 ID 分别为 82/57/80/52。四核 HWH 的控制寄存器、数据寄存器偏移和 32 位宽已与实际维护的裸机驱动头逐项核对；仅接受既有的已审定名称别名。

实际裸机产物及完整 SHA256 在 [board/standalone_2025_2](../../board/standalone_2025_2/README.md)。`boot.bin` SHA256 为 `f448da712206f5673616a2f415bc591b7a21f685a03fec014db1516259cd113a`。这些检查证明本次文件配对与离线构建，不证明实体运行。

## 失败尝试与构建入口适配

[attempts.json](attempts.json) 及 [attempts](attempts/) 保留三个不同目录的真实记录，未将首次尝试改写为成功：

1. 首次 `vitis_migration_final` 在 SDK `create_client()` 阶段发生 UTF-8 解码错误。官方脚本子进程退出码虽为 0，缺少完成标记且有 traceback，构建入口正确判为失败；没有 BSP/FSBL/应用产物。
2. `retry1` 的平台/BSP/FSBL 已完成，但随后的应用阶段被 SDK 报 `workspace already in use` 拒绝，未完成应用与 Bootgen。
3. `retry2` 才完成本次四个阶段，发布产物全部取自此目录。

最终构建入口采用进程局部的隐藏子控制台与 `chcp 65001`，规避 SDK 对中文诊断按 UTF-8 解码失败的情况。SDK `dispose()` 后的残留服务只按本阶段日志的新端口、安装路径、`RigelApp` 和 `java.exe` 精确匹配并清理。没有修改全局 Windows 区域设置、安装文件或其他 Java 程序。此处是构建入口对已复现问题的兼容处理，不冒充 AMD 官方补丁。

## 从源复现与源闭包

使用 [Vivado 工程 README](../../README.md) 中同一会话的 `$Output/leaf.xsa` 作为新输入、`$Session/ps` 作为新输出。完整 PowerShell 命令只维护在该页第 7 步，不再以本目录历史 `hardware.xsa` 为默认构建输入。

该入口通过实际 Vitis Python API 从选定 XSA 重建平台和应用，再执行独立校验与 Bootgen；不要求恢复的 CMake 缓存可在其他路径原样使用。Vitis 原生源闭包保留实际配置、BSP/FSBL/APP 源、ELF、导出库、硬件 XSA、可移植入口和记录，省略 object、CMake/IDE/SDK 锁等构建缓存。原生工具要求的大小写文件名在外部恢复目录保留。

**PYNQ 路线不使用本目录的裸机 `boot.bin` 替换 Linux 启动文件。** Linux PYNQ 的板端内存、驱动与启动流程是另一路线。PL 摄像头/LCD 外部时序和摄像头域 CDC 覆盖仍需后续核实，详见 [主迁移报告](../migration_2025_2_original.md)。
