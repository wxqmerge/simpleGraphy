# Builds install.exe from install.cs (next to this script) using Windows
# PowerShell 5.1's built-in .NET Framework compiler, so the result runs on any
# Windows without the .NET SDK. This folder is baked into the exe as a
# fallback source path.
param([string]$OutFile)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $OutFile) { $OutFile = Join-Path $root 'install.exe' }

$cs = Get-Content -Raw -LiteralPath (Join-Path $root 'install.cs')
$cs = $cs.Replace('__SRC_ROOT__', $root)

$tmpCs = Join-Path $env:TEMP 'simpleGraphy_install_src.cs'
Set-Content -LiteralPath $tmpCs -Value $cs -Encoding UTF8

$runner = @'
$ErrorActionPreference = 'Stop'
$src = Get-Content -Raw -LiteralPath '__CS__'
if (Test-Path -LiteralPath '__EXE__') { Remove-Item -LiteralPath '__EXE__' -Force }
Add-Type -TypeDefinition $src -OutputType ConsoleApplication -OutputAssembly '__EXE__' -ReferencedAssemblies 'System.dll'
if (-not (Test-Path -LiteralPath '__EXE__')) { throw 'compiler produced no output' }
'@
# double single quotes so apostrophes in paths survive the quoted literals below
$runner = $runner.Replace('__CS__', $tmpCs.Replace("'", "''"))
$runner = $runner.Replace('__EXE__', $OutFile.Replace("'", "''"))

$runnerTmp = Join-Path $env:TEMP 'simpleGraphy_install_build.ps1'
Set-Content -LiteralPath $runnerTmp -Value $runner -Encoding UTF8

$ps51 = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path $ps51)) { $ps51 = 'powershell' }

& $ps51 -NoProfile -ExecutionPolicy Bypass -File $runnerTmp
if ($LASTEXITCODE -ne 0) { throw "install.exe build failed (exit $LASTEXITCODE)" }

Write-Host "Built: $OutFile"
