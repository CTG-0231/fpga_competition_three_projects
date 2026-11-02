# HLS 2025.2：从 .bin 对象恢复源码，再生成四核 IP

本工程与 `pynq/`、`vivado/` 并列。下面的构建输入来自本包 `src/native_2025_2.zip` 的恢复结果，不依赖本机已有的 HLS 工程、`FUXIAN` 目录或旧构建产物。全部命令在 **Windows PowerShell** 执行，按顺序使用同一个窗口。

## 需要保留哪个版本

- **必须保留 `src/native_2025_2.zip`**：下面恢复源码、重新编译四核 IP 的输入。
- `src/native_2019_2.zip` 是旧版工程的源码快照，仅用于恢复或对照 2019.2；不参与本页的 2025.2 构建，可以从只使用 2025.2 的工作副本中移除。
- 保留 `src/source_catalog.json` 中的 `native_2025_2` 条目，以及 `build/` 下的恢复和构建脚本。不需要安装 HLS 2019.2。

移除旧快照不影响已经恢复的 2025.2 工程或已生成的 IP、XSA、位流。若还要执行完整提交包检查，则需同步移除 `src/source_catalog.json` 中的 `native_2019_2` 条目，并更新本工程及上级提交目录的 `release_checksums.json`。仅删除 ZIP 或修改 README 不会自动更新这些清单。

## 1. 先分清恢复与构建

快照 ZIP 内的 `objects/<sha256>.bin` 是源码文件的内容对象，原文件名保存在 `manifest.json`。用 `build/restore_sources.py` 自动还原文件名、目录和字节；不要逐个改名，也不要把这些 `.bin` 当作 SD 卡镜像。

| 步骤 | 实际输入 | 实际输出 |
| --- | --- | --- |
| 恢复 | `src/native_2025_2.zip` 的对象和清单 | `$Native/src/hls/` 中的 12 个算法文件、5 个测试文件，以及历史导出 IP/报告 |
| 重新构建 | **`$Native/src/hls`** | `$Build/work/projects/<core>/hls.app` 和新的 IP |
| RTL 验证 | **本轮 `$Build` 中生成的四个 IP** | `$Session/rtl_check` 中的日志和结果 |

恢复出的 `exported_ip/` 是历史 IP，不作为下面重新综合的输入。快照内也有旧构建脚本；本说明统一使用提交树 `hls/build/` 的入口，并显式传入恢复出的源码，避免旧入口的目录布局假设。

## 2. 设置本次路径

只修改 `$Package` 和工具路径。`$Package` 指包含 `hls`、`vivado`、`pynq` 的实际解压目录。Python 必须能在 PowerShell 运行；下面用 `python` 命令找到其可执行文件。

```powershell
$ErrorActionPreference = 'Stop'
$Package = (Resolve-Path 'E:/work/FPGA/Qian/fpga_competition_three_projects').Path
$Python = (Get-Command python -CommandType Application -ErrorAction Stop).Source
$VitisRun = 'D:/software/vivado2025.2/2025.2/Vitis/bin/vitis-run.bat'
$VivadoBin = 'D:/software/vivado2025.2/2025.2/Vivado/bin'
$Hls = Join-Path $Package 'hls'
$Session = Join-Path (Split-Path $Package -Parent) ('hls_rebuild_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$Native = Join-Path $Session 'native_hls'
$Build = Join-Path $Session 'build_hls'
if (!(Test-Path -LiteralPath $VitisRun -PathType Leaf)) { throw 'Check VitisRun path' }
if (Test-Path -LiteralPath $Session) { throw 'Choose a NEW Session directory' }
New-Item -ItemType Directory -Path $Session | Out-Null
Write-Host "This run: $Session"
```

`$Session` 位于整个提交树外；**不要预先创建 `$Native` 或 `$Build`**，恢复和构建脚本会创建它们。已有目录即使为空也会被拒绝。需要重做时选新的 `$Session`，保留旧日志。

## 3. 恢复 2025.2 的 .bin 对象

```powershell
& $Python -I -X utf8 -B "$Hls/build/restore_sources.py" --group native_2025_2 --destination $Native
if ($LASTEXITCODE -ne 0) { throw 'HLS restoration failed' }
if (!(Test-Path -LiteralPath "$Native/src/hls/conv/conv.cpp")) { throw 'Restored HLS source missing' }
```

这条命令只读取 `native_2025_2` 对应的快照，并检查该快照及恢复文件的完整性，不读取 `native_2019_2.zip`。因此移除旧版 ZIP 后仍可按本页继续恢复和编译。

`build/check_project.py` 检查的是整个提交包，会读取索引中的所有快照并对照文件清单；它不是本页恢复和编译的前置步骤。旧 ZIP 已删除而索引未同步，或 README 已修改而清单未更新时，该检查会报错，不代表 2025.2 构建依赖旧版本。需要执行全包检查时，先按上面的说明同步索引和清单。

正常恢复共 **355 个文件**；这只是恢复成功，不代表刚完成了综合。实际源码目录是 `$Native/src/hls`，不是 `$Native`、`compile_inputs` 或 `exported_ip`。

## 4. 用恢复出的源码重新构建

```powershell
& $Python -I -X utf8 -B "$Hls/build/hls_2025_2.py" --source "$Native/src/hls" --output $Build --tool $VitisRun --action build
if ($LASTEXITCODE -ne 0) { throw "HLS build failed; inspect $Build/work/runs" }
foreach ($Core in @('conv','pwdwconv','fc','shortcut')) {
    if (!(Test-Path -LiteralPath "$Build/work/projects/$Core/solution1/impl/ip/component.xml")) {
        throw "Missing new IP: $Core"
    }
}
Get-Content -LiteralPath "$Build/summary.json"
```

Python 入口验证 17 个输入文件的 SHA256，再调用 [hls_2025_2.tcl](build/hls_2025_2.tcl)；日志 `tool_version.log` 必须识别为 2025.2。四核均应为 `complete`，汇总 `all_requested_actions_pass` 应为 `true`。

| 文件位置（相对于 `$Build`） | 用途 |
| --- | --- |
| `inputs/` | 从恢复目录复制的原始输入，构建前后核对 SHA256 |
| `compile_inputs/`、`compile_source_diff.json` | 现有 2025.2 兼容流程产生的编译副本及差异记录 |
| `work/projects/<core>/hls.app` | 本轮新建的 HLS 工程 |
| `work/projects/<core>/solution1/impl/ip/component.xml` | 本轮新导出的 IP 描述文件 |
| `exported/<core>.zip` | 本轮 IP 压缩包 |
| `work/runs/<core>/hls.log`、`summary.json` | 本轮日志和状态 |

`fc` 使用 `avgpool_fc` 源码目录；其导出 IP 名称仍为 `fc`。目标器件为 `xc7z020clg484-2`，HLS 周期 5 ns；这不等同于整机实际 FCLK 频率。

## 5. 验证本轮新 IP 的 RTL

```powershell
& $Python -I -X utf8 -B "$Hls/build/validate_hls_rtl.py" --extended --vivado-bin $VivadoBin --output "$Session/rtl_check" --ip "conv=$Build/work/projects/conv/solution1/impl/ip" --ip "pwdwconv=$Build/work/projects/pwdwconv/solution1/impl/ip" --ip "fc=$Build/work/projects/fc/solution1/impl/ip" --ip "shortcut=$Build/work/projects/shortcut/solution1/impl/ip"
if ($LASTEXITCODE -ne 0) { throw "RTL validation failed; inspect $Session/rtl_check" }
Get-Content -LiteralPath "$Session/rtl_check/summary.json"
```

各核必须有 `RTL_FUNCTIONAL_PASS`，没有 `MISMATCH`，并且结果为 `pass`。这是有界输入的顶层 RTL 验证，不能推导完整模型准确率或板上性能。`--action csim` / `cosim` 为另行选择的新构建任务；原测试台的已知限制和失败仍见历史报告，不能以 IP 导出成功代替仿真成功。

## 6. 交给 Vivado 时选择正确流程

只重建随包 Vivado 2025.2 工程及 XSA：按 [Vivado README](../vivado/README.md) 恢复其快照即可，其中已经带有对应的四核 IP，**不要求先执行本页的 HLS 重建**。

希望整机使用**本轮新生成的 HLS IP**：保留 `$Build/work/projects` 的完整路径，继续 [重新集成新 HLS IP 的步骤](../vivado/build/vivado_2025_2/readme.md)。不要以复制旧 IP 或仅打开旧 XSA 代替重建。

## 目录与验证边界

| 推荐目录 | 内容 |
| --- | --- |
| `src/` | 审阅源码 `kernels/`、必需的 2025.2 对象快照及恢复索引；2019.2 快照仅用于旧版留档 |
| `sim/` | 测试台审阅副本与历史 RTL 结果 |
| `build/` | 恢复、校验、HLS/Tcl 构建与 RTL 验证入口 |
| `board/` | 四核寄存器契约与整机集成说明 |
| `data/` | 定点输入、参考输出格式说明 |
| `skill/` | 本流程的可复用技能 |
| `report/` | 带来源的历史综合、兼容差异和功能报告 |

本次文档修订不修改算法源码、2025.2 快照或构建脚本。现有构建器会在外部副本中禁用一处旧 DATAFLOW、调整偏置复制、将 PW 偏置容量 1024 扩为 1280。这是**原有 2025.2 流程**，本次文档修订没有增加代码修改。该容量差异会影响某些 1280 通道输入，因此不能宣称与原 2019.2 RTL 所有输入等价。具体历史依据见 [HLS 报告](report/hls_2025_2/readme.md)。修改本说明本身不代表重新执行了四核综合或板测。
