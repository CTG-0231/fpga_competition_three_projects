# AC820 RiceVision：三个并列工程

依据赛题3.3.5.4及用户指定的组织方式，本包将 `pynq/`、`hls/`、`vivado/` 作为三个同级工程。PYNQ使用新提供的 `pynq (1)(2).tar` 替换原RAR中的PYNQ；HLS、Vivado及其PS软件来自 `FPGA_COMPETION(1).rar`，并保留此前2025.2迁移产物。原输入压缩包均未覆盖。

```text
fpga_competition/
├── README.md
├── pynq/
│   ├── README.md
│   ├── src/
│   ├── sim/
│   ├── build/
│   ├── board/
│   ├── data/
│   ├── skill/
│   │   ├── README.md
│   │   └── skill.md
│   └── report/
├── hls/       # 同样包含上述七个目录、README与技能说明
└── vivado/    # 同样包含上述七个目录；Vitis作为PS软件归入此工程
```

按题目示例保留 `README.md`，其他提交文件和目录使用小写英文、数字、下划线或连字符，保留文件扩展名的点号。中文只用于文件内容。各工程根README给出目录对照、构建与运行步骤。

| 工程 | 内容与入口 |
| --- | --- |
| [pynq](pynq/README.md) | 新TAR的Python程序、106权重、相机/LCD/触摸数据、配对bit/HWH；从 `board/lanuch.py` 或一键Notebook运行 |
| [hls](hls/README.md) | 四个定点计算核、测试台、原生工程快照、2025.2重建与RTL验证入口 |
| [vivado](vivado/README.md) | 整机RTL/BD/XDC、原生工程、2025.2构建及PS/Vitis软件；Vitis不另设第四个工程 |

## 改动与保留

PYNQ权重文件名统一小写，同时修改文件键查询；启动入口归入board并同步一键Notebook。数值预处理、106权重字节、计算调度、六类顺序、阈值4000、LCD绘制和bit/HWH未改变。PYNQ可以直接从本工程目录运行，不需要恢复旧目录。详见 [改动表](pynq/report/reorganization_changes.md) 和 [检查结论](pynq/report/pynq_review.md)。

工具原生工程有大小写敏感的生成文件与引用。为完整保留原始工程，采用小写SHA256对象归档，原路径作为manifest中的数据保存；`build/restore_sources.py` 可将其原样恢复到提交树外的全新工作目录。生成的原生工作目录不是比赛提交树，不通过盲目修改工具内部名称来冒充可用工程。各快照包含哪些文件见各自 `src/source_catalog.json`。PYNQ原TAR的519文件也有完整快照，便于追溯差异。

此前2025.2的PL产物保存在Vivado工程内，未覆盖新TAR的PYNQ配对。原TAR为旧版bit/HWH和驱动接口，不能混合两套文件并声称已验证。历史构建/板测记录保持其日期和版本，本次仅做本地整理与检查，未访问开发板或重新综合。

## 验证与交接

从每个工程根目录执行 `python -B build/check_project.py`，核对路径、逐文件SHA256及快照。根目录及三个工程的 `release_checksums.json` 为交付清单；运行后新增采样/报告会改变清单，因此首次运行前校验。

PYNQ主机回归53项：51项通过、2项缺外部旧源而跳过、0失败。真实权重读取及63次核调用调度使用模拟设备检查，不代表PL数值计算或新板识别准确率。每个工程的 `report/packaging_verification.json` 记录本轮范围。设计报告、真实对话导出和最终参赛材料由队伍依据赛题其他条款确认；本轮不将历史记录伪写成新的实测结果。

## 从对象快照复现 HLS / Vivado 2025.2

按照 [HLS README](hls/README.md) 将 `.bin` 内容对象恢复为原生源码，再显式用恢复目录构建四核；按照 [Vivado README](vivado/README.md) 恢复原生工程，再重新综合、实现并生成含本轮 bit 的 XSA。所有输入来自本提交包，所有新输出在提交树外，不依赖 `FUXIAN` 或原机器已有的工作目录。

Vivado 2025.2 快照自带四个对应 HLS IP，单独重建它不要求先重建 HLS。需要接入本轮新生成的 HLS IP 时，采用 [新 IP 集成入口](vivado/build/vivado_2025_2/readme.md)。2026-10-31 本次说明修订只更新 Markdown 和相应校验清单，未修改算法、RTL、对象快照或 PYNQ。历史报告保持原范围，不把本次文档检查算作新的完整构建或板测。
