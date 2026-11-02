# 板级产物与本轮输出位置

本目录 `overlays/3v3_2025_2/` 和 `standalone_2025_2/` 保存此前构建的产物，不是执行新的恢复命令后自动生成的文件。

按 [Vivado README](../README.md) 从 `.bin` 对象恢复 2025.2 原生工程并重建后，新 XSA 位于该次 `$Session/output/leaf.xsa`；可选导出的 bit/HWH 位于 `$Session/overlay`。这一路线使用恢复目录内的四核 IP，不要求先重建 HLS。若使用本轮重新生成的 HLS IP，按 [集成流程](../build/vivado_2025_2/readme.md) 输出到该次 `$Pl/r/leaf.xsa`。

每次输出关联自己的源清单、工具版本、日志和 SHA256。并列 PYNQ 工程保留自身配对；不要自动用这些产物替换其位流或 SD Linux 启动文件。裸机 `boot.bin` 与 PYNQ 系统镜像用途不同。
