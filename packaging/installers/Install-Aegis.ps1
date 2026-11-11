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
    [string]$VerifySeed,
    [string]$TrustedSeedSha256,
    [string]$VerifyPublisherBootstrap,
    [string]$TrustedPublisherThumbprint,
    [string]$TrustedBootstrapSha256,
    [ValidateSet('status','doctor','install','update','repair','rollback','uninstall','purge')]
    [string]$Operation
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($Check -and $Operation) {
    [Console]::Error.WriteLine('-Check cannot be combined with -Operation.')
    exit 2
}

if (($VerifySeed -and ($Check -or $Operation -or $DryRun -or $VerifyPublisherBootstrap)) -or
    ((-not [string]::IsNullOrEmpty($TrustedSeedSha256)) -and -not $VerifySeed) -or
    ($VerifyPublisherBootstrap -and ($Check -or $Operation -or $DryRun)) -or
    ((-not [string]::IsNullOrEmpty($TrustedPublisherThumbprint) -or
      -not [string]::IsNullOrEmpty($TrustedBootstrapSha256)) -and -not $VerifyPublisherBootstrap)) {
    [Console]::Error.WriteLine('Conflicting or incomplete protected verifier arguments.')
    exit 2
}

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

function Assert-AegisPinnedLocalFile {
    param([string]$Path, [long]$MaxBytes, [string]$AllowedExtension)
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'Local file path required' }
    $absolute = [IO.Path]::GetFullPath($Path)
    if ($absolute.StartsWith('\\')) { throw 'Network/UNC paths are not allowed as offline trust roots' }
    if ($AllowedExtension -and
        [IO.Path]::GetExtension($absolute).ToLowerInvariant() -cne $AllowedExtension) {
        throw 'Unreviewed native bootstrap file type'
    }
    $cursor = $absolute
    while ($cursor) {
        $item = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Offline path contains symbolic link/junction/reparse point'
        }
        $parent = [IO.Directory]::GetParent($cursor)
        if ($null -eq $parent) { break }
        $cursor = $parent.FullName
    }
    $file = Get-Item -LiteralPath $absolute -Force -ErrorAction Stop
    if (-not ($file -is [IO.FileInfo]) -or
        $file.Length -lt 1 -or $file.Length -gt $MaxBytes) {
        throw 'Offline artifact is not a regular bounded local file'
    }
    return $file
}

function Test-AegisOfflineSeedHash {
    param([string]$Path, [string]$ExternalSha256)
    if ($ExternalSha256 -cnotmatch '^[0-9a-f]{64}$') {
        [Console]::Error.WriteLine('Independently pinned lowercase SHA-256 required.')
        exit 2
    }
    try {
        $file = Assert-AegisPinnedLocalFile -Path $Path -MaxBytes 1073741824 -AllowedExtension ''
        $digest = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
        $matches = $digest -ceq $ExternalSha256
        if ($Json) {
            $result = [ordered]@{
                schema = 'aegis.installer.seed-byte-check.v1'
                result = $(if ($matches) { 'HASH_MATCH_ONLY' } else { 'REJECTED' })
                byte_digest_match = $matches
                sha256 = $digest
                size_bytes = $file.Length
                signature_verified = $false
                owner_approved = $false
                executed = $false
                core_activated = $false
            }
            Write-Output (ConvertTo-Json -InputObject $result -Compress)
        } elseif ($matches) {
            Write-Output 'RESULT=HASH_MATCH_ONLY'
            Write-Output ('SHA256=' + $digest)
            Write-Output ('SIZE_BYTES=' + $file.Length)
            Write-Output 'SIGNED_RELEASE=NOT_VERIFIED'
            Write-Output 'PUBLISHER_SIGNATURE=NOT_VERIFIED'
            Write-Output 'INSTALL_AUTHORITY=NOT_CONNECTED'
            Write-Output 'NO_CHANGES_MADE=TRUE'
        } else {
            Write-Output 'RESULT=REJECTED'
            Write-Output 'SIGNED_RELEASE=NOT_VERIFIED'
            Write-Output 'NO_CHANGES_MADE=TRUE'
        }
        if ($matches) { exit 0 }
        exit 3
    } catch {
        # Explicit developer fixture diagnostics only. Ordinary operator
        # mode never reveals file paths or internal trust-check details.
        if ((Test-Path Env:AEGIS_INSTALLER_TEST_DIAGNOSTICS) -and
            $env:AEGIS_INSTALLER_TEST_DIAGNOSTICS -eq '1') {
            [Console]::Error.WriteLine(
                'TEST-ONLY-SEED-DIAGNOSTIC: ' + $_.Exception.GetType().FullName +
                ': ' + $_.Exception.Message
            )
        }
        [Console]::Error.WriteLine('Offline seed unavailable, redirected or invalid.')
        exit 3
    }
}

function Test-AegisPublisherSignedBootstrap {
    param([string]$Path, [string]$PublisherThumbprint, [string]$IndependentSha256)
    # Only Windows Authenticode of an independently pinned EXE.
    # This does not certify the release manifest, assets, fresh revocation
    # information, Team A owner approval or an executable installer.
    if ($PublisherThumbprint -cnotmatch '^[0-9a-fA-F]{40}$' -or
        $IndependentSha256 -cnotmatch '^[0-9a-f]{64}$') {
        [Console]::Error.WriteLine('Both independently pinned publisher certificate and SHA-256 are required.')
        exit 2
    }
    try {
        $file = Assert-AegisPinnedLocalFile -Path $Path -MaxBytes 67108864 -AllowedExtension '.exe'
        $observed = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
        if ($observed -cne $IndependentSha256) { throw 'Pinned EXE digest differs' }
        $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName -ErrorAction Stop
        if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate) {
            throw 'Publisher signature invalid or untrusted'
        }
        $cert = $signature.SignerCertificate
        if ($cert.Thumbprint.ToUpperInvariant() -cne $PublisherThumbprint.ToUpperInvariant()) {
            throw 'Authenticode publisher certificate does not match independent pin'
        }
        $now = [DateTime]::UtcNow
        if ($cert.NotBefore.ToUniversalTime() -gt $now -or
            $cert.NotAfter.ToUniversalTime() -lt $now) {
            throw 'Publisher signing certificate expired or not yet valid'
        }
        $codeEku = $false
        foreach ($extension in $cert.Extensions) {
            if ($extension.Oid.Value -eq '2.5.29.37') {
                $eku = [Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$extension
                foreach ($oid in $eku.EnhancedKeyUsages) {
                    if ($oid.Value -eq '1.3.6.1.5.5.7.3.3') { $codeEku = $true }
                }
            }
        }
        if (-not $codeEku) { throw 'Publisher certificate missing code signing EKU' }
        if ($Json) {
            $receipt = [ordered]@{
                schema = 'aegis.installer.publisher-bootstrap-check.v1'
                result = 'AUTHENTICODE_BINARY_ONLY'
                publisher_certificate_thumbprint = $cert.Thumbprint.ToLowerInvariant()
                executable_sha256 = $observed
                publisher_authenticode_verified = $true
                publisher_revocation_fresh = $false
                release_ed25519_verified = $false
                release_assets_verified = $false
                owner_approved = $false
                executed = $false
                core_activated = $false
            }
            Write-Output (ConvertTo-Json -InputObject $receipt -Compress)
        } else {
            Write-Output 'RESULT=AUTHENTICODE_BINARY_ONLY'
            Write-Output ('BOOTSTRAP_SHA256=' + $observed)
            Write-Output 'PUBLISHER_SIGNATURE=AUTHENTICODE_VALID'
            Write-Output 'REVOCATION_FRESH=FALSE'
            Write-Output 'ED25519_RELEASE=NOT_VERIFIED'
            Write-Output 'ASSETS_VERIFIED=FALSE'
            Write-Output 'INSTALL_AUTHORITY=NOT_CONNECTED'
            Write-Output 'NO_CHANGES_MADE=TRUE'
        }
        exit 0
    } catch {
        [Console]::Error.WriteLine('Publisher bootstrap authentication refused.')
        exit 3
    }
}

if ($VerifySeed) {
    Test-AegisOfflineSeedHash -Path $VerifySeed -ExternalSha256 $TrustedSeedSha256
    exit 3
}
if ($VerifyPublisherBootstrap) {
    Test-AegisPublisherSignedBootstrap -Path $VerifyPublisherBootstrap -PublisherThumbprint $TrustedPublisherThumbprint -IndependentSha256 $TrustedBootstrapSha256
    exit 3
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
