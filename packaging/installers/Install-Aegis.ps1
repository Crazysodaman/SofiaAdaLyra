#Requires -Version 5.1
<#
Aegis Platform installer, UX-1 preflight only.
Never install, elevate, change a service, or infer signed artifact trust.
The release executor and owner approval backend are not connected.
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$NoColor
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$themePath = Join-Path $repoRoot 'contracts\ui\aegis-theme-v1.json'
$useColor = (-not $NoColor) -and (-not (Test-Path Env:NO_COLOR)) -and
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
    Write-Host 'AEGIS PLATFORM INSTALLER PREFLIGHT'
    Write-Host 'MODE=PREVIEW_ONLY'
    Write-Host 'SIGNED_RELEASE=NOT_VERIFIED'
    Write-Host 'SERVICE_STATE=NOT_OBSERVED'
    Write-Host ('OS_PLATFORM=' + [Environment]::OSVersion.Platform)
    Write-Host ('OS_VERSION=' + [Environment]::OSVersion.Version)
    Write-Host ('ARCH_64BIT=' + [Environment]::Is64BitOperatingSystem)
    Write-Host 'INSTALL_AUTHORITY=NOT_CONNECTED'
    Write-Host 'RESULT=NO_CHANGES_MADE'
}

if ($Check) {
    Show-AegisPreflight
    exit 0
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

while ($true) {
    Write-AegisText 'AEGIS PLATFORM | INSTALLATION WIZARD' primary
    Write-AegisText 'PREVIEW ONLY | SIGNED BACKEND NOT CONNECTED' warning
    Write-AegisText '[1] Check prerequisites (read-only)' accent
    Write-AegisText '[2] Install Platform (blocked)' accent
    Write-AegisText '[3] Update / repair / rollback (blocked)' accent
    Write-AegisText '[4] Uninstall Platform (blocked)' accent
    Write-AegisText '[0] Exit' accent
    $choice = Read-Host 'Select [0-4]'
    switch ($choice) {
        '0' { exit 0 }
        '1' { Show-AegisPreflight }
        { $_ -in '2','3','4' } {
            Write-AegisText (
                'BLOCKED: signed release, owner approval and installed ' +
                'service executor not connected.'
            ) warning
        }
        default { Write-Host 'Invalid selection; no operation performed.' }
    }
}
