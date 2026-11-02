# 2025.2 构建入口：恢复工程与重新集成的区别

**只要从 .bin 快照恢复出的 2025.2 Vivado 工程生成 XSA，执行 [工程根 README](../../README.md) 即可。** 主流程的完整 PowerShell/Tcl 均在那里：恢复 `native_2025_2` → `$Native/p/leaf.xpr` → 重新综合/实现 → 新 XSA。不依赖已有本机构建。

本目录 `build.py` 是另一条**重新集成本轮新 HLS IP**的入口。它的 `--native-project` 读取原始 `trash.xpr` / `trash.srcs` 布局，不能传入恢复出的 2025.2 `p/leaf.xpr` 目录。两者输入格式不同。

## 1. 先从对象快照生成本轮 HLS IP

完整执行 [HLS README](../../../hls/README.md) 的第 2～5 步。保留该 PowerShell 会话中的 `$Package`、`$Python`、`$Session`、`$Build`。本流程后续输入为 **`$Build/work/projects`** 中本轮生成的四个 IP；不是历史 `board/`、`FUXIAN` 或旧 XSA。

如果重开了 PowerShell，需要把上述变量重新设为**该轮实际记录的路径**，不要重新计算时间戳指向不存在的目录。

## 2. 从原始 .bin 对象恢复 Vivado 源工程

这里恢复 `native_2019_2` 是为了读取原版 BD/RTL/XDC，再由迁移入口生成新的 2025.2 工程；不要求安装旧版 Vivado。

```powershell
$Project = Join-Path $Package 'vivado'
$Vivado = 'D:/software/vivado2025.2/2025.2/Vivado/bin/vivado.bat'
$Original = Join-Path $Session 'native_vivado_original'
$Pl = Join-Path $Session 'build_pl'
& $Python -I -X utf8 -B "$Project/build/check_project.py"
if ($LASTEXITCODE -ne 0) { throw 'Vivado package verification failed' }
& $Python -I -X utf8 -B "$Project/build/restore_sources.py" --group native_2019_2 --destination $Original
if ($LASTEXITCODE -ne 0) { throw 'Original Vivado restoration failed' }
if (!(Test-Path -LiteralPath "$Original/board/trash.xpr")) { throw 'Original project missing' }
foreach ($Core in @('conv','pwdwconv','fc','shortcut')) {
    if (!(Test-Path -LiteralPath "$Build/work/projects/$Core/solution1/impl/ip/component.xml")) {
        throw "Missing newly built HLS IP: $Core"
    }
}
```

原始 Vivado 快照恢复 407 个文件。`$Original` 必须是全新外部目录，不要提前创建；本轮 PL 输出也必须在提交树外，并与原始源码、IP 输入互不包含。

## 3. 重新集成、综合并生成 XSA

```powershell
& $Python -I -X utf8 -B "$Project/build/vivado_2025_2/build.py" --native-project "$Original/board" --hls-ip-root "$Build/work/projects" --workspace $Pl --vivado $Vivado --python $Python
if ($LASTEXITCODE -ne 0) { throw "Vivado build failed; inspect $Pl/build_status.json" }
Get-Content -LiteralPath "$Pl/build_status.json"
if (!(Test-Path -LiteralPath "$Pl/r/leaf.xsa")) { throw 'New XSA missing' }
Get-FileHash -LiteralPath "$Pl/r/leaf.xsa" -Algorithm SHA256
```

入口在新的 workspace 中准备 BD/RTL/XDC，接入明确指定的四个新 IP，调用本目录 `migrate.tcl`、`flow.tcl`。结果为 `$Pl/r/p/leaf.xpr`、`$Pl/r/leaf.xsa` 和本轮报告。它不是在旧工程中直接导出一个既有 XSA。

仅想提前检查准备阶段，可先在**另一个新 workspace**（例如 `$Session/prepare_check`）使用相同命令并增加 `--prepare-only`；准备成功不代表综合或实现通过。失败重试保留日志，优先选新输出目录。`--resume` 仅适用于源哈希不变且运行进程均已停止的现场；若父级综合停在失败状态，应先诊断，不能用反复执行导出命令掩盖失败。

## 4. 导出本轮配对

```powershell
& $Python -I -X utf8 -B "$Project/build/export_overlay.py" "$Pl/r/leaf.xsa" "$Session/overlay_new_hls" --io-voltage 3.3 --hls-policy regenerated_2025_2_original_algorithm
if ($LASTEXITCODE -ne 0) { throw 'Overlay export failed' }
& $Python -I -X utf8 -B "$Project/build/validate_pynq27_hwh.py" --hwh "$Session/overlay_new_hls/leaf.hwh" --output "$Session/hwh_new_hls_check.json"
if ($LASTEXITCODE -ne 0) { throw 'Offline HWH validation failed' }
```

## 原有迁移行为与边界

构建器在复制后的 BD 中处理生成目录、视频输入 IP 升级、RGB565 到 RGB888 映射及已核对的单 ID AXI 配置；IP 导出包按指定输入读取。输入检查包含实际综合源哈希、物理接口、寄存器及地址，不能代替形式等价证明。

构建入口以单线程/单任务运行，子进程设置 `XILINX_LOCAL_USER_DATA=no`；Python 调用使用隔离模式，不修改 Windows 全局环境。安装工具、许可证或上板不是此脚本的行为。

保留 `build_status.json`、实际工具版本、源清单、运行日志及资源/时序/DRC 报告。正 WNS 只描述已约束路径；外部相机/IO 时序覆盖和电气适配仍需单独确认。新硬件不得自动覆盖并列 PYNQ 的旧配对，裸机启动文件不得冒充 PYNQ 系统镜像。
