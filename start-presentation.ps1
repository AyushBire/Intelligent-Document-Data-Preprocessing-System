<#
.SYNOPSIS
Starts the local presentation services and reconnects the Vercel website.
.DESCRIPTION
Keeps all startup commands in one terminal. Requires the existing private
environment, Python environment, PostgreSQL runtime and cloudflared executable.
.PARAMETER NoDeploy
Starts services without committing or pushing a changed tunnel address.
.OUTPUTS
Startup status and the live sign-in URL. Returns a nonzero exit code on failure.
#>
param([switch]$NoDeploy)

$ErrorActionPreference = 'Stop'
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python environment missing: $pythonPath"
}
$startupArguments = @((Join-Path $PSScriptRoot 'scripts\start_presentation.py'))
if ($NoDeploy) { $startupArguments += '--no-deploy' }
& $pythonPath @startupArguments
exit $LASTEXITCODE
