# AC820 摄像头 LCD 预览调试

日期：2026-10-24（Asia/Shanghai）。板卡：192.168.5.7，PYNQ 2.7，OV5640，224×224 BGR888，LCD 800×480。用户确认使用原工程 3.3V 位流。

## 实测结果

| 项目 | 结果 |
| --- | ---: |
| 原 UI 绘制 | 约 1104 ms/帧 |
| 优化后 UI 热路径 | 约 38 ms/帧 |
| LCD 全帧拷贝和缓存刷新（已旋转输入） | 约 2.5 ms |
| 原采集、UI、LCD、PNG 和固定延迟循环 | 0.584 FPS |
| 优化后 LCD 循环，关闭网页编码 | 7.50 FPS |
| 优化后 LCD 循环，网页 JPEG 独立限频 2 FPS | 5.97 FPS |
| 实际 Jupyter 完整应用的一次实时采样 | 6.56 FPS |

循环基准包括相机采集、ARM 绘制和 LCD 写入；网页启用时包括图像编码。数值为板上生产和提交帧的速率，没有用光学仪器测量 LCD 面板的实际刷新，也不包含浏览器接收与绘制延迟。完整应用实时值随场景和采样窗口变化。

## 已部署变更

- `src/trash_pynq/ui.py`：缓存单个界面状态和有界几何数据，使用 24 KB 查表保持预览装饰的逐像素结果；普通帧只更新相机区域。
- `src/trash_pynq/preview.py`：状态未变化时，只更新 LCD 物理缓冲 `[68:404, 436:772]`；状态变化时完整刷新。
- `board/01_bringup_and_demo.ipynb` 和 `board/01_bringup_and_demo_optimized.ipynb`：JPEG 网页预览独立限频；以实际处理耗时计算等待时间；修复 Stop 早于后台任务启动时的竞态。
- `build/make_notebook.py`：同步生成逻辑，避免重新生成后退回慢路径。
- 触摸初始化失败时清理相应资源并允许摄像头继续运行，通过 Jupyter 按钮操作。

板上备份原文件：`/home/xilinx/jupyter_notebooks/pynq_port/report/camera_backup_20261024T230036/`。

## 验证

原字体下 162 帧逐像素回归及 17 类异常输入匹配通过；LCD presenter 的 8 项测试通过。板上额外比较 4 张实时帧和完整 LCD 缓冲，均与原画面逐像素一致。实时任务正常运行，自动对焦已初始化，106 个权重数组已加载，VDMA 状态无驱动错误位。

保留原单帧 VDMA 的停止、缓存同步和分配生命周期。有限 A/B 实验中，跳过每帧重置在第 8 次完成后出现 `0x14810` 错误，因此未部署；采用硬件单帧计数且保留重置也没有提高采集速度。未修改传感器 PLL、曝光、位流或 HLS 核。

GT911 初始化读取 `0x8140` 时反复出现 `BlockingIOError [Errno 11]`，当前实时会话未启用触摸。此问题需另行检查 I²C 和触摸复位链路；摄像头和 LCD 已运行。

## 使用

当前会话已运行优化 Notebook，不需要重复初始化。用 Jupyter 中的 Stop 按钮停止预览，再运行清理单元释放 DMA。`BROWSER_FPS=0` 可关闭网页图像更新，将更多时间留给 LCD；默认值为 2。

详细数据见 `camera_fps_baseline.json`、`camera_fps_optimized.json`、`camera_live_status.json` 和 `camera_rearm_ab.json`。SSH 密码通过运行时环境变量传入，没有保存到代码中。
