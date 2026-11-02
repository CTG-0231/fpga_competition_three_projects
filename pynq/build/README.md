# 构建与诊断

`check_project.py` 只读校验交付路径、SHA和快照；`doctor.py` 核对配对元数据和权重尺寸，不下载PL。`make_notebook.py` 是原TAR标准Notebook生成器，仅在有意更新标准Notebook时执行，不用于覆盖优化Notebook。

`restore_sources.py` 依据src/source_catalog.json恢复原TAR或prepared历史输入到全新外部目录；不是当前运行树启动的必要步骤。旧包中的其他历史构建工具完整保存在runtime_snapshot，可恢复查阅。硬件2025.2重建由并列hls、vivado工程的build入口负责。
