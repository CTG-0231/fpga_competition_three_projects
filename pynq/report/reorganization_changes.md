# 本次改动及功能影响

| 部位 | 改动 | 功能影响与依据 |
| --- | --- | --- |
| 顶层 | pynq、hls、vivado三个同级工程，各有七目录与README | 组织方式变化；Vitis完整纳入Vivado的PS部分 |
| PYNQ来源 | 替换为新TAR内容；原RAR的pynq_port不作为运行来源 | 保留新TAR自身功能和阈值，非上一版softmax实现 |
| 文件命名 | README.md例外，其余使用小写英文路径 | 同步权重、Notebook和启动入口路径引用 |
| 106权重 | 文件名小写、model_manifest中的name同步 | 所有权重字节/SHA不变 |
| model.py | weight_specs输出及_weight查询统一小写 | 只有文件键变化；真实权重全63次调用回归通过 |
| 启动入口 | lanuch.py移到board，根目录判断改为上一层 | 命令变为python3 board/lanuch.py，一键Notebook已同步 |
| sim | 原测试归入sim；更新文件名断言，增加实际资产回归和运行入口 | 53项中51通过、2跳过；不表示新板测 |
| HLS | 原算法源/测试台与完整原生快照，2025.2入口默认源目录修正 | 原算法字节未改，本次未重新综合 |
| Vivado/Vitis | 完整原生快照、现有2025.2重建脚本/产物/报告 | 本次未改RTL、PS算法或用新bit替换PYNQ配对 |
| Vitis源码命名 | 15个C/头文件仅同步include大小写及权重路径字符串 | 已与原RAR的50个应用源文件对照；保留原换行，未改变C标识符或控制流程 |
| Vivado工具依赖 | 将原元数据辅助模块归入build/overlay_contract.py，3处导入/文件路径同步 | 辅助模块和PYNQ 2.7解析器保持原字节，不与当前PYNQ运行模块混用 |
| skill | 三工程各补skill/README.md和skill/skill.md | 记录操作流程、验证证据和失效条件 |
| 报告/校验 | 新增输入映射、恢复检查、路径检查及交付SHA清单 | 便于追溯与确认传输完整；历史报告保留原版本边界 |

完整原TAR519份文件保存在src/runtime_snapshot.zip；原RAR的HLS、Vivado、Vitis全部文件保存在对应原生快照。恢复脚本在提交树外保留原生大小写以保证工具引用，不将生成工作区算作提交命名合规的目录。原输入RAR/TAR保持原哈希。
