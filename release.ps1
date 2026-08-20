<#
.SYNOPSIS
    PlanX CartoLab release script — delegates to shared packaging/release.ps1.
    Usage: .\release.ps1 -Version <x.y.z> [-Message "<summary>"] [-DryRun]
#>
param(
    [Parameter(Mandatory = $true)] [string] $Version,
    [string] $Message = "",
    [switch] $DryRun
)

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path -ErrorAction SilentlyContinue }
if (-not $scriptDir) { $scriptDir = Get-Location }
$sharedRelease = Join-Path $scriptDir "..\packaging\release.ps1" -Resolve

$params = @{
    PluginDir = "planx_cartolab"
    Version   = $Version
    Message   = if ($Message) { $Message } else { "Release v$Version" }
}
if ($DryRun) { $params['DryRun'] = $true }

& $sharedRelease @params
