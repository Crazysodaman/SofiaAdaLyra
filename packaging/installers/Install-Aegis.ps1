#Requires -Version 5.1
<#
Aegis Platform installer, UX-1 preflight only.
Never install, elevate, change a service, or infer signed artifact trust.
The release executor and owner approval backend are not connected.
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$NoColor,
    [switch]$LineMode,
    [switch]$Json,
    [switch]$DryRun,
    [ValidateSet('status','doctor','install','update','repair','rollback','uninstall','purge')]
    [string]$Operation
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'contracts\ui\aegis-theme-v1.json') -PathType Leaf)) {
    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}
$themePath = Join-Path $repoRoot 'contracts\ui\aegis-theme-v1.json'
$useColor = (-not $NoColor) -and (-not $LineMode) -and (-not $Json) -and (-not (Test-Path Env:NO_COLOR)) -and
    ($Host.Name -eq 'ConsoleHost')
$theme = $null
if (Test-Path -LiteralPath $themePath -PathType Leaf) {
    try {
        $document = Get-Content -LiteralPath $themePath -Encoding UTF8 -Raw |
            ConvertFrom-Json -ErrorAction Stop
        if ($document.schema -eq 'aegis.ui.theme.v1') {
            $theme = $document.tokens
        }
    } catch {
        $theme = $null
    }
}

function Write-AegisText {
    param(
        [string]$Value,
        [ValidateSet('primary','accent','success','warning','text_main')]
        [string]$Role = 'text_main'
    )
    if (-not $script:useColor -or $null -eq $script:theme) {
        Write-Host $Value
        return
    }
    # Windows PowerShell 5.1 consoles expose 16 colors, not truecolor.
    # This is a contrast-safe terminal fallback for the verified hex roles.
    $expected = @{
        primary = '#9400D3'
        accent = '#00C2FF'
        success = '#39FF14'
        warning = '#FFB000'
        text_main = '#E5E7EB'
    }
    $fallback = @{
        primary = 'Magenta'
        accent = 'Cyan'
        success = 'Green'
        warning = 'Yellow'
        text_main = 'Gray'
    }
    if ($script:theme.$Role -eq $expected[$Role]) {
        Write-Host $Value -ForegroundColor $fallback[$Role]
    } else {
        Write-Host $Value
    }
}

function Show-AegisPreflight {
    Write-Output 'AEGIS PLATFORM INSTALLER PREFLIGHT'
    Write-Output 'MODE=PREVIEW_ONLY'
    if ($Operation) { Write-Output ('REQUESTED_OPERATION=' + $Operation) }
    else { Write-Output 'REQUESTED_OPERATION=none' }
    Write-Output 'SIGNED_RELEASE=NOT_VERIFIED'
    Write-Output 'SERVICE_STATE=NOT_OBSERVED'
    Write-Output ('OS_PLATFORM=' + [Environment]::OSVersion.Platform)
    Write-Output ('OS_VERSION=' + [Environment]::OSVersion.Version)
    Write-Output ('ARCH_64BIT=' + [Environment]::Is64BitOperatingSystem)
    Write-Output 'INSTALL_AUTHORITY=NOT_CONNECTED'
    Write-Output 'CORE_ACTIVATED=FALSE'
    Write-Output 'RESULT=NO_CHANGES_MADE'
}

function Write-AegisResult {
    param([ValidateSet('BLOCKED','NO_CHANGES_MADE')][string]$Result)
    $requested = 'none'
    if ($Operation) { $requested = $Operation }
    if ($Json) {
        $record = [ordered]@{
            schema = 'aegis.installer.preflight.v1'
            mode = 'PREVIEW_ONLY'
            operation = $requested
            signed_release = 'NOT_VERIFIED'
            service_state = 'NOT_OBSERVED'
            authority = 'NOT_CONNECTED'
            executed = $false
            owner_approved = $false
            core_activated = $false
            result = $Result
        }
        Write-Output (ConvertTo-Json -InputObject $record -Compress)
        return
    }
    if ($Result -eq 'NO_CHANGES_MADE') {
        Show-AegisPreflight
        return
    }
    Write-Output 'MODE=PREVIEW_ONLY'
    Write-Output ('REQUESTED_OPERATION=' + $requested)
    Write-Output 'SIGNED_RELEASE=NOT_VERIFIED'
    Write-Output 'INSTALL_AUTHORITY=NOT_CONNECTED'
    Write-Output 'RESULT=BLOCKED'
    Write-Output 'BLOCKED: signed OS executor and current SAFE/STOP owner approval not connected.'
}

if ($Check) {
    Write-AegisResult NO_CHANGES_MADE
    exit 0
}
if ($Operation) {
    if ($Operation -in @('status','doctor')) {
        Write-AegisResult NO_CHANGES_MADE
        exit 0
    }
    Write-AegisResult BLOCKED
    exit 3
}
if ($Json -or $DryRun) {
    [Console]::Error.WriteLine('-Json and -DryRun require -Check or -Operation.')
    exit 2
}

try {
    if ([Console]::IsInputRedirected -or [Console]::IsOutputRedirected) {
        [Console]::Error.WriteLine(
            'Interactive installer requires a console; use -Check for preflight.'
        )
        exit 2
    }
} catch {
    [Console]::Error.WriteLine(
        'No interactive console available; use -Check for preflight.'
    )
    exit 2
}

$narrow = $false
try { $narrow = ([Console]::WindowWidth -lt 64) } catch { $narrow = $false }
while ($true) {
    if ($narrow) {
        Write-AegisText 'AEGIS PLATFORM INSTALLER' primary
        Write-AegisText 'PREVIEW ONLY / NO INSTALL AUTHORITY' warning
    } else {
        Write-AegisText '+------------------------------------------------------------+' primary
        Write-AegisText '|                 AEGIS PLATFORM INSTALLER                   |' primary
        Write-AegisText '|           PREVIEW ONLY / NO INSTALL AUTHORITY              |' warning
        Write-AegisText '+------------------------------------------------------------+' primary
    }
    Write-AegisText '[1] Install Platform (blocked)' accent
    Write-AegisText '[2] Update Platform (blocked)' accent
    Write-AegisText '[3] Repair Platform (blocked)' accent
    Write-AegisText '[4] Uninstall Platform (blocked)' accent
    Write-AegisText '[5] Diagnostics (read-only)' accent
    Write-AegisText '[6] Rollback (blocked)' accent
    Write-AegisText '[7] Status (unverified)' accent
    Write-AegisText '[0] Exit' accent
    Write-Host '[?] Help | [B] Back | [C] Cancel'
    $choice = Read-Host 'Select [0-7]'
    switch ($choice) {
        { $_ -in '0','B','b','C','c' } { exit 0 }
        { $_ -in '5','7' } { Show-AegisPreflight; break }
        { $_ -in '1','2','3','4','6' } {
            Write-AegisText 'BLOCKED: signed release, native executor and SAFE/STOP approval not connected.' warning
            break
        }
        '?' {
            Write-Host 'Choose 5 or 7 for read-only checks. Lifecycle changes require a certified signed installer.'
            break
        }
        default { Write-Host 'Invalid selection; no operation performed.' }
    }
}
