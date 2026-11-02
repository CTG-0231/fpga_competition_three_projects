param(
    [Parameter(Mandatory=$true)][string]$Vivado,
    [Parameter(Mandatory=$true)][string]$Script,
    [Parameter(Mandatory=$true)][string]$Log,
    [Parameter(Mandatory=$true)][string]$Prepared,
    [Parameter(Mandatory=$true)][string]$Result,
    [Parameter(Mandatory=$true)][string]$NativeProject,
    [ValidateSet('migrate','resume')][string]$Mode = 'migrate'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
if (-not (Test-Path -LiteralPath $Vivado -PathType Leaf)) { throw 'Vivado executable is missing.' }
$nativeArgs = if ($Mode -eq 'resume') { @($Result,$NativeProject) } else { @($Prepared,$Result,$NativeProject,'all') }
# Native diagnostics belong in the captured console/log; preserve its exit code.
$ErrorActionPreference = 'Continue'
& $Vivado -mode batch -nojournal -log $Log -source $Script -tclargs @nativeArgs
$code = $LASTEXITCODE
if ($null -eq $code) { exit 1 }
exit $code
