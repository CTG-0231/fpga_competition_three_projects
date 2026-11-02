# 上板工程与运行入口

当前步骤以 [工程README](../README.md) 为准。终端从工程根执行 `python3 board/lanuch.py`，或运行本目录 `00_one_click_start.ipynb`。保留lanuch原拼写。

`01_bringup_and_demo_optimized.ipynb` 是入口使用的六阶段程序；标准Notebook另存。`overlays/1v8`、`overlays/3v3` 为新TAR原配对，不因目录整理更换。`linux/` 保留镜像/外设集成说明及触摸修复文件；不自动安装应用自启动。

实际电压、镜像、I2C/pinctrl、CMA与接线由板卡环境决定。不要把并列Vivado工程裸机boot.bin写进PYNQ卡，也不要混用不同导出的bit/HWH。
