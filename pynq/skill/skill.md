---
name: pynq-runtime-handoff
description: 核对AC820 PYNQ运行包的模型、位流、设备和路径依赖，处理大小写及部署入口变更并保存可复用验收记录。适用于运行包交接和目录整理。
---

# pynq-runtime-handoff

读取本工程README、src/source_catalog.json、report/pynq_review.md。输入为匹配AC820的PYNQ运行包及明确的模型/位流来源；输出为可追溯部署目录、路径映射、验证结果和适用限制。

1. 记录输入SHA、bit/HWH配对、器件/Bank电压、权重格式及六类顺序。只把本包4000阈值作为原始分数策略，不能称作概率或跨模型通用参数。
2. 路径改小写时同步weight_specs、内部_weight键和model_manifest；枚举真实目录字符串检查大小写，不能只在Windows测试open成功。保持原始字节快照用于追溯。
3. 启动入口位于board/lanuch.py；同步入口根目录与一键Notebook导入。先跑sim/run_host_tests.py，再明确报告跳过原因和模拟设备边界。
4. 上板前核对镜像、PS I2C、GT911/pinctrl和CMA；复制文件不等于安装systemd。正常停止旧应用，确认PL/VDMA唯一所有者，再启动新内核/进程。
5. 先用固定输入比较原始六项分数，再检查相机、LCD、真实触摸及保存。Save帧不能默认等于上一Detect帧；记录实际用户声明类别后才能统计识别准确率。
6. DMA超时/清理失败时保持缓冲和锁，确认硬件停止再释放。关机遵循正常停止、sync和Linux关机；目录整理不自动重刷卡或改变网络、启动服务。

验证依据：sim/host_tests.json的53项含2跳过；report/packaging_verification.json记录源恢复和包检查。没有本轮真实板测、当前卡自启动或跨版本位流兼容结论。

失效条件：位流/元数据不配对、权重形状/类别或布局改变、未知电气状态、无黄金固定输入、无法确认DMA停止。遇到这些条件应明确缺口，不能以目录或主机测试代替上板验收。
