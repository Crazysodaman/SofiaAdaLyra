#Requires -Version 5.1
<#
Aegis native Windows GUI shell, UX-1. Safe read-only preview.
No Platform process invocation, approval, settings write, or host state access.
Launch from a Windows PowerShell 5.1 STA console. -Check never opens a window.
#>
[CmdletBinding()]
param([switch]$Check)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$themePath = Join-Path $root 'contracts\ui\aegis-theme-v1.json'
if (-not (Test-Path -LiteralPath $themePath -PathType Leaf)) {
    throw 'Aegis shared theme manifest missing'
}
$theme = Get-Content -LiteralPath $themePath -Encoding UTF8 -Raw |
    ConvertFrom-Json -ErrorAction Stop
if ($theme.schema -ne 'aegis.ui.theme.v1') {
    throw 'Unsupported Aegis theme schema'
}
$expected = @{
    primary = '#9400D3'
    accent = '#00C2FF'
    tertiary = '#39FF14'
    background = '#000000'
    surface_card = '#0B1020'
    text_main = '#E5E7EB'
    text_muted = '#94A3B8'
    warning = '#FFB000'
}
foreach ($role in @($expected.Keys)) {
    if ($theme.tokens.$role -ne $expected[$role]) {
        throw ('Aegis shared theme role mismatch: ' + $role)
    }
}
if ($Check) {
    Write-Output 'AEGIS_GUI_PREFLIGHT=PASS'
    Write-Output 'THEME=aegis.ui.theme.v1'
    Write-Output 'STATUS=UNVERIFIED'
    Write-Output 'HOST_OPERATIONS=DISABLED'
    Write-Output 'STATE_WRITES=NONE'
    exit 0
}
if (-not $IsWindows -and $PSVersionTable.PSVersion.Major -ge 6) {
    throw 'Aegis WinForms control center supports Windows only'
}
if ([Threading.Thread]::CurrentThread.GetApartmentState() -ne 'STA') {
    throw 'Launch in STA: powershell.exe -STA -NoProfile -File Start-AegisControlCenter.ps1'
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

function Color-ForRole {
    param([ValidateSet('primary','accent','tertiary','background','surface_card',
        'text_main','text_muted','warning')][string]$Role)
    return [System.Drawing.ColorTranslator]::FromHtml($expected[$Role])
}
function Label-ForAegis {
    param([string]$Text,[int]$X,[int]$Y,[int]$Width=520,
        [int]$Height=30,[int]$Size=11,[string]$ColorRole='text_main')
    $control = New-Object System.Windows.Forms.Label
    $control.Text = $Text
    $control.Location = New-Object System.Drawing.Point($X, $Y)
    $control.Size = New-Object System.Drawing.Size($Width, $Height)
    $control.ForeColor = Color-ForRole $ColorRole
    $control.Font = New-Object System.Drawing.Font('Segoe UI', $Size)
    $control.AutoEllipsis = $true
    return $control
}

$window = New-Object System.Windows.Forms.Form
$window.Text = 'Aegis Platform Control Center | Preview'
$window.StartPosition = 'CenterScreen'
$window.ClientSize = New-Object System.Drawing.Size(860, 560)
$window.MinimumSize = New-Object System.Drawing.Size(720, 470)
$window.BackColor = Color-ForRole background
$window.ForeColor = Color-ForRole text_main
$window.KeyPreview = $true
$window.AccessibleName = 'Aegis Platform Control Center preview'
$window.Add_KeyDown({
    if ($_.KeyCode -eq [System.Windows.Forms.Keys]::Escape) {
        $window.Close()
    }
})

$header = Label-ForAegis -Text 'AEGIS PLATFORM' -X 24 -Y 18 -Width 500 -Height 40 -Size 19 -ColorRole primary
$window.Controls.Add($header)
$status = Label-ForAegis -Text 'OFFLINE | Management service not connected' -X 24 -Y 64 -Width 785 -Height 30 -ColorRole warning
$window.Controls.Add($status)

$sidebar = New-Object System.Windows.Forms.Panel
$sidebar.Location = New-Object System.Drawing.Point(24, 110)
$sidebar.Size = New-Object System.Drawing.Size(222, 410)
$sidebar.Anchor = 'Top,Bottom,Left'
$sidebar.BackColor = Color-ForRole surface_card
$window.Controls.Add($sidebar)

$content = New-Object System.Windows.Forms.Panel
$content.Location = New-Object System.Drawing.Point(266, 110)
$content.Size = New-Object System.Drawing.Size(570, 410)
$content.Anchor = 'Top,Bottom,Left,Right'
$content.BackColor = Color-ForRole surface_card
$window.Controls.Add($content)

$title = Label-ForAegis -Text 'Platform' -X 20 -Y 20 -Width 505 -Height 40 -Size 17 -ColorRole accent
$title.Anchor = 'Top,Left,Right'
$content.Controls.Add($title)
$source = Label-ForAegis -Text 'SOURCE: UNVERIFIED' -X 20 -Y 72 -Width 505 -Height 32 -ColorRole warning
$content.Controls.Add($source)
$description = Label-ForAegis -Text 'No authenticated Platform session. Live values are unavailable.' -X 20 -Y 116 -Width 515 -Height 70 -Size 11
$description.Anchor = 'Top,Left,Right'
$content.Controls.Add($description)
$notice = Label-ForAegis -Text 'No actions are enabled. No protected state is accessed.' -X 20 -Y 240 -Width 515 -Height 72 -Size 10 -ColorRole text_muted
$content.Controls.Add($notice)

$pages = @(
    @{ Label = 'Platform'; Text = 'Service status, identity and health will come from authenticated Platform IPC.' },
    @{ Label = 'Core Manager'; Text = 'Core install, lifecycle and removal require signed receipts and owner authorization.' },
    @{ Label = 'Module Manager'; Text = 'Installed modules, connection health and settings require live verified observation.' },
    @{ Label = 'Settings'; Text = 'Saved/applied settings and revisions will be read from the Platform-owned API.' },
    @{ Label = 'Security / Approvals'; Text = 'Approvals, STOP and enrollment are enforced by the running Platform, not this window.' },
    @{ Label = 'Updates / Recovery'; Text = 'Signed update, repair and rollback require installed-host authority and receipts.' },
    @{ Label = 'Diagnostics'; Text = 'Logs and service health are unavailable until a verified local session exists.' }
)
$top = 12
foreach ($page in $pages) {
    $button = New-Object System.Windows.Forms.Button
    $button.Text = $page.Label
    $button.AccessibleName = $page.Label + ' page'
    $button.Location = New-Object System.Drawing.Point(10, $top)
    $button.Size = New-Object System.Drawing.Size(202, 47)
    $button.FlatStyle = 'Flat'
    $button.FlatAppearance.BorderSize = 0
    $button.ForeColor = Color-ForRole text_main
    $button.BackColor = Color-ForRole surface_card
    $button.Font = New-Object System.Drawing.Font('Segoe UI', 10)
    $button.Tag = $page
    $button.Add_Click({
        $selected = $this.Tag
        $title.Text = $selected.Label
        $description.Text = $selected.Text
    })
    $sidebar.Controls.Add($button)
    $top += 54
}
[void]$window.ShowDialog()
$window.Dispose()
