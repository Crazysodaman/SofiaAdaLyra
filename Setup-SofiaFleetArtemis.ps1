[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Prepare", "Artemis", "Verify")]
    [string]$Phase,

    [string]$RepoRoot = (Get-Location).Path,
    [string]$ArtemisHost = "Artemis",
    [string]$ArtemisIp = "192.168.1.55",
    [int]$Port = 7443,

    [string]$FleetRoot = (Join-Path $env:LOCALAPPDATA "SofiaAdaLyra\FleetPKI\artemis-v1"),
    [string]$RemoteRoot = "C:\ProgramData\SofiaAdaLyra\FleetCanary",

    [switch]$SkipCopy
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Text)
    Write-Host ""
    Write-Host "=== $Text ===" -ForegroundColor Cyan
}

function Assert-Repo {
    if (-not (Test-Path (Join-Path $RepoRoot "pyproject.toml") -PathType Leaf)) {
        throw "RepoRoot does not look like SofiaAdaLyra: $RepoRoot"
    }
    if (-not (Test-Path (Join-Path $RepoRoot "src\sofia") -PathType Container)) {
        throw "RepoRoot is missing src\sofia: $RepoRoot"
    }
}

function Invoke-PythonCapture {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    $output = & python @Arguments 2>&1
    $code = $LASTEXITCODE
    $text = ($output | Out-String).Trim()

    if ($code -ne 0) {
        throw "Python command failed (exit $code): python $($Arguments -join ' ')`n$text"
    }

    return $text
}

function Get-Fingerprint {
    param([string]$CertificatePath)

    $value = Invoke-PythonCapture -Arguments @(
        "-m", "sofia.distributed.pki",
        "fingerprint",
        $CertificatePath
    )

    $value = $value.Trim().ToLowerInvariant()
    if ($value -notmatch '^[0-9a-f]{64}$') {
        throw "Unexpected certificate fingerprint output: $value"
    }
    return $value
}

function Get-OrCreateNodeId {
    param([string]$Root)

    $path = Join-Path $Root "artemis-node-id.txt"
    if (Test-Path $path -PathType Leaf) {
        $value = (Get-Content $path -Raw).Trim()
        try { [void][guid]$value }
        catch { throw "Existing Artemis node ID is not a valid UUID: $value" }
        return $value
    }

    $value = [guid]::NewGuid().ToString()
    Set-Content -Path $path -Value $value -Encoding ASCII
    return $value
}

function Assert-PkiComplete {
    param([string]$Root)

    $required = @(
        "ca\fleet-ca.pem",
        "ca\fleet-ca-key.pem",
        "venus\venus-client.pem",
        "venus\venus-client-key.pem",
        "artemis\artemis-server.pem",
        "artemis\artemis-server-key.pem"
    )

    $missing = @()
    foreach ($relative in $required) {
        if (-not (Test-Path (Join-Path $Root $relative) -PathType Leaf)) {
            $missing += $relative
        }
    }

    if ($missing.Count -gt 0) {
        throw @"
Fleet PKI directory exists but is incomplete.
Refusing to overwrite or silently rotate keys.

Root:
  $Root

Missing:
  $($missing -join "`n  ")
"@
    }
}

function Prepare-OnVenus {
    Assert-Repo
    Set-Location $RepoRoot

    Write-Step "Repository"
    $hash = (& git rev-parse --short HEAD 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "git rev-parse failed: $hash" }
    Write-Host "Repo: $RepoRoot"
    Write-Host "HEAD: $hash"

    Write-Step "Fleet PKI"
    if (-not (Test-Path $FleetRoot)) {
        Write-Host "Creating new Fleet PKI at:"
        Write-Host "  $FleetRoot"

        & python -m sofia.distributed.pki bootstrap-pair `
            --output-dir "$FleetRoot" `
            --server-name "$ArtemisHost" `
            --server-dns "$ArtemisHost" `
            --server-dns "$ArtemisHost.local" `
            --server-ip "$ArtemisIp" `
            --controller-name "Venus"

        if ($LASTEXITCODE -ne 0) {
            throw "Fleet PKI provisioning failed."
        }
    }
    else {
        Write-Host "Existing Fleet PKI found. Reusing it without rotating keys."
        Assert-PkiComplete -Root $FleetRoot
    }

    Assert-PkiComplete -Root $FleetRoot

    $nodeId = Get-OrCreateNodeId -Root $FleetRoot
    $venusPin = Get-Fingerprint (Join-Path $FleetRoot "venus\venus-client.pem")
    $serverPin = Get-Fingerprint (Join-Path $FleetRoot "artemis\artemis-server.pem")

    Write-Host "Artemis node ID : $nodeId"
    Write-Host "Venus cert pin  : $venusPin"
    Write-Host "Artemis cert pin: $serverPin"

    Write-Step "Build Artemis agent bundle"
    $bundle = Join-Path $FleetRoot "bundle"
    New-Item -ItemType Directory -Force (Join-Path $bundle "certs") | Out-Null
    New-Item -ItemType Directory -Force (Join-Path $bundle "state") | Out-Null

    Copy-Item (Join-Path $FleetRoot "ca\fleet-ca.pem") `
        (Join-Path $bundle "certs\fleet-ca.pem") -Force
    Copy-Item (Join-Path $FleetRoot "artemis\artemis-server.pem") `
        (Join-Path $bundle "certs\artemis-server.pem") -Force
    Copy-Item (Join-Path $FleetRoot "artemis\artemis-server-key.pem") `
        (Join-Path $bundle "certs\artemis-server-key.pem") -Force

    $agentConfig = [ordered]@{
        node_id                           = $nodeId
        node_name                         = $ArtemisHost
        listen_host                       = "0.0.0.0"
        listen_port                       = $Port
        server_certificate                = "certs/artemis-server.pem"
        server_private_key                = "certs/artemis-server-key.pem"
        client_ca_file                    = "certs/fleet-ca.pem"
        expected_client_public_key_sha256 = $venusPin
        ledger_path                       = "state/agent-ledger.db"
        protocol_version                  = "1.0"
    }

    $agentConfig |
        ConvertTo-Json -Depth 5 |
        Set-Content (Join-Path $bundle "agent.json") -Encoding UTF8

    Write-Step "Validate Artemis configuration"
    & python -m sofia.distributed.agent_main `
        --config (Join-Path $bundle "agent.json") `
        --check-config

    if ($LASTEXITCODE -ne 0) {
        throw "Fleet agent configuration validation failed."
    }

    Write-Step "Ensure pinned wheel-build backend"
    & python -m pip install --disable-pip-version-check "setuptools==80.9.0"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install pinned setuptools build backend."
    }

    Write-Step "Build Fleet wheel from clean committed snapshot"
    $wheelDir = Join-Path $FleetRoot "wheel"
    New-Item -ItemType Directory -Force $wheelDir | Out-Null

    # Build from a clean git archive instead of the live repo tree. This avoids
    # stale/locked build artifacts on Windows and guarantees the wheel matches HEAD.
    $snapshotRoot = Join-Path $env:TEMP ("sofia-fleet-build-" + [guid]::NewGuid().ToString("N"))
    $snapshotZip = Join-Path $snapshotRoot "sofia-head.zip"
    New-Item -ItemType Directory -Force $snapshotRoot | Out-Null

    try {
        & git archive --format=zip --output="$snapshotZip" HEAD
        if ($LASTEXITCODE -ne 0) {
            throw "git archive failed."
        }

        # Remove any older wheel for this package so selection cannot pick stale output.
        Get-ChildItem "$wheelDir\sofia_ada_lyra-*.whl" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue

        & python -m pip wheel "$snapshotZip" `
            --no-deps `
            --no-build-isolation `
            --wheel-dir "$wheelDir"

        if ($LASTEXITCODE -ne 0) {
            throw "Wheel build failed."
        }
    }
    finally {
        Remove-Item -Recurse -Force $snapshotRoot -ErrorAction SilentlyContinue
    }

    $wheel = Get-ChildItem "$wheelDir\sofia_ada_lyra-*.whl" |
        Sort-Object LastWriteTime |
        Select-Object -Last 1

    if ($null -eq $wheel) {
        throw "No Fleet wheel was produced in $wheelDir"
    }

    $wheelHash = (Get-FileHash $wheel.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Host "Wheel: $($wheel.FullName)"
    Write-Host "SHA256: $wheelHash"

    if ($SkipCopy) {
        Write-Host ""
        Write-Host "Preparation complete. -SkipCopy was specified, so Artemis was not modified."
        return
    }

    Write-Step "Copy canary package to Artemis"
    if ($RemoteRoot -notmatch '^[A-Za-z]:\\') {
        throw "RemoteRoot must be an absolute Windows path such as C:\ProgramData\..."
    }

    $driveLetter = $RemoteRoot.Substring(0,1)
    $relativeRemote = $RemoteRoot.Substring(3)
    $shareRoot = "\\$ArtemisHost\$driveLetter`$"
    $shareRootByIp = "\\$ArtemisIp\$driveLetter`$"
    $psDriveName = "SOFIAFLEET"

    if (Get-PSDrive -Name $psDriveName -ErrorAction SilentlyContinue) {
        Remove-PSDrive -Name $psDriveName -Force
    }

    # Reuse the existing Artemis SMB credential context first. This is important
    # because Venus may already have persistent H:/M:/X: mappings to \\Artemis.
    $mapped = $false

    try {
        New-PSDrive `
            -Name $psDriveName `
            -PSProvider FileSystem `
            -Root $shareRoot `
            -Scope Script `
            -ErrorAction Stop | Out-Null

        # Prove write access, not merely mapping access.
        $probeDir = "$psDriveName`:\ProgramData\SofiaAdaLyraWriteProbe"
        try {
            New-Item -ItemType Directory -Force $probeDir -ErrorAction Stop | Out-Null
            Remove-Item $probeDir -Force -ErrorAction SilentlyContinue
            $mapped = $true
            Write-Host "Reusing current/default SMB credentials for $ArtemisHost."
        }
        catch {
            throw "Existing Artemis SMB session is not writable under C:\ProgramData."
        }
    }
    catch {
        Remove-PSDrive -Name $psDriveName -Force -ErrorAction SilentlyContinue

        Write-Host ""
        Write-Host "Existing Artemis SMB credentials cannot write to C:\ProgramData."
        Write-Host "Preserving H:, M:, and X: and retrying through $shareRootByIp."
        Write-Host ""

        $credential = Get-Credential -Message "Administrator credentials for $ArtemisHost"

        New-PSDrive `
            -Name $psDriveName `
            -PSProvider FileSystem `
            -Root $shareRootByIp `
            -Credential $credential `
            -Scope Script `
            -ErrorAction Stop | Out-Null

        $probeDir = "$psDriveName`:\ProgramData\SofiaAdaLyraWriteProbe"
        New-Item -ItemType Directory -Force $probeDir -ErrorAction Stop | Out-Null
        Remove-Item $probeDir -Force -ErrorAction SilentlyContinue

        $mapped = $true
        Write-Host "Connected with writable administrator access through $ArtemisIp."
    }

    try {
        if (-not $mapped) {
            throw "Failed to create writable Artemis SMB mapping."
        }

        $remoteCanary = "$psDriveName`:\$relativeRemote"
        New-Item -ItemType Directory -Force $remoteCanary | Out-Null


        Copy-Item (Join-Path $bundle "*") $remoteCanary -Recurse -Force
        Copy-Item $wheel.FullName $remoteCanary -Force

        if ($PSCommandPath -and (Test-Path $PSCommandPath -PathType Leaf)) {
            Copy-Item $PSCommandPath `
                (Join-Path $remoteCanary "Setup-SofiaFleetArtemis.ps1") `
                -Force
        }

        Write-Host "Copied bundle to ${ArtemisHost}:$RemoteRoot"
    }
    finally {
        Remove-PSDrive -Name $psDriveName -Force -ErrorAction SilentlyContinue
    }

    Write-Host ""
    Write-Host "VENUS PREP COMPLETE" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next, open Administrator PowerShell on Artemis and run:"
    Write-Host ""
    Write-Host "  Set-ExecutionPolicy -Scope Process Bypass"
    Write-Host "  & '$RemoteRoot\Setup-SofiaFleetArtemis.ps1' -Phase Artemis -ArtemisHost '$ArtemisHost'"
    Write-Host ""
    Write-Host "Leave that window open when the foreground Fleet agent starts."
}

function Start-OnArtemis {
    if ($env:COMPUTERNAME -ine $ArtemisHost) {
        throw "This phase must run on $ArtemisHost. Current computer: $env:COMPUTERNAME"
    }

    if (-not (Test-Path $RemoteRoot -PathType Container)) {
        throw "Canary directory not found: $RemoteRoot"
    }

    $agentJson = Join-Path $RemoteRoot "agent.json"
    if (-not (Test-Path $agentJson -PathType Leaf)) {
        throw "agent.json not found: $agentJson"
    }

    $wheel = Get-ChildItem "$RemoteRoot\*.whl" |
        Sort-Object LastWriteTime |
        Select-Object -Last 1

    if ($null -eq $wheel) {
        throw "No Sofía wheel found in $RemoteRoot"
    }

    Write-Step "Artemis Python"
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -eq $python) {
        throw "python.exe was not found on Artemis."
    }
    & $python.Source --version

    Write-Step "Create isolated canary environment"
    $venv = Join-Path $RemoteRoot ".venv"
    $agentPython = Join-Path $venv "Scripts\python.exe"

    if (-not (Test-Path $agentPython -PathType Leaf)) {
        & $python.Source -m venv $venv
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create Artemis Fleet venv."
        }
    }
    else {
        Write-Host "Existing canary venv found. Reusing it."
    }

    Write-Step "Install Fleet package"
    & $agentPython -m pip install --disable-pip-version-check --no-deps --force-reinstall $wheel.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Fleet package installation failed."
    }

    & $agentPython -m pip install --disable-pip-version-check cryptography pywin32
    if ($LASTEXITCODE -ne 0) {
        throw "Fleet dependencies installation failed."
    }

    Write-Step "Validate copied agent configuration"
    & $agentPython -m sofia.distributed.agent_main `
        --config $agentJson `
        --check-config

    if ($LASTEXITCODE -ne 0) {
        throw "Artemis agent configuration validation failed."
    }

    Write-Step "Open temporary LocalSubnet firewall rule"
    $firewallName = "SofiaAdaLyra Fleet Canary $Port"

    Get-NetFirewallRule -DisplayName $firewallName -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule -ErrorAction SilentlyContinue

    New-NetFirewallRule `
        -DisplayName $firewallName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $Port `
        -RemoteAddress LocalSubnet `
        -Profile Any | Out-Null

    Write-Host "Temporary rule created: $firewallName"

    Write-Step "Start foreground Fleet agent"
    Write-Host "The console will stay occupied while the agent is running."
    Write-Host "Leave this window open and return to Venus for the Verify phase."
    Write-Host "Press Ctrl+C when we are finished with the foreground canary."
    Write-Host ""

    & $agentPython -m sofia.distributed.agent_main --config $agentJson
}

function Verify-FromVenus {
    Assert-Repo
    Set-Location $RepoRoot

    Write-Step "Load expected Artemis identity"
    Assert-PkiComplete -Root $FleetRoot

    $nodeIdPath = Join-Path $FleetRoot "artemis-node-id.txt"
    if (-not (Test-Path $nodeIdPath -PathType Leaf)) {
        throw "Artemis node ID file is missing: $nodeIdPath"
    }

    $nodeId = (Get-Content $nodeIdPath -Raw).Trim()
    $serverPin = Get-Fingerprint (Join-Path $FleetRoot "artemis\artemis-server.pem")

    Write-Host "Expected node ID : $nodeId"
    Write-Host "Expected cert pin: $serverPin"

    Write-Step "TCP check"
    $tcp = Test-NetConnection $ArtemisHost -Port $Port -WarningAction SilentlyContinue
    Write-Host "Remote address   : $($tcp.RemoteAddress)"
    Write-Host "TCP $Port open     : $($tcp.TcpTestSucceeded)"

    if (-not $tcp.TcpTestSucceeded) {
        throw "Artemis is not reachable on TCP $Port. Keep the Artemis foreground agent running and check its console."
    }

    Write-Step "Read-only pinned-mTLS discovery canary"
    & python -m sofia.ops.discovery_canary `
        --host "$ArtemisHost" `
        --port $Port `
        --ca-file (Join-Path $FleetRoot "ca\fleet-ca.pem") `
        --client-cert (Join-Path $FleetRoot "venus\venus-client.pem") `
        --client-key (Join-Path $FleetRoot "venus\venus-client-key.pem") `
        --expected-node-id "$nodeId" `
        --expected-name "$ArtemisHost" `
        --expected-server-key "$serverPin"

    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "Fleet discovery canary failed with exit code $code."
    }

    Write-Host ""
    Write-Host "MUTUAL-TLS CANARY PASSED" -ForegroundColor Green
    Write-Host "No Fleet trust/enrollment was created by this verification."
}

switch ($Phase) {
    "Prepare" { Prepare-OnVenus }
    "Artemis" { Start-OnArtemis }
    "Verify"  { Verify-FromVenus }
}
