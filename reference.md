# 按 README 重新还原、编译、导出

本次工作目录是 `E:/work/FPGA/Qian/rebuild`。输入来自 `fpga_competition_three_projects` 中 HLS、Vivado README 指向的原生对象快照。

本轮从 `.bin` 对象重新还原，不使用刚才已经编译好的工程来代替还原。按 HLS README 调用 `hls_2025_2.py`，由它调用 `hls_2025_2.tcl` 生成四核；再将本轮 IP 放入恢复的 Vivado 工程。Vivado Tcl 原文直接取自它的 README，随后用 PowerShell 启动综合、实现和导出。只调整本机路径，并补充新 HLS IP 的接入步骤。

## 本轮文件位置

| 内容 | 位置 |
| --- | --- |
| HLS 恢复源码 | `hls/source/src/hls/` |
| HLS 本轮工程 | `hls/build/work/projects/<core>/hls.app` |
| Vivado 恢复工程 | `vivado/restored/p/leaf.xpr` |
| Vivado 本轮 Tcl | `vivado/restored/build_from_readme.tcl` |
| 本轮 XSA / bit / HWH | `results/readme_build/` |
| 工具运行输出 | `results/readme_console.log`、`results/readme_vivado.log`、`results/readme_retry.log` |

旧工作副本暂时保留，本轮以表内路径为准。原来的 `results/rebuild_2025_2.rar` 是上一轮产物，不是本轮编译结果。根目录仍为 hls、vivado、results 和本说明。

## 实际启动命令

```powershell
Set-Location 'E:/work/FPGA/Qian/rebuild'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File './hls/restore_compile.ps1'
```

脚本执行一次完整流程。已有恢复/构建目标不能原地重复执行还原；不要在当前任务运行时再启动第二份。

## 本次实际执行的 PowerShell 全文

```powershell
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
$Package = 'E:/work/FPGA/Qian/fpga_competition_three_projects'
$Python = 'C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$VitisRun = 'D:/software/vivado2025.2/2025.2/Vitis/bin/vitis-run.bat'
$Vivado = 'D:/software/vivado2025.2/2025.2/Vivado/bin/vivado.bat'
$Hls = Join-Path $Package 'hls'
$Project = Join-Path $Package 'vivado'
$HlsNative = Join-Path $Root 'hls/source'
$HlsBuild = Join-Path $Root 'hls/build'
$Native = Join-Path $Root 'vivado/restored'
$Output = Join-Path $Root 'results/readme_build'
$Tcl = Join-Path $Native 'build_from_readme.tcl'
$env:XILINX_LOCAL_USER_DATA = 'no'
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

# HLS README: restore the native 2025.2 snapshot.
Write-Host 'STEP 1: Restore HLS from .bin objects'
& $Python -I -X utf8 -B "$Hls/build/restore_sources.py" --group native_2025_2 --destination $HlsNative
if ($LASTEXITCODE -ne 0) { throw 'HLS restoration failed' }

# HLS README: the documented Python entry calls the packaged HLS Tcl.
Write-Host 'STEP 2: Compile HLS 2025.2 and export four IPs'
Push-Location "$Root/hls"
try {
    & $Python -I -X utf8 -B "$Hls/build/hls_2025_2.py" --source "$HlsNative/src/hls" --output $HlsBuild --tool $VitisRun --action build
    if ($LASTEXITCODE -ne 0) { throw 'HLS build failed' }
} finally { Pop-Location }

# Vivado README: restore native_2025_2, then open its p/leaf.xpr.
Write-Host 'STEP 3: Restore Vivado from .bin objects'
& $Python -I -X utf8 -B "$Project/build/restore_sources.py" --group native_2025_2 --destination $Native
if ($LASTEXITCODE -ne 0) { throw 'Vivado restoration failed' }

# Connect this run's freshly exported IPs to the restored Vivado project.
foreach ($Core in @('conv','pwdwconv','fc','shortcut')) {
    Copy-Item -Path "$HlsBuild/work/projects/$Core/solution1/impl/ip/*" -Destination "$Native/workspace/ip_repo/$Core" -Recurse -Force
}

# Take the Tcl block directly from the Vivado README without changing it.
$Doc = Get-Content -LiteralPath "$Project/README.md" -Raw -Encoding UTF8
$Match = [regex]::Match($Doc, "(?s)@'\r?\n(.*?)\r?\n'@ \| Set-Content")
if (!$Match.Success) { throw 'Vivado README Tcl block not found' }
[IO.File]::WriteAllText($Tcl, $Match.Groups[1].Value, [Text.Encoding]::ASCII)

Write-Host 'STEP 4: Vivado synthesis, implementation, bitstream and XSA'
Push-Location $Native
try {
    & $Vivado -mode batch -nojournal -log "$Root/results/readme_vivado.log" -source $Tcl -tclargs $Native $Output build
    if ($LASTEXITCODE -ne 0) { throw 'Vivado build failed; see results/readme_vivado.log' }
    $BuildLog = Get-Content -LiteralPath "$Root/results/readme_vivado.log" -Raw
    if ($BuildLog -notmatch '(?m)^RESTORED_PROJECT_XSA_BUILD_COMPLETED' -or $BuildLog -match '(?m)^ERROR:') {
        throw 'Vivado did not finish the documented flow'
    }
} finally { Pop-Location }

Write-Host 'STEP 5: Export bit and HWH from the new XSA'
& $Python -I -X utf8 -B "$Project/build/export_overlay.py" "$Output/leaf.xsa" $Output --io-voltage 3.3 --hls-policy regenerated_2025_2_original_algorithm
if ($LASTEXITCODE -ne 0) { throw 'Overlay export failed' }
Write-Host "COMPLETED: $Output"

```

## 首轮 Vivado 的退出异常及恢复

本轮从对象还原和 HLS 四核重建开始执行。首次 Vivado 批处理有两个模块在退出时出现 `EXCEPTION_ACCESS_VIOLATION`：`design_1_axi_mem_intercon_3_imp_xbar_0_synth_1`、`design_1_ps7_0_axi_periph_imp_auto_pc_0_synth_1`。日志显示它们已完成综合并写出 DCP，其余 37 个子任务完成。

首轮批处理结束后，实际执行以下恢复命令。它只重置失败项和被阻塞的顶层综合，随后继续实现和导出，不修改算法或 RTL；导出部分仍沿用 README Tcl 原文。

```powershell
Set-Location 'E:/work/FPGA/Qian/rebuild'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File './vivado/restored/resume_compile.ps1'
```

恢复脚本全文：

```powershell
$ErrorActionPreference='Stop'
$Native=$PSScriptRoot
$Root=Split-Path (Split-Path $Native -Parent) -Parent
$Output=Join-Path $Root 'results/readme_build'
$Python='C:/Users/ASUS/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$Vivado='D:/software/vivado2025.2/2025.2/Vivado/bin/vivado.bat'
$Project='E:/work/FPGA/Qian/fpga_competition_three_projects/vivado'
$env:XILINX_LOCAL_USER_DATA='no'
Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue

# Run only after the initial README batch process has stopped.
$Prefix=@'
if {[version -short] ne "2025.2"} { error "Use Vivado 2025.2" }
set native [file normalize [lindex $argv 0]]
set output [file normalize [lindex $argv 1]]
set_param general.maxThreads 1
open_project [file join $native p leaf.xpr]
foreach run [get_runs] {
    set state [get_property STATUS $run]
    if {[regexp -nocase {running} $state]} { error "Run is still active: $run" }
    if {[regexp -nocase {error|fail} $state]} { reset_run $run }
}
if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} {
    reset_run synth_1
    launch_runs synth_1 -jobs 1
    wait_on_run synth_1
}
if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!"} { error "Synthesis failed" }
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1
set impl [get_runs impl_1]
set bit [file join [get_property DIRECTORY $impl] design_1_wrapper.bit]
if {[get_property STATUS $impl] ne "write_bitstream Complete!" || [get_property PROGRESS $impl] ne "100%" || ![file isfile $bit]} { error "Bitstream not complete" }
open_run impl_1
'@
$Original=Get-Content -LiteralPath "$Native/build_from_readme.tcl" -Raw
$Tail=($Original -split 'open_run impl_1',2)[1]
$Resume=Join-Path $Native 'resume_from_failure.tcl'
[IO.File]::WriteAllText($Resume,$Prefix+"`n"+$Tail,[Text.Encoding]::ASCII)
Push-Location $Native
try {
    & $Vivado -mode batch -nojournal -log "$Root/results/readme_retry.log" -source $Resume -tclargs $Native $Output
    if ($LASTEXITCODE -ne 0) { throw 'Vivado retry failed' }
    $Log=Get-Content -LiteralPath "$Root/results/readme_retry.log" -Raw
    if ($Log -notmatch '(?m)^RESTORED_PROJECT_XSA_BUILD_COMPLETED' -or $Log -match '(?m)^ERROR:') { throw 'Vivado retry incomplete' }
} finally { Pop-Location }
& $Python -I -X utf8 -B "$Project/build/export_overlay.py" "$Output/leaf.xsa" $Output --io-voltage 3.3 --hls-policy regenerated_2025_2_original_algorithm
if ($LASTEXITCODE -ne 0) { throw 'Overlay export failed' }
Write-Host "COMPLETED: $Output"

```

## 本轮完成结果

2026-11-01 01:01（本机时间）完成。恢复批处理返回码为 `0`，日志记录 `RESTORED_PROJECT_XSA_BUILD_COMPLETED` 和 `COMPLETED`。

- HLS：`conv`、`pwdwconv`、`fc`、`shortcut` 已用 2025.2 重新编译并导出 IP，已接入本轮 Vivado 工程。
- Vivado：2025.2 顶层综合、布局、布线、`write_bitstream`、`write_hw_platform -include_bit` 完成。
- 输出：`results/readme_build/leaf.xsa`、`leaf.bit`、`leaf.hwh`。
- 最终已约束路径时序：WNS `0.530 ns`、WHS `0.022 ns`，建立和保持违例端点均为 `0`。仍有原工程的未约束路径（包括摄像头 PCLK 无时钟定义），本轮未改动其约束；不把这一结果称为所有路径均通过时序。
- 本轮仅完成主机端编译与导出，没有重新上板验证，未改动 PYNQ 工程。

打开本轮 Vivado 工程用 `vivado/restored/p/leaf.xpr`；四个 HLS 工程分别位于 `hls/build/work/projects/<core>/hls.app`。不要把旧工作副本或旧 RAR 当成本轮结果。

## 打包本轮工程和结果

从 rebuild 根目录执行以下 PowerShell。明确列出本轮输入，不包含旧工作副本，也不把目标 RAR 本身放进压缩包。只生成一个 RAR，不另建校验目录。

```powershell
Set-Location 'E:/work/FPGA/Qian/rebuild'
& 'D:/software/winrar/Rar.exe' a -cfg- -ma5 -m3 -md32m -mt2 -idq -r `
  'results/readme_build/rebuilt_2025_2.rar' `
  'hls/source' 'hls/build' 'hls/restore_compile.ps1' `
  'vivado/restored' 'reference.md' `
  'results/readme_build/leaf.xsa' `
  'results/readme_build/leaf.bit' `
  'results/readme_build/leaf.hwh' `
  'results/readme_build/*.rpt' `
  'results/readme_console.log' `
  'results/readme_vivado.log' `
  'results/readme_retry.log'
if ($LASTEXITCODE -ne 0) { throw 'RAR packaging failed' }
```

完整的从 `.bin` 还原命令需要保留输入提交目录 `fpga_competition_three_projects`（上述 `$Package`）。本 RAR 保存本轮已经还原并编译的工程和输出，不重复包含输入快照库。

