# Vitis HLS 2025.2 迁移与验证

本目录记录真正执行的 2025.2 C 综合、Vivado IP 导出、源码保留检查及顶层 RTL 功能验证。不是修改工程中的版本字符串。目标器件为 `xc7z020clg484-2`，时钟约束 5 ns、uncertainty 12.5%，导出 VLNV 保持 `xilinx.com:hls:{conv,fc,pwdwconv,shortcut}:0.0`。

四个核均已完成真实 2025.2 综合与 IP 导出，并通过独立顶层 RTL 的 521382 个原始 Q10 位值检查，包括 PW1280 最后一行偏置和 DW960。所有 12 个 canonical 算法文件及 5 个原测试文件 SHA256 保持原值。实际编译副本有 4 处公开兼容改动，见下文。未进行实体板验证，也未宣称完整网络的端到端 RTL 等价。

## 可复现入口

本报告保留历史实测数据。新一次复现统一执行 [HLS 工程 README](../../README.md)：先校验包并恢复 `native_2025_2` 的 `.bin` 对象，再将 `<恢复根>/src/hls` 显式传给 `--source`，输出到新的外部目录。不要以默认源码目录或已有本机构建代替恢复步骤。

入口先核对 [source_manifest.json](source_manifest.json) 中的 12 个算法文件和 5 个原测试文件 SHA256，再复制输入、生成受控编译副本并调用 `vitis-run --mode hls --tcl`。默认 `build` 执行真实 `csynth_design` 和 `export_design`。每核工程位于 `work/projects/<kernel>/solution1`，IP 位于其 `impl/ip`，IP ZIP 位于 `exported`，命令日志、状态和工具写出的配置位于 `work/runs`。这些是 2025.2 支持的 Tcl 批处理工程；工具提示它们不会自动显示为 Unified IDE 工作区组件。

综合后执行独立功能验证，命令同样见工程 README 第 5 步；四个 `--ip` 都应指向本轮新输出。下面描述验证方法和此前结果，不预先替本轮运行判定通过。

验证器用 Vivado `xvlog`、`xelab -mt off`、`xsim` 编译真实导出 Verilog，通过原寄存器偏移配置指针、写 AP_START、轮询 AP_DONE，并由字节寻址 AXI 存储模型接受全部 DMA 请求。期望结果由独立 Python 整数 Q10 计算得到，采用 AP_RND（最近舍入，平分时向正无穷）及 AP_SAT；逐个比较原始 uint16 位值。实际结果存储区先清零，期望文件单独保存。默认包含 PW96、DW32 等多行用例；`--extended` 再覆盖 PW4→1280 的 62720 个输出和 DW960 的 47040 个输出。

此模型每个端口最多一个未完成 burst，支持 INCR/FIXED、WSTRB、RLAST/WLAST、AXI-Lite 独立握手，并断言本组 DMA 的 ARID/AWID/WID 均为 0。它覆盖有限确定性向量，不是 AXI 协议一致性认证、整个神经网络证明、实现时序检查或上板验证。

## 源码与配置差异

12 个 canonical `.h/.cpp` 的字节、`ap_fixed<16,6,AP_RND,AP_SAT>` 类型和网络数学计算保留不变。原 5 个测试程序也保留原字节。[compile_source_diff.json](compile_source_diff.json) 记录编译派生副本的精确行、原/新 SHA256；归档同时保留 canonical 和实际编译副本，不能把二者混称逐字节相同。

conv 原 `compute_output` 循环中的 DATAFLOW 在 2025.2 默认前端报 `HLS 200-994`（`ch.0` 跨迭代读）。2025.2 `set_directive_dataflow` 没有 `-off` 选项，实测直接使用会失败；`config_dataflow -strict_mode warning -enable_canonicalization=false` 也不能解决。受控副本仅将第 85 行唯一 DATAFLOW pragma 换为说明注释，表达式、类型、循环和接口不变。

随后独立顶层 RTL 测试发现新版静态行 burst 的请求被 padding 条件与首迭代条件共同限制，首列处于 padding 时无读请求而后续有效列等待数据。正式 Tcl 对 conv 三个输入各设置 `set_directive_cache conv inN -lines 1 -depth 1`，用官方缓存机制抑制该静态 burst 推断。该版本已经完成 401408 个输出的原始 Q10 位值比较，768423 cycles，DMA 读 85243 拍、写 100352 拍；它保持原偏移和 32 位地址，不声称调度或吞吐与 2019.2 相同。

PW/DW 的动态二维偏置 `memcpy` 在新 RTL 中遗漏非首行初始化。PW24 首 16 通道有数值，尾 8 通道为 X；层次探针确认 16 个分区只写 row0，row1 未写。相同输入、期望和总线模型下，原 2019.2 RTL 的 PW24 act0/1、DW stride1/2 全部通过；仅禁止新工具自动 inline 不能修复。编译副本将 PW、DW 两处唯一动态偏置复制改为 `0 <= bias_index < M/channel` 的逐元素等价赋值，二维索引使用各文件自己的 Tm（PW16、DW8），不增补虚假偏置，不改变参数和定点运算。全量扫描 7 个 memcpy 中仅此 2 个为运行期动态偏置长度，详见 [memcpy_audit.json](memcpy_audit.json)。

模型实际末层输出为 1280 通道。canonical `pwconv.h` 的 MAX_LEN 为 1024；原 HLS 导出和原交付 prepared IP 中偏置 RAM 都是 64 行×16，并未发现已扩为 80 行的旧 RTL。为覆盖真实模型边界，编译副本将 PW MAX_LEN 改为 1280，保持 canonical 原文件，实际新 RAM 可覆盖 row79。该存储边界修复不改变网络、参数、数据类型或量化。它不否定原有板上运行观察，但不能据原工程能运行就推断此前 1280 边界已验证。

四处编译副本差异为 conv.cpp 一处 pragma、pwconv.cpp/dwconv.cpp 两处等价复制、pwconv.h 一处容量。新源码均由构建脚本从已校验 canonical 字节生成，逐项记录原/新 SHA256；未修改生成 IP-XACT。`--conv-dataflow keep` 和 `--bias-copy original` 仅用于诊断复现旧失败，正式构建使用默认兼容配置。

其他显式迁移设置见 [hls_2025_2.tcl](../../build/hls_2025_2.tcl)：m_axi 地址 32 位、AXI-Lite 数据 32 位、禁止自动端口加宽、固定原 CTRL bundle/offset、关闭新增默认自动循环流水线、显式中断状态寄存器 TOW。脚本不修改工具生成 IP-XACT。

## 接口检查范围

[register_contract.json](register_contract.json) 对照原导出 IP：所有控制/参数寄存器的地址集合、32 位宽、已核实名字别名、单一 CTRL bank、VLNV，以及 IP-XACT 中全部 RTL 端口名称/方向/宽度。名字别名仅用于已确认的原 `_V` 名称与新工具名称之间的映射；不放宽数值偏移和宽度。

CTRL 的 AP_READY 捕获/读清行为与新增 bit 9 interrupt 字段是已记录的工具变化。现有 PYNQ runner 只写 bit 0，读取 bit 1/2 判断完成/空闲，不使用 bit 3/9；原裸机推理也轮询 IsDone。不能因此声称整个 CTRL 位图完全相同。IRQ 状态保持显式 TOW 配置。

新 IP 的 `C_M_AXI_*_ENABLE_ID_PORTS` 默认从 false 变为 true。虽然 IP-XACT 宣告的完整 RTL 端口表可相同，Vivado BD 实际可见 ID pin 会改变；这不是单纯名称差异，必须由 Vivado 集成检查另行处理。不能用本报告的端口表检查代替 BD/XCI 实例连接审核。相同 `0.0` VLNV 的旧/新仓库也不能在同一工程中混载，应使用新的冻结仓库和输出目录。

## 实测结果与边界

[rtl_functional_results.json](rtl_functional_results.json) 和 [logs](logs/) 保存真实工具日志及每个用例的输入/期望 SHA256：

| 核 | 原始 Q10 位值检查数 | DMA 读拍 | DMA 写拍 | fixture 累计 cycles |
|---|---:|---:|---:|---:|
| shortcut | 16 | 8 | 4 | 73 |
| fc | 6 | 35203 | 3 | 191302 |
| conv | 401408 | 85243 | 100352 | 768423 |
| pwdwconv（8 用例） | 119952 | 34944 | 29988 | 107841 |

cycles 包含该 fixture 的复位、寄存器操作和本总线模型等待，不是实体 DDR 吞吐测量。PW/DW 用例包括 PW24 act0/1、DW stride1/2、PW16→96、PW4→1280、DW32、DW960，原始整数逐值相等。独立 C99 整数参考还交叉核对了本验证器的全部 11 个用例；完整网络 host 黄金结果另见 `native_2025_2` 恢复后目录内的 `report/q10_reference_2025_2.json`，不将 host 数学结果冒充完整网络 RTL 或实体板结果。

[csim_original.json](csim_original.json) 独立统计原测试输出：shortcut 10000 值均为 4；conv 401408 对、PW 18816 对均无不等，原代码会在不等时返回非零；FC 原程序只有打印，独立比较六对相同。conv 原伪随机生成式存在有符号整数溢出的可移植性限制，FC 打印精度也弱于原始位值比较，因此新增整数 RTL 验证单独承担更强的检查。

原官方 HLS C/RTL cosim 的状态单独保留：shortcut 通过；FC 和 conv 在本机 Xsim AXI VIP 内部发生 fatal，PW 在 C TB 包装阶段发生 SIGSEGV；修正测试接口 depth 后 FC/PW 仍失败。不能把这些记录写成四核 HLS cosim 通过，也不应仅凭工具 fatal 判断算法错。

本机 Xsim 在 `$fatal` 后可能仍返回 0。验证器必须同时看到最终 `RTL_FUNCTIONAL_PASS`、没有 `MISMATCH`/`Fatal:` 才通过。只翻转 shortcut 一个期望位的独立负例已真实出现 Q10 mismatch，`--check-log` 实际退出 1；原通过目录未修改。

[qor.json](qor.json) 保留旧/新 HLS 综合资源、估计时钟和 latency：

| 核 | BRAM18K 旧→新 | DSP 旧→新 | FF 旧→新 | LUT 旧→新 | 估计 ns 旧→新 |
|---|---:|---:|---:|---:|---:|
| shortcut | 54→36 | 0→0 | 2402→2885 | 3163→3679 | 4.375→4.443 |
| fc | 14→18 | 3→3 | 6323→5658 | 8779→9582 | 4.375→4.834 |
| conv | 44→34 | 28→28 | 14014→11127 | 13957→12431 | 4.539→5.311 |
| pwdwconv | 110→120 | 112→97 | 41625→37914 | 38966→34449 | 7.146→5.152 |

HLS 估计不是布局布线后的时序结论，部分估计超过本次 5 ns 目标。旧报告目标封装是 clg400，新构建按实际板卡用 clg484；工具版本、调度及配置同时变化，资源差异不能全部归因于单一 pragma。conv 旧 latency 未定义，无法给出可信吞吐比；FC 报告由 65650 增为 191146 cycles，应作为性能变化留档。完整系统资源、时序及实体板结果由集成报告单独记录。

[portable_rebuild_verification.json](portable_rebuild_verification.json) 记录从正式、可搬移的 Python/Tcl 入口使用全新外部目录重建后的 Verilog 逐文件 SHA256 对照；不能只把本机绝对路径的临时 Tcl 当作复现入口。工具生成的 `*_actual_config.cfg` 保留本次实际路径作为来源记录，换机器重建由 wrapper 重新生成路径。

## 官方依据

- [UG1399 2025.2：vitis 与 vitis-run](https://docs.amd.com/r/2025.2-English/ug1399-vitis-hls/vitis-v-and-vitis-run-Commands)
- [UG1399 2025.2：export_design](https://docs.amd.com/r/2025.2-English/ug1399-vitis-hls/export_design)
- [UG1399 2025.2：set_directive_dataflow](https://docs.amd.com/r/2025.2-English/ug1399-vitis-hls/set_directive_dataflow)
- [UG1399 2025.2：config_interface](https://docs.amd.com/r/2025.2-English/ug1399-vitis-hls/config_interface)
- [UG1399 2025.2：set_directive_cache](https://docs.amd.com/r/2025.2-English/ug1399-vitis-hls/set_directive_cache)
- [UG1448：缓存端口不采用静态 burst 推断](https://docs.amd.com/r/2025.2-English/ug1448-hls-guidance/Burst-Inference)

工具调用仅对当前子进程移除外部 PYTHONHOME/PYTHONPATH，并设置 `XILINX_LOCAL_USER_DATA=no` 作为本机经验措施，不修改系统环境，也不宣称这是 AMD 官方修复或许可证措施。
