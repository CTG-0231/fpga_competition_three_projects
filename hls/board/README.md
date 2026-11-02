# HLS 与整机的交接

`register_contract.json` 定义四核寄存器和接口。HLS 不作为独立 Linux 应用启动。

按 [HLS README](../README.md) 从对象快照恢复源码并重新生成 IP 后，将本轮 `work/projects` 路径交给 [Vivado 新 IP 集成入口](../../vivado/build/vivado_2025_2/readme.md)。若仅重建随包的 Vivado 原生快照，它已携带对应的历史 2025.2 IP，无需另外运行 HLS。

恢复出的 `exported_ip/` 属于历史快照；不能记为本轮综合结果。不得只换一个 IP 或位流就宣称 PYNQ 配对和驱动已验证。
