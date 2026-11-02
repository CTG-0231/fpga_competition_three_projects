# 2025.2 裸机启动产物

本页记录历史产物；下文“本次”“当前 PYNQ 默认”指当时的迁移包，不指本提交的并列 PYNQ 工程。重新生成时按 [Vivado README](../../README.md) 从对象快照恢复、重建新 XSA，再执行其可选 Vitis 分支，结果输出到该次新会话目录。

这里是 **standalone 裸机** 的 FSBL + 新 PL + 应用启动包，已完成实际编译、链接、离线校验和 Bootgen 打包。**它不是 PYNQ Linux 启动镜像，不用于替换已刷好 PYNQ 的 SD 卡启动文件。** 当时配对的 [历史 overlay](../overlays/3v3_2025_2/manifest.json) 仍保留用于追溯；当前 PYNQ 的运行方式见 [并列工程 README](../../../pynq/README.md)。

本包使用本次全新 Vivado/HLS 2025.2 PL 的 `leaf.xsa`，不是此前“旧 PL + 新 PS”的验证包。`hardware.xsa` 已随包保留，SHA256 为 `2b111cec0c83827a454aad4f890a42f251c392a8ac87c3f58691216f94408892`。`pl.bit` 与同次 XSA 内位流及当前 PYNQ 默认 3.3 V overlay 逐字节相同。

| 文件 | 用途 | 字节 |
|---|---|---:|
| `boot.bin` | Bootgen 生成的 FSBL + PL + 应用启动镜像 | 4503764 |
| `fsbl.elf` | 新平台生成的 ARM FSBL | 302988 |
| `trash_app.elf` | 新平台/BSP 链接的 ARM 应用 | 1165028 |
| `pl.bit` | 配套新 PL 位流 | 4045692 |
| `hardware.xsa` | 同次硬件导出，含位流与 HWH | 1683842 |

`boot.bif`、`bootgen.log`、`trash_app.map`、`verification.json` 和 [manifest.json](manifest.json) 保留打包顺序、链接信息及实际文件 SHA256。裸机应用运行时仍需要其源码约定的 SD 权重/输入数据；构建通过不表示已经完成板上启动或推理。

ARM 应用入口为 `0x00100000`。离线校验已检查堆/栈、视频保留区、SDT 中断 ID、长文件名支持，以及四个 HLS 驱动的寄存器偏移和 32 位宽。实体板测试尚未进行，PL 外部相机/LCD 时序覆盖的限制仍见主迁移报告。

完整构建过程、两次失败记录与最终成功结果见 [Vitis 报告](../../report/vitis_2025_2/README.md)。
