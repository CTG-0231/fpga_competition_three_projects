---
name: zynq-pl-ps-release
description: 从 .bin 对象快照恢复 Zynq Vivado 2025.2 工程，重新综合实现并导出含本轮位流的 XSA；区分快照 IP 复用、新 HLS 集成和 PYNQ 配对验证。
---

# Vivado 原生工程恢复与 XSA 复现技能

主入口为 [工程 README](../README.md)，含可写出外部 Tcl 文件的 PowerShell 命令。它从快照恢复输入，不要求已有本机构建目录。`skill.md` 文件名按比赛提交的小写规则保留。

## 选择输入路线

- **重建随包 2025.2 工程**：恢复 `native_2025_2`，输入 `<恢复根>/p/leaf.xpr`，四个 HLS IP 已在 `<恢复根>/workspace/ip_repo`。无须先恢复或构建 HLS；新 XSA 必须来自本轮综合/实现。
- **重新集成本轮新 HLS IP**：先按 HLS README 恢复并生成新 IP，再按 [集成说明](../build/vivado_2025_2/readme.md) 恢复 `native_2019_2`，向 `build.py` 传入 `<恢复根>/board` 和本轮 HLS `work/projects`。这个入口读取 `trash.xpr` 布局，不能传入 2025.2 的 `p/leaf.xpr`。

## 执行与交付

1. 校验提交清单；恢复到整个提交树外、尚不存在的目录。按清单还原原生大小写，不更名工具内部文件。
2. 显式启动安装的 Vivado 2025.2。启动前仅为当前子进程设置 `XILINX_LOCAL_USER_DATA=no`，保留日志；不得因此修改 Windows 全局电源、软件或启动配置。
3. 使用 README 的 inspect 模式核对 XPR、器件、BD、四核 IP。检查通过仅证明工程加载，不是综合成功。
4. 只在本轮新恢复的目录重置运行并构建；同一工程不得由另一个 GUI/batch 进程并行使用。综合成功后运行到 `write_bitstream`，检查精确完成状态、100% 和非空新 bit。
5. `open_run impl_1` 后 `write_hw_platform -fixed -include_bit`，输出到本轮新目录。保存资源、时序、DRC、方法学报告以及 XSA/bit SHA256。不得把已有 `board/` 产物当作本轮生成。
6. 需要 overlay 时从同一新 XSA 导出 bit/HWH，并做离线解析检查。需要裸机软件时将同一 XSA 输入 Vitis；记录与 PYNQ Linux 不同的用途。

## 失败及证据边界

源恢复失败、缺 IP、版本不符、运行失败或只有 `route_design Complete!` 时不宣称 XSA 构建完成。保留 `runme.log` 和原失败现场，不删除旧包，也不反复重置仍在运行的工程。

1280 通道 HLS 行为差异和外部时序约束覆盖不足仍适用。新 XSA 生成、HWH 解析、PYNQ 驱动适配、整机板测分别提供证据；不自动覆盖并列 PYNQ 配对或 SD 启动文件。历史资料见 [迁移记录](../report/migration_2025_2_original.md)、[时序审查](../report/vivado_2025_2/timing_review.md)；本次修订不改写历史构建日期或补写板测成绩。
