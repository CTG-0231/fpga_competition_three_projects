# 主机验证

从PYNQ工程根目录运行 `python -B sim/run_host_tests.py --output-dir <全新的外部目录>`。
依赖Python 3.8以上、NumPy和Pillow；C预处理对照用例在有GCC时编译小型参考程序。

`test_*.py` 为原TAR测试及本轮文件路径回归。`host_tests.json` / `host_tests.log` 记录整理后53项：51通过、2跳过。`input_tar_host_tests.*` 记录原TAR50项检查。

测试使用模拟分配器和核调用检查，不访问PYNQ板卡、不下载位流、不模拟完整HLS运算。两项外部原源对照因旧路径未部署而跳过，原因原样保留。
