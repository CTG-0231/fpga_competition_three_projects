# AC820 GT911 触摸修复

日期：2026-10-24，Asia/Shanghai。板卡新地址：192.168.5.9；SSH 主机密钥与原板一致。重启后 Jupyter 初始无活动会话。

## 根因与修复

Linux 的设备树仅配置了 MIO 的复用功能，保留了启动时的强制三态。读取与原工程 `vitis_trash/ps7_init.c` 对照如下：

| 引脚 | 修复前 | 原工程与修复后 | 用途 |
| --- | --- | --- | --- |
| MIO0 | `0x1601` | `0x0600` | GT911 INT，复位时选择地址 |
| MIO50 | `0x1241` | `0x1240` | I²C0 |
| MIO51 | `0x1241` | `0x1240` | I²C0 |

`bit0=1` 强制三态，使软件配置的输出无法生效。[AMD UG585](https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM/Example-Configure-MIO-pin-6-as-a-GPIO-signal) 和 [Xilinx Linux pinctrl 驱动](https://raw.githubusercontent.com/Xilinx/linux-xlnx/xilinx-v2020.2/drivers/pinctrl/pinctrl-zynq.c) 支持这一解释：`set_mux()` 不改变 bit0；显式 `bias-pull-up` 或 `bias-disable` 配置才能解除该状态。

修复通过 Linux pinctrl 设备树 overlay 完成：I²C0 增加 `bias-pull-up`，MIO0 增加 `bias-disable`；暂时解绑再重新绑定对应 GPIO 和 I²C0 驱动以应用配置。未手工写 PS 寄存器，未修改 BOOT.BIN、image.ub 或 I/O 电压标准。PS MIO50/51 保留原 1.8V 配置，PL 使用用户确认的 3.3V 位流。

## 板上验证

- 修复前，`0x5d` 和 `0x14` 的读取均报 `EAGAIN`。
- 修复后，原 GT911 初始化成功；`0x5d:0x8140` 连续 100 次读出 `911`，约 0.061 秒内完成，无读取错误；未选择的 `0x14` 正常返回无设备。
- 配置头读出 `[93,32,3,224,1,5]`，分辨率 800×480，最多 5 个触点。
- 已启动实际 Jupyter 完整应用，自动对焦、106 个权重和触摸均初始化成功，预览持续运行，采样约 5.3–6.2 FPS。
- 已收到 9 次 Detect 和 2 次 Save 的实物点击，包含完整按下、松开记录及正确按钮命中。实际执行后 `saved_count=2`，推理有分类输出。另一次点击位于按钮外下边缘，正确地没有命中。尚未收到 Light 区域的实物点击记录，不声称该位置已完成实物验收。

## 开机持久化

已安装并启用 `ac820-touch-pinctrl.service`，在 Jupyter 和 PL 服务之前应用同一设备树修复。实际启动返回成功，日志确认引脚配置正确；在运行中的 Jupyter/GPIO 会话上走幂等路径，没有重新绑定设备。未为本次验证重启开发板，冷启动验收仍待后续重启。

安装的文件：`/usr/local/sbin/ac820-touch-pinctrl.py`、`/usr/local/share/ac820-touch/gt911_pads_fix.dtbo`、`/etc/systemd/system/ac820-touch-pinctrl.service`。安装前状态记录：`report/touch_backup_20261024T232058/manifest.json`。源码、设备树及回退说明同步保存在 `board/linux/touch_fix/`。

测量数据保存在 `report/touch_debug_status.json`，本机也保留同名副本。
