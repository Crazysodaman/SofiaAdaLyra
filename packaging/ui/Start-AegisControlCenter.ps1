#Requires -Version 5.1
<#
Windows Aegis Platform Control Center, GUI shell (read-only, Core-free).
The service-side authenticated management API is not yet connected.
No elevation, owner approval minting, installer execution, or state DB access.
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$NoColor
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$themePath = Join-Path $root 'contracts\ui\aegis-theme-v1.json'
if (-not (Test-Path -LiteralPath $themePath -PathType Leaf)) {
    throw 'Aegis canonical theme contract is missing.'
}
$themeDocument = Get-Content -LiteralPath $themePath -Encoding UTF8 -Raw |
    ConvertFrom-Json -ErrorAction Stop
if ($themeDocument.schema -ne 'aegis.ui.theme.v1') {
    throw 'Unsupported Aegis theme contract.'
}
$required = @(
    'primary','accent','tertiary','background','surface_card',
    'text_main','text_muted','warning','danger'
)
foreach ($key in $required) {
    $value = [string]($themeDocument.tokens.$key)
    if ($value -cnotmatch '^#[0-9A-F]{6}$') {
        throw "Invalid canonical theme token: $key"
    }
}
if ($Check) {
    Write-Output 'AEGIS_GUI_SCHEMA=aegis.ui.theme.v1'
    Write-Output 'UI_MODE=READ_ONLY'
    Write-Output 'SERVICE_SOURCE=UNVERIFIED'
    Write-Output 'SERVICE_DATA=UNAVAILABLE'
    Write-Output 'MANAGEMENT_TRANSPORT=NOT_CONNECTED'
    Write-Output 'GUI_ACTIONS=NO_MUTATIONS_ENABLED'
    Write-Output 'RESULT=NO_CHANGES_MADE'
    return
}
if (-not [Environment]::OSVersion.Platform.ToString().Equals('Win32NT')) {
    throw 'Native Aegis GUI requires Windows.'
}
Add-Type -AssemblyName PresentationCore,PresentationFramework,WindowsBase

function New-AegisBrush {
    param([string]$Token)
    $hex = [string]($script:themeDocument.tokens.$Token)
    $color = [System.Windows.Media.ColorConverter]::ConvertFromString($hex)
    $brush = New-Object System.Windows.Media.SolidColorBrush($color)
    $brush.Freeze()
    return $brush
}

$bg = New-AegisBrush background
$card = New-AegisBrush surface_card
$purple = New-AegisBrush primary
$cyan = New-AegisBrush accent
$mainText = New-AegisBrush text_main
$mutedText = New-AegisBrush text_muted
$warning = New-AegisBrush warning

$window = New-Object System.Windows.Window
$window.Title = 'Aegis Platform Control Center | Preview'
$window.Width = 1080
$window.Height = 700
$window.MinWidth = 640
$window.MinHeight = 420
$window.WindowStartupLocation = 'CenterScreen'
$window.Background = $bg
$window.Foreground = $mainText

$layout = New-Object System.Windows.Controls.Grid
$layout.Margin = [System.Windows.Thickness]::new(18.0)
$headerRow = New-Object System.Windows.Controls.RowDefinition
$headerRow.Height = [System.Windows.GridLength]::Auto
$bodyRow = New-Object System.Windows.Controls.RowDefinition
$bodyRow.Height = [System.Windows.GridLength]::new(1.0,[System.Windows.GridUnitType]::Star)
[void]$layout.RowDefinitions.Add($headerRow)
[void]$layout.RowDefinitions.Add($bodyRow)

$header = New-Object System.Windows.Controls.StackPanel
$header.Margin = [System.Windows.Thickness]::new(0.0,0.0,0.0,16.0)
$title = New-Object System.Windows.Controls.TextBlock
$title.Text = 'AEGIS PLATFORM'
$title.Foreground = $purple
$title.FontSize = 28
$title.FontWeight = 'Bold'
$subtitle = New-Object System.Windows.Controls.TextBlock
$subtitle.Text = 'CONTROL CENTER 1.0 | PREVIEW ONLY | NO AUTHENTICATED SERVICE'
$subtitle.Foreground = $warning
$subtitle.FontSize = 12
[void]$header.Children.Add($title)
[void]$header.Children.Add($subtitle)
[System.Windows.Controls.Grid]::SetRow($header,0)
[void]$layout.Children.Add($header)

$body = New-Object System.Windows.Controls.Grid
$navCol = New-Object System.Windows.Controls.ColumnDefinition
$navCol.Width = [System.Windows.GridLength]::new(230.0)
$contentCol = New-Object System.Windows.Controls.ColumnDefinition
$contentCol.Width = [System.Windows.GridLength]::new(1.0,[System.Windows.GridUnitType]::Star)
[void]$body.ColumnDefinitions.Add($navCol)
[void]$body.ColumnDefinitions.Add($contentCol)

$navigation = New-Object System.Windows.Controls.StackPanel
$navigation.Background = $card
$navigation.Margin = [System.Windows.Thickness]::new(0.0,0.0,15.0,0.0)

$detail = New-Object System.Windows.Controls.StackPanel
$detail.Margin = [System.Windows.Thickness]::new(18.0)
$pageTitle = New-Object System.Windows.Controls.TextBlock
$pageTitle.Text = 'Platform'
$pageTitle.FontSize = 24
$pageTitle.FontWeight = 'SemiBold'
$pageTitle.Foreground = $cyan
[void]$detail.Children.Add($pageTitle)

foreach ($line in @(
    'Source: UNVERIFIED | Management IPC not connected',
    'Health: UNAVAILABLE | No Core or module state inferred',
    'All install, uninstall, settings writes and approvals are disabled.',
    'This window has no canonical state DB or administrative permissions.'
)) {
    $message = New-Object System.Windows.Controls.TextBlock
    $message.Text = $line
    $message.Margin = [System.Windows.Thickness]::new(0.0,10.0,0.0,0.0)
    $message.TextWrapping = 'Wrap'
    $message.Foreground = $mutedText
    [void]$detail.Children.Add($message)
}

$panel = New-Object System.Windows.Controls.Border
$panel.Background = $card
$panel.Child = $detail
[System.Windows.Controls.Grid]::SetColumn($navigation,0)
[System.Windows.Controls.Grid]::SetColumn($panel,1)
[void]$body.Children.Add($navigation)
[void]$body.Children.Add($panel)

foreach ($page in @(
    'Platform','Core Manager','Module Manager','Settings','Fleet',
    'Security / Approvals','Updates / Recovery','Diagnostics'
)) {
    $button = New-Object System.Windows.Controls.Button
    $button.Content = $page
    $button.Tag = $page
    $button.Margin = [System.Windows.Thickness]::new(6.0)
    $button.Padding = [System.Windows.Thickness]::new(12.0)
    $button.HorizontalContentAlignment = 'Left'
    $button.Foreground = $mainText
    $button.Background = $card
    $button.BorderBrush = $purple
    $button.Cursor = 'Hand'
    $button.Add_Click({
        param($sender, $eventArgs)
        # Navigation only. No privileged operation is attached.
        $script:pageTitle.Text = [string]$sender.Tag
    })
    [void]$navigation.Children.Add($button)
}
[System.Windows.Controls.Grid]::SetRow($body,1)
[void]$layout.Children.Add($body)
$window.Content = $layout
[void]$window.ShowDialog()
