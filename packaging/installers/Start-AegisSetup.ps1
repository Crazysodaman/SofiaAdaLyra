#Requires -Version 5.1
<#
PowerShell fallback launcher for Aegis setup media.

This is the documented equivalent when the OS C# compiler is unavailable and
Aegis-Setup.exe cannot be built. It locates the adjacent signed release bundle
and invokes Install-Aegis.ps1 with the approved UAC elevation mechanism. It does
not accept a manual hash, approval id, Python path or service command, and it
does not disable execution policy or anti-malware.
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$Json,
    [switch]$NoColor,
    [ValidateSet('verify','status','doctor','install','update','repair','rollback','uninstall','reinstall','reconcile','purge')]
    [string]$Operation,
    [string]$BundleRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Find-AegisInstaller {
    param([string]$BaseDirectory)
    $parent = [IO.Directory]::GetParent($BaseDirectory)
    $parentPath = if ($null -eq $parent) { $BaseDirectory } else { $parent.FullName }
    $candidates = @(
        (Join-Path $BaseDirectory 'Install-Aegis.ps1'),
        (Join-Path $BaseDirectory 'installer\Install-Aegis.ps1'),
        (Join-Path $parentPath 'Install-Aegis.ps1')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}

function Find-AegisBundle {
    param([string]$BaseDirectory)
    $parent = [IO.Directory]::GetParent($BaseDirectory)
    $parentPath = if ($null -eq $parent) { $BaseDirectory } else { $parent.FullName }
    $candidates = @(
        $BaseDirectory,
        $parentPath,
        (Join-Path $BaseDirectory 'release'),
        (Join-Path $BaseDirectory 'bundle'),
        (Join-Path $parentPath 'release'),
        (Join-Path $parentPath 'bundle')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath (Join-Path $candidate 'release-manifest.json') -PathType Leaf) {
            return [IO.Path]::GetFullPath($candidate)
        }
    }
    return $null
}

function Quote-AegisArgument {
    param([string]$Value)
    if ($Value -match '["\r\n]') { throw 'Unsupported installer path or argument.' }
    return '"' + $Value + '"'
}

$baseDirectory = $PSScriptRoot
$installer = Find-AegisInstaller -BaseDirectory $baseDirectory
if ($null -eq $installer) {
    [Console]::Error.WriteLine(
        'Aegis setup media is incomplete: Install-Aegis.ps1 was not found. ' +
        'Use the complete signed setup media.')
    exit 2
}
$resolvedBundle = $BundleRoot
if ([string]::IsNullOrWhiteSpace($resolvedBundle)) {
    $resolvedBundle = Find-AegisBundle -BaseDirectory $baseDirectory
}
if ([string]::IsNullOrWhiteSpace($resolvedBundle)) {
    [Console]::Error.WriteLine(
        'Aegis setup media is incomplete: release-manifest.json was not found. ' +
        'Use the complete signed setup media.')
    exit 2
}

$parts = New-Object 'System.Collections.Generic.List[string]'
$parts.Add('-NoProfile')
$parts.Add('-File')
$parts.Add((Quote-AegisArgument -Value $installer))
$parts.Add('-BundleRoot')
$parts.Add((Quote-AegisArgument -Value $resolvedBundle))
if ($Operation) {
    $parts.Add('-Operation')
    $parts.Add($Operation)
}
if ($Check) { $parts.Add('-Check') }
if ($Json) { $parts.Add('-Json') }
if ($NoColor) { $parts.Add('-NoColor') }
$argumentLine = $parts -join ' '

$hostPath = $null
try { $hostPath = (Get-Process -Id $PID).Path } catch { $hostPath = $null }
if ([string]::IsNullOrWhiteSpace($hostPath)) {
    $candidate = Join-Path $PSHOME 'powershell.exe'
    if (Test-Path -LiteralPath $candidate -PathType Leaf) { $hostPath = $candidate }
}
if ([string]::IsNullOrWhiteSpace($hostPath)) {
    [Console]::Error.WriteLine('Unable to locate the current PowerShell host for setup.')
    exit 2
}

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$elevated = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

try {
    if ($elevated) {
        $direct = @('-NoProfile', '-File', $installer, '-BundleRoot', $resolvedBundle)
        if ($Operation) { $direct += @('-Operation', $Operation) }
        if ($Check) { $direct += '-Check' }
        if ($Json) { $direct += '-Json' }
        if ($NoColor) { $direct += '-NoColor' }
        & $hostPath @direct
        if (Test-Path Variable:LASTEXITCODE) { exit $LASTEXITCODE }
        exit 0
    }
    $process = Start-Process -FilePath $hostPath -Verb RunAs -ArgumentList $argumentLine `
        -Wait -PassThru -ErrorAction Stop
    if ($null -eq $process) {
        [Console]::Error.WriteLine('Windows did not start the elevated Aegis installer.')
        exit 2
    }
    exit $process.ExitCode
} catch {
    [Console]::Error.WriteLine(
        'Administrator approval was not granted or the elevated installer could not start. ' +
        'Approve the Windows UAC prompt and run setup again.')
    exit 2
}
