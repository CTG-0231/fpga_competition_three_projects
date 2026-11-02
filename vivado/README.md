# Vivado 2025.2：从 .bin 对象恢复工程，再构建 bit 和 XSA

本工程与 `hls/`、`pynq/` 并列，Vitis 裸机软件归入本工程。下面的主流程只依赖本提交包、Python 和已安装的 Vivado 2025.2：**恢复对象快照 → 打开恢复出的 `p/leaf.xpr` → 重新综合/实现 → 生成 bit → 导出含 bit 的 XSA**。不使用已有 `vivado_build`、`FUXIAN`、旧 XSA 或 `board/` 内的历史位流。

## 1. 是否需要先恢复 HLS

**单独复现随包 Vivado 工程，不需要。** `src/native_2025_2.zip` 同时保存了 2025.2 XPR、BD、RTL、XDC，以及 `workspace/ip_repo/` 中四个已导出的 HLS IP。恢复后 Vivado 可以使用这些 IP 重新综合整机。

如果要从 C++ 重新生成四核并让整机使用**本轮新 IP**，先执行 [HLS README](../hls/README.md)，再执行 [完整重新集成流程](build/vivado_2025_2/readme.md)。这与本页“重建随包 2025.2 原生工程”是两个明确的入口，不能混用输入路径。

## 2. 设置路径（Windows PowerShell）

以下所有 PowerShell 代码块在**同一个窗口**依次执行；只修改 `$Package`、`$Vivado`。`$Package` 指实际解压后包含三个工程的目录。不要把 PowerShell 命令粘到 Vivado Tcl Console。

```powershell
$ErrorActionPreference = 'Stop'
$Package = (Resolve-Path 'E:/work/FPGA/Qian/fpga_competition_three_projects').Path
$Python = (Get-Command python -CommandType Application -ErrorAction Stop).Source
$Vivado = 'D:/software/vivado2025.2/2025.2/Vivado/bin/vivado.bat'
$Project = Join-Path $Package 'vivado'
$Session = Join-Path (Split-Path $Package -Parent) ('vivado_rebuild_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$Native = Join-Path $Session 'native_vivado'
$Output = Join-Path $Session 'output'
$Tcl = Join-Path $Session 'build_restored.tcl'
if (!(Test-Path -LiteralPath $Vivado -PathType Leaf)) { throw 'Check Vivado 2025.2 path' }
if (Test-Path -LiteralPath $Session) { throw 'Choose a NEW Session directory' }
New-Item -ItemType Directory -Path $Session | Out-Null
Write-Host "This run: $Session"
```

`$Session` 是提交树的同级新目录。**不要预先创建 `$Native` 或 `$Output`**；不要用 `fpga_competition_three_projects/vivado_01`，因为仍在整个提交树内。重新尝试时换一个新 Session，保留失败现场。

## 3. 校验并恢复 .bin 对象快照

```powershell
& $Python -I -X utf8 -B "$Project/build/check_project.py"
if ($LASTEXITCODE -ne 0) { throw 'Vivado package verification failed' }
& $Python -I -X utf8 -B "$Project/build/restore_sources.py" --group native_2025_2 --destination $Native
if ($LASTEXITCODE -ne 0) { throw 'Vivado restoration failed' }
if (!(Test-Path -LiteralPath "$Native/p/leaf.xpr")) { throw 'Restored XPR missing' }
```

成功恢复 **919 个文件**。ZIP 中的 `objects/<sha256>.bin` 是内容对象；恢复脚本按 `manifest.json` 重建原生文件名并校验 SHA256。这些对象不是烧录镜像，不要手动改扩展名。

恢复后的关键位置：

```text
native_vivado/
├── p/leaf.xpr
└── workspace/
    ├── inputs/          # BD、RTL、XDC
    └── ip_repo/
        ├── conv/component.xml
        ├── pwdwconv/component.xml
        ├── fc/component.xml
        └── shortcut/component.xml
```

原生树恢复工具要求的文件大小写；它位于提交树外，不再对其内部文件做批量小写改名。

## 4. 写出本次构建的 Tcl 脚本

**下面仍是 PowerShell 代码块，整段复制执行。** 它只把 Tcl 文本写入 `$Session/build_restored.tcl`；实际输入是第 3 步恢复的工程。`inspect` 模式只检查工程和 IP；`build` 模式才运行综合、实现及导出。

```powershell
@'
if {$argc != 3} { error "Expected: restored_root output_dir inspect|build" }
set native [file normalize [lindex $argv 0]]
set output [file normalize [lindex $argv 1]]
set mode [lindex $argv 2]
if {$mode ni {inspect build}} { error "Mode must be inspect or build" }
if {[version -short] ne "2025.2"} { error "Use Vivado 2025.2" }
if {![info exists ::env(XILINX_LOCAL_USER_DATA)] || $::env(XILINX_LOCAL_USER_DATA) ne "no"} {
    error "Set XILINX_LOCAL_USER_DATA=no BEFORE starting Vivado"
}
set_param general.maxThreads 1
set xpr [file join $native p leaf.xpr]
if {![file isfile $xpr]} { error "Restored p/leaf.xpr missing: $xpr" }
set ip_dirs {}
foreach core {conv pwdwconv fc shortcut} {
    set dir [file join $native workspace ip_repo $core]
    if {![file isfile [file join $dir component.xml]]} { error "Missing HLS IP: $dir" }
    lappend ip_dirs $dir
}
if {$mode eq "build" && [file exists $output]} {
    error "Output already exists; preserve logs and use a fresh restored workspace"
}
open_project $xpr
if {[get_property PART [current_project]] ne "xc7z020clg484-2"} { error "Unexpected FPGA part" }
# Resolve repository locations inside this newly restored tree only.
set_property ip_repo_paths $ip_dirs [current_project]
update_ip_catalog
foreach core {conv pwdwconv fc shortcut} {
    if {![llength [get_ipdefs -all -quiet xilinx.com:hls:${core}:0.0]]} {
        error "IP definition not discovered: $core"
    }
}
set bd_files [get_files -quiet */design_1.bd]
if {[llength $bd_files] != 1} { error "Expected one restored design_1.bd" }
set bd [lindex $bd_files 0]
if {![file isfile $bd]} { error "Restored design_1.bd file missing" }
foreach run [get_runs] {
    if {[regexp -nocase {running|queued} [get_property STATUS $run]]} {
        error "Run active; do not operate on a workspace used by another Vivado session"
    }
}
if {$mode eq "inspect"} {
    puts "RESTORED_PROJECT_INSPECTION_PASS: $xpr"
    close_project
    exit
}
file mkdir $output
report_ip_status -file [file join $output ip_status.rpt]
# This is a fresh reconstruction: discard restored run status, not source files.
reset_run impl_1
foreach run [get_runs -filter {IS_SYNTHESIS == 1}] { reset_run $run }
generate_target all $bd
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {[get_property STATUS [get_runs synth_1]] ne "synth_design Complete!" ||
    [get_property PROGRESS [get_runs synth_1]] ne "100%"} { error "Synthesis failed" }
launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1
set impl [get_runs impl_1]
set bit [file join [get_property DIRECTORY $impl] design_1_wrapper.bit]
if {[get_property STATUS $impl] ne "write_bitstream Complete!" ||
    [get_property PROGRESS $impl] ne "100%" || ![file isfile $bit]} {
    error "New bitstream was not completed; do not export XSA"
}
if {[file size $bit] == 0} { error "Empty bitstream" }
open_run impl_1
report_utilization -file [file join $output utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $output timing_summary.rpt]
check_timing -verbose -file [file join $output check_timing.rpt]
report_drc -file [file join $output drc.rpt]
report_methodology -file [file join $output methodology.rpt]
report_clocks -file [file join $output clocks.rpt]
report_io -file [file join $output io.rpt]
write_hw_platform -fixed -include_bit -force -file [file join $output leaf.xsa]
file copy $bit [file join $output leaf.bit]
close_project
puts "RESTORED_PROJECT_XSA_BUILD_COMPLETED"
'@ | Set-Content -LiteralPath $Tcl -Encoding ascii
```

该脚本不修改算法、RTL、BD 功能或 XDC 电气参数。它在**恢复副本**内重新定位 IP 仓库、重置运行状态并生成工具输出。`reset_run` 会清理该恢复副本中的运行产物，因此只用于本流程新建的工作目录，不能拿去覆盖你正在使用的旧工程。

## 5. 先检查路径和 IP，再开始构建

环境变量只设在当前 PowerShell 进程及其子进程中，用于绕开本机先前出现的 Tcl 用户应用加载错误，不修改 Windows 全局配置。使用显式 2025.2 路径，避免双击 XPR 被旧版 Vivado 打开。

```powershell
$env:XILINX_LOCAL_USER_DATA = 'no'
Push-Location $Session
try {
    & $Vivado -mode batch -nojournal -log "$Session/inspect.log" -source $Tcl -tclargs $Native $Output inspect
    if ($LASTEXITCODE -ne 0) { throw "Inspect failed: $Session/inspect.log" }
    $InspectLog = Get-Content -LiteralPath "$Session/inspect.log" -Raw
    if ($InspectLog -notmatch '(?m)^RESTORED_PROJECT_INSPECTION_PASS:' -or $InspectLog -match '(?m)^ERROR:') {
        throw "Inspect incomplete: $Session/inspect.log"
    }
} finally { Pop-Location }
```

检查通过后，执行下面这段才会开始较长时间的综合/实现。不要同时在 GUI 中打开并构建同一个 `$Native/p/leaf.xpr`。

快照没有保留旧综合 DCP 等运行缓存，首次加载可能提示 `generated file not found ... .dcp`；后面的生成目标和综合会重新生成它们。源码、BD 或 `component.xml` 缺失则不能按这一情况忽略，必须先查明原因。

```powershell
Push-Location $Session
try {
    & $Vivado -mode batch -nojournal -log "$Session/build.log" -source $Tcl -tclargs $Native $Output build
    if ($LASTEXITCODE -ne 0) { throw "Build failed: $Session/build.log" }
    $BuildLog = Get-Content -LiteralPath "$Session/build.log" -Raw
    if ($BuildLog -notmatch '(?m)^RESTORED_PROJECT_XSA_BUILD_COMPLETED' -or $BuildLog -match '(?m)^ERROR:') {
        throw "Build incomplete: $Session/build.log"
    }
    if (!(Test-Path -LiteralPath "$Output/leaf.xsa")) { throw 'New XSA missing' }
} finally { Pop-Location }
Get-FileHash -LiteralPath "$Output/leaf.xsa", "$Output/leaf.bit" -Algorithm SHA256
```

成功结果为 **`$Session/output/leaf.xsa`**，包含本轮生成的 bit；旁边有 `leaf.bit` 和时序、资源、DRC 等报告。`route_design Complete!` 还不是 bit 完成，不能仅凭工具退出或看到旧 XSA 就判成功。发生错误时保留 `build.log` 和 `native_vivado/p/leaf.runs/*/runme.log`；不要重复重置仍在运行的工程。

## 6. 从本轮 XSA 成套导出 bit/HWH（可选）

```powershell
& $Python -I -X utf8 -B "$Project/build/export_overlay.py" "$Output/leaf.xsa" "$Session/overlay" --io-voltage 3.3 --hls-policy regenerated_2025_2_original_algorithm
if ($LASTEXITCODE -ne 0) { throw 'Overlay export failed' }
& $Python -I -X utf8 -B "$Project/build/validate_pynq27_hwh.py" --hwh "$Session/overlay/leaf.hwh" --output "$Session/hwh_check.json"
if ($LASTEXITCODE -ne 0) { throw 'Offline HWH check failed' }
```

这里的 policy 字符串是现有导出器对 **2025.2 HLS 系列**的固定标识：本页复用快照中已导出的 HLS IP，再重新综合整机；不表示本轮重新执行了 HLS，也不证明其与 2019.2 全输入等价。3.3 V 对应本快照的 PL 约束，不可据此推断所有 PS MIO 电平。

这些产物保存到新目录。**不自动覆盖并列 PYNQ 工程的配对 bit/HWH、驱动或 SD 启动文件。** 离线 HWH 解析通过不代表整机上板通过。

## 7. 可选 Vitis 裸机分支

确实需要重建裸机程序时，再用本轮 XSA：

```powershell
$Vitis = 'D:/software/vivado2025.2/2025.2/Vitis'
& $Python -I -X utf8 -B "$Project/build/build_vitis_2025_2.py" --workspace "$Session/ps" --xsa "$Output/leaf.xsa" --vitis $Vitis
if ($LASTEXITCODE -ne 0) { throw 'Vitis build failed; inspect the new PS workspace logs' }
```

此分支使用包内 PS 软件，生成裸机平台/BSP/FSBL/ELF/`boot.bin`，不是 PYNQ Linux 镜像，也不是本次 HLS/Vivado 恢复的前置步骤。原始 Vitis 完整资料保存在 `src/vitis/native_from_rar.zip`；原始名恢复与 2025.2 PS 源快照索引见 `src/source_catalog.json`。

## 目录、成功标准与已知边界

| 推荐目录 | 内容 |
| --- | --- |
| `src/` | RTL/BD/XDC 审阅副本、原名对象快照、Vitis PS 软件 |
| `sim/` | 地址、寄存器、PS/PL 接口验证记录 |
| `build/` | 校验、恢复、整机迁移/构建及导出入口 |
| `board/` | 明确标为历史结果的 overlay 和裸机产物 |
| `data/` | 输入与参考资料索引 |
| `skill/` | 恢复、构建、交付技能 |
| `report/` | 综合、实现、时序、资源和历史失败记录 |

验收需要区分“对象恢复成功”“工程能打开”“本轮 bit/XSA 构建成功”和“实物功能通过”。本说明修订检查恢复路径及工程加载，不把历史构建或原板测记录记作本轮新测试。

已有 2025.2 迁移包含 HLS 兼容副本变化，PW 1024/1280 容量差异不能描述为与原版全输入等价。现有时序报告也有外部相机/IO 约束覆盖不足；正 WNS 不代表所有路径已约束。保留 [原迁移记录](report/migration_2025_2_original.md) 和 [时序审查](report/vivado_2025_2/timing_review.md) 的时间、范围，不把历史产物或本次文档修改当作新的板上验证。
