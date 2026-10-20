# Read-only runtime observation for the canonical Sofia Windows service.
# Never starts/stops processes, reads the canonical DB, or changes SCM/registry.
# Does not print process command lines, event messages, private paths or secrets.
[CmdletBinding()]
param(
    [ValidateRange(1,24)][int]$Hours = 2
)

$ErrorActionPreference = 'Stop'
$report = [ordered]@{
    schema = 'sofia.runtime.windows-observation.v1'
    checked_at = (Get-Date).ToUniversalTime().ToString('o')
    service = [ordered]@{
        name = 'SofiaAdaLyra'
        registered = $false
        scm_state = 'unknown'
        wrapper_process_present = $false
        child_count = $null
        child_mode = 'unknown'
        service_account = 'unknown'
    }
    user_interface = [ordered]@{
        session_ui_process_count = $null
        tray_process_count = $null
        desktop_process_count = $null
        detection = 'unknown'
    }
    active_release = [ordered]@{
        state_path_registry_option_read = $false
        canonical_state_file_present = $null
        filesystem_release_pointer_present = $null
        active_release_status = 'unknown_not_reading_database'
        newest_release_stderr_age_minutes = $null
    }
    event_observation = [ordered]@{
        windows_service_errors = $null
        python_service_errors = $null
        messages_redacted = $true
    }
    limits = @(
        'SCM RUNNING means wrapper alive, not proven application readiness.'
        'No child may be normal: bootstrap mode runs inside pythonservice.exe.'
        'The desktop and tray are separate from the headless service.'
        'A release pointer without canonical DB verification is not proof of an active release.'
        'No canonical DB, private chat, log message or service credentials were read.'
        'No process, registry, service, settings or database was modified.'
    )
}

try {
    $svc = Get-CimInstance Win32_Service -Filter "Name='SofiaAdaLyra'" -ErrorAction Stop
    if ($null -ne $svc) {
        $report.service.registered = $true
        $report.service.scm_state = [string]$svc.State
        $report.service.service_account = if ($svc.StartName -eq 'LocalSystem') {
            'LocalSystem'
        } else { 'other_or_unknown' }

        if ($svc.ProcessId -gt 0) {
            $wrapper = Get-CimInstance Win32_Process -Filter "ProcessId=$($svc.ProcessId)" -ErrorAction Stop
            $report.service.wrapper_process_present = ($null -ne $wrapper)
            $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($svc.ProcessId)" -ErrorAction Stop)
            $report.service.child_count = $children.Count
            $report.service.child_mode = if ($children.Count -eq 0) {
                'no_child_bootstrap_or_stopped_application_unverified'
            } else {
                'child_present_requires_readiness_check'
            }
        }
    } else {
        $report.service.scm_state = 'not_installed'
    }
} catch {
    $report.service.scm_state = 'query_failed'
}

try {
    $python = @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.Name -match '(?i)^(python|pythonw|pythonservice)([0-9.]*)\.exe$'
    })
    $observable = @($python | Where-Object { [string]$_.CommandLine -ne '' })
    $ui = @($observable | Where-Object {
        $_.CommandLine -match '(?i)(-m\s+sofia\.ui(?:\s|$)|-m\s+sofia\.ui\.desktop(?:\s|$))'
    })
    $tray = @($observable | Where-Object {
        $_.CommandLine -match '(?i)-m\s+sofia\.ui\.tray_agent(?:\s|$)'
    })
    $report.user_interface.session_ui_process_count = $ui.Count
    $report.user_interface.tray_process_count = $tray.Count
    $report.user_interface.desktop_process_count = $ui.Count
    $report.user_interface.detection = if ($observable.Count -eq 0) {
        'command_line_unavailable_or_no_python_process'
    } else { 'best_effort_command_line_match' }
} catch {
    $report.user_interface.detection = 'process_inspection_unavailable'
}

try {
    # The existing pywin32 GetServiceCustomOption is NOT used here:
    # it requests registry creation rights even for read operations.
    $key = 'Registry::HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\SofiaAdaLyra\Parameters'
    $item = Get-ItemProperty -LiteralPath $key -ErrorAction Stop
    if ($null -ne $item -and [string]$item.StatePath -ne '') {
        $report.active_release.state_path_registry_option_read = $true
        $state = [string]$item.StatePath
        $report.active_release.canonical_state_file_present = [System.IO.File]::Exists($state)
        $parent = Split-Path -Parent $state
        if ($parent -and [System.IO.Directory]::Exists($parent)) {
            $release = Join-Path $parent 'release-runtime'
            $pointer = Join-Path $release 'active-release.json'
            $report.active_release.filesystem_release_pointer_present = [System.IO.File]::Exists($pointer)
            $logs = Join-Path $release 'logs'
            if ([System.IO.Directory]::Exists($logs)) {
                $newest = Get-ChildItem -LiteralPath $logs -Filter '*.stderr.log' -File -ErrorAction Stop |
                    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
                if ($null -ne $newest) {
                    $report.active_release.newest_release_stderr_age_minutes = [math]::Round(
                        ((Get-Date).ToUniversalTime() - $newest.LastWriteTimeUtc).TotalMinutes, 1
                    )
                }
            }
        }
    }
} catch {
    # ACL or missing optional value: never create a registry key.
}

try {
    $start = (Get-Date).AddHours(-$Hours)
    $scm = @(Get-WinEvent -FilterHashtable @{
        LogName = 'System'; ProviderName = 'Service Control Manager'; StartTime = $start
    } -ErrorAction Stop | Where-Object {
        $_.Level -le 2 -and $_.Message -match 'SofiaAdaLyra'
    })
    $report.event_observation.windows_service_errors = $scm.Count
} catch {}

try {
    $start = (Get-Date).AddHours(-$Hours)
    $events = @(Get-WinEvent -FilterHashtable @{
        LogName = 'Application'; StartTime = $start
    } -ErrorAction Stop | Where-Object {
        $_.Level -le 2 -and ($_.ProviderName -match '(?i)python' -or
            $_.ProviderName -match '(?i)Sofia')
    })
    $report.event_observation.python_service_errors = $events.Count
} catch {}

$report | ConvertTo-Json -Depth 5
