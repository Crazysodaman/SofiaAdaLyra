#Requires -Version 5.1
<#
Aegis Platform 1.0 neutral Windows Control Center shell.
Not a service authority, installer, canonical database client, or Sofía Core.
The only file loaded is the reviewed shared UI token manifest. No network
endpoint, service state or write operations are available in this first shell.
#>
[CmdletBinding()]
param([switch]$Check)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ThemePath = Join-Path $PSScriptRoot '..\..\contracts\ui\aegis-theme-v1.json'

function Get-AegisTheme {
    if (-not (Test-Path -LiteralPath $ThemePath -PathType Leaf)) {
        throw 'Aegis theme contract is missing'
    }
    $document = Get-Content -LiteralPath $ThemePath -Encoding UTF8 -Raw |
        ConvertFrom-Json -ErrorAction Stop
    if ($document.schema -ne 'aegis.ui.theme.v1') {
        throw 'Unrecognized Aegis UI theme contract'
    }
    $required = @{
        primary = '#9400D3'
        accent = '#00C2FF'
        tertiary = '#39FF14'
        background = '#000000'
        surface_card = '#0B1020'
        text_main = '#E5E7EB'
        text_muted = '#94A3B8'
        error = '#9F0202'
    }
    foreach ($key in $required.Keys) {
        if ($document.tokens.$key -cne $required[$key]) {
            throw "Aegis theme token mismatch: $key"
        }
    }
    return $document.tokens
}

$Tokens = Get-AegisTheme
if ($Check) {
    # Safe in CI and unattended Windows sessions: does not load WinForms
    # or call a Windows service, registry, owner credential or Core API.
    Write-Output 'AEGIS_GUI=READ_ONLY_SHELL'
    Write-Output 'THEME=aegis.ui.theme.v1'
    Write-Output 'SERVICE=UNAVAILABLE'
    Write-Output 'AUTHENTICATION=NOT_CONNECTED'
    Write-Output 'PRODUCTION_AUTHORIZED=FALSE'
    Write-Output 'ACTIONS=DISABLED'
    Write-Output 'OFFLINE_STALE_RESTART_DENIED=FAIL_CLOSED'
    exit 0
}

if (-not [Environment]::UserInteractive) {
    throw 'Aegis GUI requires an interactive Windows desktop'
}
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Get-AegisColor {
    param([Parameter(Mandatory)][string]$Role)
    if ($Tokens.PSObject.Properties.Name -notcontains $Role) {
        throw 'Unsupported UI color role'
    }
    if ([System.Windows.Forms.SystemInformation]::HighContrast) {
        if ($Role -in @('background', 'surface_card')) {
            return [System.Drawing.SystemColors]::Window
        }
        if ($Role -in @('primary', 'accent', 'tertiary', 'indicator', 'warning', 'error')) {
            return [System.Drawing.SystemColors]::Highlight
        }
        return [System.Drawing.SystemColors]::WindowText
    }
    return [System.Drawing.ColorTranslator]::FromHtml($Tokens.$Role)
}

function New-AegisLabel {
    param(
        [string]$Text, [int]$X, [int]$Y, [int]$W, [int]$H,
        [string]$Color='text_main', [float]$FontSize=10,
        [switch]$Bold
    )
    $label = New-Object System.Windows.Forms.Label
    $label.Location = New-Object System.Drawing.Point($X, $Y)
    $label.Size = New-Object System.Drawing.Size($W, $H)
    $label.Text = $Text
    $label.BackColor = Get-AegisColor 'background'
    $label.ForeColor = Get-AegisColor $Color
    $style = if ($Bold) {
        [System.Drawing.FontStyle]::Bold
    } else {
        [System.Drawing.FontStyle]::Regular
    }
    $label.Font = New-Object System.Drawing.Font('Segoe UI', $FontSize, $style)
    return $label
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Aegis Platform | Control Center'
$form.Size = New-Object System.Drawing.Size(1020, 650)
$form.MinimumSize = New-Object System.Drawing.Size(760, 520)
$form.StartPosition = 'CenterScreen'
$form.BackColor = Get-AegisColor 'background'
$form.ForeColor = Get-AegisColor 'text_main'
$form.Font = New-Object System.Drawing.Font('Segoe UI', 10)
$form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::Dpi
$form.KeyPreview = $true

$sidebar = New-Object System.Windows.Forms.Panel
$sidebar.Dock = [System.Windows.Forms.DockStyle]::Left
$sidebar.Width = 255
$sidebar.BackColor = Get-AegisColor 'surface_card'
$form.Controls.Add($sidebar)

$brand = New-AegisLabel 'AEGIS PLATFORM' 20 22 215 34 'primary' 16 -Bold
$brand.BackColor = Get-AegisColor 'surface_card'
$sidebar.Controls.Add($brand)
$subtitle = New-AegisLabel 'CONTROL CENTER  |  1.0' 20 60 215 26 'accent' 9
$subtitle.BackColor = Get-AegisColor 'surface_card'
$sidebar.Controls.Add($subtitle)

$navigation = New-Object System.Windows.Forms.ListBox
$navigation.Location = New-Object System.Drawing.Point(12, 112)
$navigation.Size = New-Object System.Drawing.Size(230, 375)
$navigation.Anchor = 'Top,Bottom,Left'
$navigation.BackColor = Get-AegisColor 'surface_card'
$navigation.ForeColor = Get-AegisColor 'text_main'
$navigation.BorderStyle = 'None'
$navigation.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$navigation.IntegralHeight = $false
$navigation.ItemHeight = 39
$navigation.SelectionMode = 'One'
@(
    'Platform Overview', 'Core Manager', 'Module Manager',
    'Fleet', 'Settings', 'Security & Approvals',
    'Updates & Recovery', 'Diagnostics'
) | ForEach-Object { [void]$navigation.Items.Add($_) }
$sidebar.Controls.Add($navigation)

$sidebarNote = New-AegisLabel 'Core-free | No private state loaded' 15 525 230 45 'text_muted' 9
$sidebarNote.Anchor = 'Bottom,Left'
$sidebarNote.BackColor = Get-AegisColor 'surface_card'
$sidebar.Controls.Add($sidebarNote)

$content = New-Object System.Windows.Forms.Panel
$content.Dock = [System.Windows.Forms.DockStyle]::Fill
$content.Padding = New-Object System.Windows.Forms.Padding(28)
$content.BackColor = Get-AegisColor 'background'
$form.Controls.Add($content)
# Dock the sidebar ahead of the fill panel so the 255px navigation area is
# reserved instead of being painted over by DockStyle.Fill.
$form.Controls.SetChildIndex($sidebar, 0)
$sidebar.BringToFront()

$heading = New-AegisLabel 'Platform Overview' 28 40 685 50 'primary' 21 -Bold
$heading.Anchor = 'Top,Left,Right'
$content.Controls.Add($heading)
$state = New-AegisLabel 'SERVICE: UNAVAILABLE / SOURCE: UNVERIFIED / PERMISSION: UNKNOWN' 30 110 670 35 'accent' 11 -Bold
$state.Anchor = 'Top,Left,Right'
$content.Controls.Add($state)

$card = New-Object System.Windows.Forms.Panel
$card.Location = New-Object System.Drawing.Point(28, 173)
$card.Size = New-Object System.Drawing.Size(690, 224)
$card.Anchor = 'Top,Left,Right'
$card.BackColor = Get-AegisColor 'surface_card'
$content.Controls.Add($card)

$details = New-AegisLabel (
    'No authenticated Platform management service is connected.' +
    [Environment]::NewLine +
    'Installed Cores, Modules, Fleet, settings, and health are NOT OBSERVED.' +
    [Environment]::NewLine +
    'No state has been read or modified.'
) 18 23 650 178 'text_main' 11
$details.BackColor = Get-AegisColor 'surface_card'
$details.Anchor = 'Top,Left,Right'
$card.Controls.Add($details)

$notice = New-AegisLabel (
    'Read-only shell. Changes, owner approvals, install, repair and uninstall ' +
    'remain disabled until the authenticated management API is implemented.'
) 28 429 675 80 'text_muted' 10
$notice.Anchor = 'Top,Left,Right'
$content.Controls.Add($notice)

# UI-only previews of lifecycle actions. They are deliberately disabled.
# Team A's authenticated Platform management adapter must be connected and
# service-side SAFE/STOP, revocation and permission checks must pass first.
$script:actionsByPage = @{
    'Platform Overview' = @('Refresh Status')
    'Core Manager' = @('Start Core', 'Stop Core', 'Restart Core')
    'Module Manager' = @('Install Module', 'Uninstall Module', 'Reinstall Module')
    'Fleet' = @('Enroll Host', 'Revoke Host')
    'Settings' = @('Save Settings', 'Apply Settings')
    'Security & Approvals' = @('Request Approval', 'Review Requests')
    'Updates & Recovery' = @('Update Platform', 'Repair Platform', 'Rollback')
    'Diagnostics' = @('View Diagnostics')
}
$script:actionButtons = @()
for ($i = 0; $i -lt 3; $i++) {
    $action = New-Object System.Windows.Forms.Button
    $action.Location = New-Object System.Drawing.Point((28 + $i * 218), 514)
    $action.Size = New-Object System.Drawing.Size(205, 36)
    $action.Anchor = 'Bottom,Left'
    $action.FlatStyle = 'Flat'
    $action.BackColor = Get-AegisColor 'surface_card'
    $action.ForeColor = Get-AegisColor 'text_muted'
    $action.Enabled = $false
    $action.TabStop = $false
    $action.AccessibleDescription = 'Disabled: authenticated Platform management unavailable'
    $content.Controls.Add($action)
    $script:actionButtons += $action
}
$script:head = $heading
$script:body = $details
$script:pageName = ''
$navigation.Add_SelectedIndexChanged({
    if ($null -eq $navigation.SelectedItem) { return }
    $script:pageName = [string]$navigation.SelectedItem
    $script:head.Text = $script:pageName
    $kind = switch ($script:pageName) {
        'Settings' {
            'Saved revision: UNKNOWN. Applied revision: UNKNOWN. ' +
            'Stale or changed revisions require review; no edits while offline.'
        }
        'Core Manager' {
            'Installed Cores: NOT OBSERVED. Restart is blocked while offline/stale. ' +
            'No Core is started or removed.'
        }
        'Module Manager' {
            'Installed modules: NOT OBSERVED. Disconnection is not an uninstall. ' +
            'Uninstall requires a service receipt; reinstall requires a new incarnation.'
        }
        'Fleet' {
            'Fleet hosts: NOT OBSERVED. No enrollment or discovery attempted.'
        }
        'Security & Approvals' {
            'SAFE/STOP and owner grants: NOT OBSERVED. Access denied and active STOP ' +
            'block all protected actions. No approvals can be issued.'
        }
        'Updates & Recovery' {
            'Updates and receipts: NOT OBSERVED. Install, repair, rollback and ' +
            'uninstall require verified signed plans and service authority.'
        }
        'Diagnostics' {
            'Service diagnostics: NOT OBSERVED. No logs or protected files opened.'
        }
        default {
            'Platform state: NOT OBSERVED. No authenticated service is connected.'
        }
    }
    $actions = @($script:actionsByPage[$script:pageName])
    for ($i = 0; $i -lt $script:actionButtons.Count; $i++) {
        $visible = $i -lt $actions.Count
        $script:actionButtons[$i].Visible = $visible
        if ($visible) {
            $script:actionButtons[$i].Text = $actions[$i]
            $script:actionButtons[$i].AccessibleName =
                $actions[$i] + ' (unavailable without authenticated Platform)'
        }
    }
    $script:body.Text = 'SOURCE: UNVERIFIED' + [Environment]::NewLine +
        $kind + [Environment]::NewLine +
        'No operation performed.'
})
$navigation.SelectedIndex = 0

$form.Add_Shown({ $form.Activate() })
try {
    [void]$form.ShowDialog()
} finally {
    $form.Dispose()
}
