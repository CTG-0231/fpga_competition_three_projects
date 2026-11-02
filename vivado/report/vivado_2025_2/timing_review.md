# 实现与时序范围

本次真实四核 2025.2 HLS 工程于 2026-10-30 22:36:02 首轮完整构建成功，退出码 0，已生成匹配的 bit/XSA/HWH。WNS +0.530 ns、WHS +0.022 ns，TNS/THS 均 0，已约束的建立/保持路径没有失败。WPWS +3.870 ns，TPWS 0。

这不代表全部接口时序闭合。`check_timing` 实报：228 个无时钟寄存器引脚由 OV5640_PCLK 驱动，364 个内部端点未约束，10 个摄像头输入无 input delay，20 个 LCD 输出无 output delay。原 XDC 未添加这些外部时序约束，且保留第 86 行 `CLOCK_DEDICATED_ROUTE FALSE`；实现日志有对应非专用 IO→BUFG 走线警告。需要根据真实摄像头/LCD 配置、器件资料和板上测量补充约束与验证；本轮没有猜造参数。

DRC 为 39 项：35 Warning、4 Advisory，0 Error、0 Critical Warning。Methodology 为另一组检查：261 项，包含 228 条 TIMING-17 Critical Warning 和 33 Warning；不能把 DRC 无 Critical 误写为整个设计没有 Critical。

CDC 报告只分析两个已定义的 FPGA 时钟，79 个端点均为 Safe，Unsafe/Unknown 为 0；未建钟摄像头域不在此完整证明范围。Bus skew 共 8 组：LCD 4 组 slack 为 9.101/9.132/9.349/9.168 ns；摄像头 4 组为 NA，不能称全部 skew 通过。

最终资源：LUT 38428/53200、FF 48559/106400、BRAM 111.5/140、DSP 134/220。Slice 使用 13018/13300（97.88%，剩 282），扩展和布局余量仍小。实际实现已成功，不能由高使用率直接断言无法运行。

原始报告随目录保存，精确数值及 SHA 见 `timing_review.json`，实际产物 SHA 见 `final_summary.json`。本轮没有物理板测、写卡或完成 FPGA 上整网推理验证。
