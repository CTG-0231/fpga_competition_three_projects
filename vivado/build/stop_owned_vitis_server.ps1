param(
    [Parameter(Mandatory=$true)][ValidateRange(1024,65535)][int]$ServerPort,
    [Parameter(Mandatory=$true)][string]$VitisInstall
)
$ErrorActionPreference = 'Stop'
# Only a port reported as newly started in this build stage may be supplied.
# Windows Vitis dispose() can kill its cmd launcher but leave Java holding the
# workspace lock. Never terminate unrelated Vitis/Java/user applications.
$connections = @(Get-NetTCPConnection -LocalPort $ServerPort -State Listen -ErrorAction SilentlyContinue)
$processIds = @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
$installPath = [IO.Path]::GetFullPath($VitisInstall).Replace('\','/').TrimEnd('/')
foreach ($serverProcessId in $processIds) {
    $serverProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$serverProcessId"
    if ($null -eq $serverProcess) { continue }
    $serverCommand = $serverProcess.CommandLine.Replace('\','/')
    if ($serverProcess.Name -ne 'java.exe' -or
        -not $serverCommand.Contains('com.xilinx.rigel.app.RigelApp') -or
        $serverCommand.IndexOf($installPath, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw 'Refusing to stop a listener whose identity does not match this Vitis build.'
    }
    Stop-Process -Id $serverProcessId -ErrorAction Stop
    Wait-Process -Id $serverProcessId -Timeout 10 -ErrorAction SilentlyContinue
    Write-Output "Released owned Vitis server at port $ServerPort"
}
