# AC820 RiceVision · PYNQ migration

把原 Vitis 裸机应用移到 AC820 的 PYNQ/Python/Jupyter，保留原有 HLS、IP、权重、类别顺序及 bitstream。LCD 界面重新布局为 800×480 的预览、结果卡、状态栏和三个触摸按钮。

**当前是待上板验收的移植工程，不是已完成板测的成品。** 用户确认原工程可正常使用，HLS 源码保持逐字节原样。四个压缩包均已解压审计；106 个真实模型文件已接入。主机测试结果见 `report/host_tests.json`。

本次核对日期为 **2026-10-23**。用户要求构建环境升级至 **2025.2**；当前本机只有 Vivado 2018.3，安装器已从 E:/Download 找到、通过数字签名验证并解包到 D:/software，后台批处理目前缺少管理员权限。安装器按用户要求下载至 `D:/software`，目标安装目录为 `D:/software/AMDDesignTools`。构建脚本已准备 2025.2 入口，但尚未运行该版本综合/实现。

**当前先验证原始位流，2025.2 安装不作为前置条件。** 原2019.2导出的配套 bit/HWH 已包含在本包，PYNQ运行它们无需在电脑上先安装新版Vivado。工具升级用于后续源码重建、约束/IP调整和新版报告；本机2018.3不能据此被视为已经重建过2019.2工程。

## 先看这些文件

| 内容 | 文件 |
| --- | --- |
| 等待画面 / 识别画面设计预览 | `report/lcd_ui_preview.png` / `report/lcd_ui_preview_identified.png` |
| 分步联调与完整应用 | `board/01_bringup_and_demo.ipynb` |
| 比赛要求及评分 | `report/contest_requirements.md` |
| 板卡、镜像、I²C、视频接口 | `report/BOARD_AUDIT.md`、`board/linux/README.md` |
| 实际镜像内核/DTB核查与新启动文件 | `report/board_image_audit.md`、`board/linux/boot_patch/manifest.json` |
| 原模型/接口/数据格式 | `report/application_audit.md` |
| Vivado 依赖、历史实现报告与升级入口 | `report/hardware_audit.md` |
| 原始 HLS 副本完整性 | `report/hls_source_integrity.json` |
| 真实权重与训练预处理证据 | `data/model_manifest.json` |

## 实际模型

原项目名是 `Trash`，当前实际任务为**水稻叶病六分类**。固定顺序：healthy、bacterial_leaf_blight、brown_spot、leaf_blast、leaf_scald、narrow_brown，与 `runs/rice/classes.json` 一致。没有替换类别、重新训练或虚构分类准确率。

- 原始摄像头：224×224，内存字节 BGR888。
- FPGA 输入：RGB、CHW、int16 Q10；`((pixel*2048-255*1024)/255)` 按 C 向零截断。
- 保持原摄像头代码的绿色补偿 `G*200/256`。训练集归一化为 RGB [-1,1]，该补偿是相机专用设置；离线训练样例使用 `preprocess_bgr(frame,256,256)` 关闭它。
- 磁盘权重：106 个 little-endian float32 文件，加载时乘1024后向零截断为 int16，**不能直接按 int16 读取原 bin**。名称和布局不重排。
- HLS 调度：1 conv、34 PW、17 DW、10 shortcut、1 FC，共63次；中间张量保持原硬件打包布局，Python 只传递缓冲。
- 输出：6个原始 int16 分数。界面显示 argmax，不把分数伪装为置信概率。

## SD 卡启动

板卡：AC820，FPGA `xc7z020clg484-2`，DDR 1GB。PYNQ 是运行框架，不代表改用 PYNQ-Z2 的引脚或镜像。

1. 板商资料中的镜像压缩包为：

   `E:/work/FPGA/小梅哥AC820型ZYNQ或安路FPSoC开发板资料/13_附赠应用/Pynq/编译生成的镜像/AC820_ZYNQ_Pynq_Boot_img-2.7.0.zip`

2. 包内是 `ACZ820_ZYNQ-2.7.0.img`，原始大小 **8,070,719,488 bytes**。解压后用原始磁盘镜像写入工具写到足够容量的 SD 卡（建议16GB或以上），并使用工具的写后校验。写镜像会覆盖选中的卡，必须依据实际磁盘型号和容量选对设备；本次没有替你选择或写入任何磁盘。
3. 按 AC820 实物/板商启动说明切到 SD 启动，断电插卡后上电；连接调试串口和网线。
4. 从串口或路由器 DHCP 租约确认实际 IP。没有找到 AC820 镜像专用的账号/IP证据，因此这里不套用 PYNQ-Z2 的默认地址或密码。
5. 浏览器进入板上 Jupyter，把整个 `pynq_port` 目录复制到板上，如 `/home/xilinx/jupyter_notebooks/pynq_port`；实际用户名按镜像配置调整。

**必须处理 Linux 外设配置差异。** 已从实际镜像核查内核驱动齐备，但 PS I²C0/1 在启动 DTB 中禁用。`board/linux/boot_patch/image.ub` 是针对这份板商镜像生成的新启动文件，已离线验证 DTB 只改变目标外设配置、内核字节不变，尚未上板。写好原镜像后，先按 `board/linux/README.md` 核对原 `image.ub` 哈希、备份并替换这个文件，再启动。不要将它用于其他镜像或把裸机 FSBL 覆盖到 Linux 镜像。CMA 实际物理地址仍需板上确认。

## 板上运行

运行推荐走源码路径，避免为了本地包安装额外下载构建工具：

```bash
cd /home/xilinx/jupyter_notebooks/pynq_port
export PYTHONPATH="$PWD/src"
python3 build/doctor.py --output report/board_doctor.json
```

然后打开 `board/01_bringup_and_demo.ipynb`。Notebook 的 `IO_VOLTAGE` 需要依据实际 I/O bank 设置为 `'3.3'` 或 `'1.8'`。两组 `.bit/.hwh` 都来自各自同一个 XSA，文件名统一为 `leaf.bit` 和 `leaf.hwh`，SHA256 在相邻 manifest 中。原实际 Vitis bit 与 `3v3/leaf.bit` 的哈希相同。

该应用保留摄像头、自动对焦、补光、LCD、触摸、识别和单次保存帧功能。浏览器按钮与 LCD 触摸使用同一操作。Save 保存原始 BGR、对应 Q10 和元信息，供重复验证。Stop 后执行清理单元。

如果只验证固定输入和输出：

```bash
python3 board/infer_file.py --board ac820 --variant 3v3 --io-voltage 3.3 \
  --input data/samples/original_infer_q10.bin --input-format q10-bin \
  --weights data/trash_weight --repeat 10 --output report/board_run.json
```

实物若非3.3V需换对应参数。可追加 `--golden path/to/original_six_logits.bin`，要求是原 Vitis 对**完全同一输入**产生的6个 int16 分数，共12 bytes；默认逐值精确比对。脚本记录中位数/P95、每次输出、核调用耗时和权重哈希，统计范围不含摄像头/预处理/LCD，不会虚构 CPU 加速比或完整数据集准确率。

`data/samples` 中的历史 Out/Infer 仅用于调试，二者经检查并非可确认为同一帧的预处理黄金对，不能据此直接声称端到端一致。详见其 manifest。

## Vivado 2025.2

按用户要求，**升级工具环境和必要的系统 IP，不改变 HLS 算法/RTL**。官方 ML Standard 支持 XC7Z020，2025.2 Standard 无需 FLEX license；使用 AMD 官方渠道。安装器已经验签解包，但后台命令行缺少管理员权限，尚未安装；不能把脚本已准备写成安装已完成。

```powershell
python build/prepare_vivado.py --help
```

恢复脚本从 `../original/trash` 和 `../original/hls` 取原始输入，生成独立构建副本，保留原工程。准备结果、实际命令和2025.2升级路径以 `report/hardware_audit.md` 为准。新构建导出 XSA 后可运行：

```bash
python3 build/export_overlay.py path/to/leaf.xsa board/overlays/rebuilt --io-voltage 3.3
```

使用新位流验收时，在 Notebook 设置 `OVERLAY_DIR='board/overlays/rebuilt'`，或给固定输入脚本添加 `--overlay-dir board/overlays/rebuilt`（替代 `--variant`）。doctor 也支持相同的 `--overlay-dir`。这样可明确区分原2019.2位流与新2025.2输出。

目前原工程的 XDC 对应 LVCMOS33，不能据此自动生成1.8V方案。重建后需验证地址、HWH、PL时钟、接口以及板上输出，记录新报告。历史 WNS 正值不等于所有外设路径均已约束，详见硬件审计。

## 本机验证与比赛提交

```bash
python3 build/test_host.py
```

测试覆盖 C 黄金预处理/量化表达式、权重格式、原模型调度和 DMA 生命周期、MMIO调用、外设原表、触控和界面。mock 测试验证软件契约，不模拟 HLS 全网数值；主机未装 Torch 的情况下也不会声称训练验证已执行。板上延迟、输出一致性、准确率、功耗均待实测。

比赛自主选题初级组允许此 Zynq-7000，推荐 PYNQ。评分权重为创新/价值30、性能/资源20、正确性/完整性20、大模型协作/Skill15、文档/复现15。完整规则见 `report/contest_requirements.md`；最终评分细则与赛程仍需官网核验。

提交前补上实际板测输出、可复现构建与时序/资源报告、原始协作聊天导出和数据/第三方代码许可。`skill/` 是本次经验模板；未做跨板实测，不能承诺通用Skill加分。没有发布到 GitHub/Gitee，也没有替原工程、权重或板商素材擅自指定再分发许可证。

用户当前要求不弹安装窗口以便查看PPT。图形安装器已经退出，后续只做后台文件准备和检查。`build/install/check_ready.ps1` 可只读检查安装包、目标路径和管理员状态，不启动任何窗口。
