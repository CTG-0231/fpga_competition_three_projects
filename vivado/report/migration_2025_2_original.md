# 2025.2迁移与本轮验证结果

2026-10-30完成3.3 V分支的四个HLS核、Vivado整机实现，以及同一新XSA对应的Vitis平台、BSP、FSBL、应用和Bootgen产物。默认 `board/overlays/3v3/` 已使用新bit/HWH。**本轮未连接实物板卡，不能称上板验证完成。** 两个输入压缩包保持不变，另出新包。

## 完成情况

| 项目 | 实际结果 | 证据与边界 |
| --- | --- | --- |
| 权重查找 | 修复小写名称KeyError；106份权重与六类顺序不变 | [改动说明](release_changes.md)，真实参数完整63次模拟调度回归 |
| HLS 2025.2 | 四核实际综合、导出完成 | [HLS报告](hls_2025_2/readme.md)，最终101个Verilog与数值验证版本逐字节一致 |
| RTL逐核数值 | 11个用例、521382个Q10值逐项一致，含PW1280和DW960 | [结果](hls_2025_2/rtl_functional_results.json)；有界单突发AXI模型，不等于全网RTL或完整AXI协议证明 |
| 完整定点软件参考 | 实际106份权重完成63次调用 | [报告](q10_reference_2025_2.json)；分数 `[-15876, 8046, -4286, -3750, 1904, -8651]`，最大值索引1 |
| Vivado 2025.2 | 新四核首轮完整综合、实现、bit/XSA导出成功，exit 0 | [产物](vivado_2025_2/final_summary.json)，[时序范围](vivado_2025_2/timing_review.md) |
| Vitis 2025.2 | 新XSA平台、BSP、FSBL、ARM GCC13.3应用、Bootgen均完成 | [证据目录](vitis_2025_2/)，[裸机说明](../board/standalone_2025_2/README.md)；不是PYNQ启动镜像 |
| PYNQ 2.7 | 原样官方解析器读取最终HWH通过 | [解析报告](pynq27_hwh_2025_2_final.json)，[文件契约](final_application_contract.json)；未分配设备内存、未下载PL |
| 主机回归 | 主机63项、启动器8项，均通过，无跳过 | [主机](host_tests.json)、[启动器](launcher_tests.json) |
| 原生工程 | 历史组和三个2025.2组保存原路径/字节，可精确恢复 | [索引](../src/source_catalog.json)；小写对象归档，恢复到提交树外 |
| 实际上板 | 未执行 | 按[运行手册](../docs/run_guide_cn.md)验证固定输入、相机/LCD、触摸及完整应用 |

## HLS兼容与数值影响

原12个算法源和5个原测试源SHA不变。2025.2编译副本只有4个文件存在受控差异：移除一处不兼容DATAFLOW；PW/DW偏置二维动态memcpy改为相同元素的标量复制；PW偏置容量1024扩为1280。另以Tcl配置卷积访问cache，避免已复现的自动突发死锁。精确差异见HLS报告。接口保持原32位、原偏移和单CTRL，软件仅接受核实过的寄存器别名。

原源码及旧打包RTL的PW偏置RAM均为64×16，不能完整覆盖末层1280通道。扩容可能改变旧分数甚至类别，不能承诺所有输入与历史实现完全相同。训练权重、类别与定点运算规则未改。新黄金文件为完整软件参考，不是新版上板数值证明。

官方原测试的RTL协同仿真并非全部通过：shortcut通过，其他尝试包含VIP/包装器失败及实际候选缺陷，失败记录保留。最终独立顶层RTL测试核对真实输出；故意翻转参考值的负例被拒绝，避免xsim遇Fatal仍返回0而被误判。未覆盖随机AXI回压、全输入空间或整网RTL执行。

## Vivado时序和资源

实际FCLK0为100 MHz，HLS目标5 ns不代表整机200 MHz。已约束路径WNS +0.530 ns、WHS +0.022 ns，TNS/THS均0。资源LUT38428/53200、FF48559/106400、BRAM111.5/140、DSP134/220；Slice13018/13300（97.88%），扩展余量小。

原约束仍有缺口：摄像头域228个无时钟寄存器引脚、364个未约束内部端点、10个输入缺input delay、20个LCD输出缺output delay。DRC为35 Warning和4 Advisory，无Error/Critical；另一个methodology检查有228条TIMING-17 Critical和33 Warning，不能混称全设计无Critical。已定义时钟的79个CDC端点为Safe，摄像头域覆盖不完整；4组摄像头bus skew为NA。

保留原针脚、电压和 `CLOCK_DEDICATED_ROUTE FALSE`，未猜造外设约束。仍需依据真实工作模式/器件参数补充外部时序、检查摄像头CDC并上板。**1.8 V目录仅保留历史2019.2配对，未迁移该分支。**

## Vitis构建与使用边界

最终四阶段连续执行均exit 0：平台85.835秒、应用17.721秒、校验0.218秒、Bootgen0.854秒。长文件名支持的3份头文件和3份库一致；ARM入口0x100000，应用结束0x11340550低于视频预留0x12100000；UART/I²C/GPIO中断及HLS MMIO契约匹配新XSA。

最终成功前保留了启动/阶段切换失败：Windows Vitis版本查询正常显示2025.2却返回1；隐藏子进程中文消息被SDK按UTF-8解码失败；平台成功后残留Java服务导致工作区锁冲突。发布入口现校验实际版本banner、仅为局部隐藏console设置UTF-8，并按本次日志确认的专属端口清理自建服务。未更改Windows全局区域、工具安装文件或用户其他应用。

`board/standalone_2025_2/boot.bin`用于独立裸机启动，**不要替换进PYNQ Linux SD卡**。本次PYNQ路线是在板商2.7系统中加载新Overlay，不要求用该裸机boot重新编译PYNQ镜像。

## 关键产物SHA256

| 产物 | SHA256 |
| --- | --- |
| 新XSA | `2b111cec0c83827a454aad4f890a42f251c392a8ac87c3f58691216f94408892` |
| 默认3v3 bit | `b0a00f0051148a356884ab19ae8281fb6308dae3108e2e538f40f3f321bd0557` |
| 默认3v3 HWH | `c93a96ce131be3f1b873c8df19ec7c9c8a05a36826dce9ff799724cb7dcc454a` |
| 新裸机ELF | `3b30f5642c4a7acc0613609394528df424675068e6bc8ee46cfee89e6091bd5d` |
| 新裸机boot.bin | `f448da712206f5673616a2f415bc591b7a21f685a03fec014db1516259cd113a` |
| 新黄金分数 | `8235cd5c02873620ec71b2cc066a5044abb657596aab07e67215275fa3afacc1` |

新板测另存JSON，不覆盖历史board_run.json等。准确率、功耗、CPU加速比、实际FPS、整网硬件数值和新版UI交互，均仍需新的物理板测。
