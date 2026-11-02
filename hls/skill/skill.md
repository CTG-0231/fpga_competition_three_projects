---
name: hls-fixed-point-reproduction
description: 从内容寻址 .bin 快照恢复 HLS 原生源码，用 Vitis HLS 2025.2 重建四核 IP 并核对 RTL 结果与交付来源。适用于本项目复现、输入路径诊断和核级验证。
---

# HLS 对象快照复现技能

使用 [工程 README](../README.md) 的连续 PowerShell 步骤；不把本机已有 HLS 工程、`FUXIAN` 或历史导出目录当作默认输入。目录名按比赛约定保留 `README.md` 特例，本技能文件使用小写 `skill.md`。

## 执行顺序

1. 校验 `build/check_project.py`；在整个提交树外选择全新会话目录。恢复目标与构建目标不得事先存在。
2. 用 `build/restore_sources.py --group native_2025_2` 恢复 355 个文件。`.bin` 是对象内容，原名由清单恢复；不手工猜文件名。
3. 构建显式指定 `--source <恢复根>/src/hls`、新的 `--output`、真实 2025.2 `vitis-run`。采用提交树 `build/hls_2025_2.py` 与配套 Tcl，不直接运行恢复快照里的旧目录入口。
4. 保存 17 个输入文件的 SHA256、`tool_version.log`、`compile_source_diff.json`、四核日志和 `summary.json`。只在四核均成功并且新 `component.xml` 存在时判定 IP 生成成功。
5. 用本轮 `work/projects/<core>/solution1/impl/ip` 执行 `validate_hls_rtl.py --extended`，核对 PASS 标记及无 MISMATCH。C 仿真、RTL 验证、综合、联合仿真分别记录，不能互相替代。
6. 若整机需要本轮新 IP，按 [Vivado 新 IP 集成入口](../../vivado/build/vivado_2025_2/readme.md) 继续；若只恢复随包 Vivado 工程，不要求重新生成 HLS。不修改 PYNQ 或 SD 卡。

## 已知失败条件与验证边界

- 不能将输出置于提交树内，或把 `compile_inputs` / `exported_ip` 当作原始源码根。
- 源 SHA 不一致、缺少任一 IP、工具版本不符时停止该流程并记录实际错误，不跳过校验。
- 现有构建器在外部兼容副本处理旧 DATAFLOW、动态偏置复制、PW 1024→1280 容量；原始文件保留。这不等于与旧 RTL 对所有输入数值一致，尤其 1280 通道存在差异。
- 重新选模型、定点位宽、张量打包或接口后，现有测试边界需要重新审核。核级有界验证不能证明完整模型精度或上板成功。
- 历史证据见 [HLS 报告](../report/hls_2025_2/readme.md)；本次 Markdown 修订不是新一次综合记录。保留原失败、超时和测试台限制。
