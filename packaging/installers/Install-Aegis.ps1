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
    (($null -ne $TrustedSeedSha256 -and $TrustedSeedSha256.Length -gt 0) -and -not $VerifySeed)) {
    [Console]::Error.WriteLine('Ambiguous seed preflight flags.')
    exit 2
}
if (($VerifyPublisherBootstrap -and ($Check -or $Operation -or $DryRun -or $VerifySeed)) -or
    (([string]::IsNullOrEmpty($VerifyPublisherBootstrap)) -and
      (-not [string]::IsNullOrEmpty($TrustedPublisherThumbprint) -or
       -not [string]::IsNullOrEmpty($TrustedBootstrapSha256)))) {
    [Console]::Error.WriteLine('Publisher trust check cannot be combined with protected operations.')
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

function Test-AegisOfflineSeedHash {
    param([string]$Path, [string]$ExternalSha256)
    # Stock PowerShell 5.1/.NET. This only checks pinned *bytes*: the signed
    # PlatformReleaseVerifier and SAFE owner approval are distinct later gates.
    if ($ExternalSha256 -cnotmatch '^[0-9a-f]{64}
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
) {
        [Console]::Error.WriteLine('Independently pinned lowercase SHA-256 is required.')
        exit 2
    }
    try {
        $absolute = [IO.Path]::GetFullPath($Path)
        if ($absolute.StartsWith('\\')) { throw 'UNC seed is not offline local media' }
        $cursor = $absolute
        while ($null -ne $cursor -and $cursor.Length -gt 0) {
            $entry = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Offline seed path contains a reparse point'
            }
            $parent = [IO.Directory]::GetParent($cursor)
            if ($null -eq $parent) { break }
            $cursor = $parent.FullName
        }
        $file = Get-Item -LiteralPath $absolute -Force -ErrorAction Stop
        if (-not ($file -is [IO.FileInfo]) -or $file.Length -lt 1 -or
            $file.Length -gt 1073741824) {
            throw 'Offline seed is not a bounded ordinary file'
        }
        $observed = (Get-FileHash -LiteralPath $absolute -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
        $matched = ($observed -ceq $ExternalSha256)
        if ($Json) {
            $record = [ordered]@{
                schema = 'aegis.installer.seed-byte-check.v1'
                result = $(if ($matched) { 'HASH_MATCH_ONLY' } else { 'REJECTED' })
                byte_digest_match = $matched
                sha256 = $observed
                size_bytes = $file.Length
                signature_verified = $false
                owner_approved = $false
                executed = $false
                core_activated = $false
            }
            Write-Output (ConvertTo-Json -InputObject $record -Compress)
        } elseif ($matched) {
            Write-Output 'RESULT=HASH_MATCH_ONLY'
            Write-Output ('SHA256=' + $observed)
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
        if ($matched) { exit 0 }
        exit 3
    } catch {
        [Console]::Error.WriteLine('Offline seed inaccessible, redirected, or outside bounded policy.')
        exit 3
    }
}

function Test-AegisPublisherSignedBootstrap {
    param(
        [string]$Path,
        [string]$PublisherThumbprint,
        [string]$IndependentSha256
    )
    # Windows' native Authenticode trust validation is distinct from
    # SHA256 integrity and from Platform's canonical Ed25519 release proof.
    # A trusted *publisher-signed* native verifier must still separately
    # validate the Ed25519 manifest and exact assets before any install.
    if ($PublisherThumbprint -cnotmatch '^[0-9A-Fa-f]{40} -Path $VerifySeed -ExternalSha256 $TrustedSeedSha256
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
 -or
        $IndependentSha256 -cnotmatch '^[0-9a-f]{64} -Path $VerifySeed -ExternalSha256 $TrustedSeedSha256
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
) {
        [Console]::Error.WriteLine('Externally pinned code-signing cert and release digest are mandatory.')
        exit 2
    }
    try {
        $absolute = [IO.Path]::GetFullPath($Path)
        if ($absolute.StartsWith('\\') -or
            [IO.Path]::GetExtension($absolute).ToLowerInvariant() -ne '.exe') {
            throw 'Native local signed executable required'
        }
        $cursor = $absolute
        while ($cursor -and $cursor.Length -gt 0) {
            $entry = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Publisher executable path contains reparse point'
            }
            $parent = [IO.Directory]::GetParent($cursor)
            if ($null -eq $parent) { break }
            $cursor = $parent.FullName
        }
        $item = Get-Item -LiteralPath $absolute -Force -ErrorAction Stop
        if (-not ($item -is [IO.FileInfo]) -or
            $item.Length -lt 1 -or $item.Length -gt 67108864) {
            throw 'Publisher executable outside bounded size'
        }
        $digest = (Get-FileHash -LiteralPath $absolute -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
        if ($digest -cne $IndependentSha256) {
            throw 'Pinned executable bytes changed'
        }
        $signature = Get-AuthenticodeSignature -LiteralPath $absolute -ErrorAction Stop
        if ($signature.Status -ne 'Valid' -or
            $null -eq $signature.SignerCertificate) {
            throw 'Unsigned or untrusted native installer'
        }
        $certificate = $signature.SignerCertificate
        if ($certificate.Thumbprint.ToUpperInvariant() -cne
            $PublisherThumbprint.ToUpperInvariant()) {
            throw 'Code signer differs from independently pinned publisher'
        }
        $utc = [DateTime]::UtcNow
        if ($certificate.NotBefore.ToUniversalTime() -gt $utc -or
            $certificate.NotAfter.ToUniversalTime() -lt $utc) {
            throw 'Code signing certificate outside validity'
        }
        $eku = $certificate.Extensions | Where-Object {
            $_.Oid.Value -eq '2.5.29.37'
        }
        if ($null -eq $eku) {
            throw 'Missing code signing key usage'
        }
        $codeSigning = ($eku | ForEach-Object {
            $_.EnhancedKeyUsages | Where-Object { $_.Value -eq '1.3.6.1.5.5.7.3.3' }
        })
        if ($null -eq $codeSigning) {
            throw 'No code signing extended key usage'
        }
        if ($Json) {
            $result = [ordered]@{
                schema = 'aegis.installer.publisher-bootstrap-check.v1'
                result = 'AUTHENTICODE_BINARY_ONLY'
                publisher_certificate_thumbprint = $certificate.Thumbprint.ToLowerInvariant()
                executable_sha256 = $digest
                publisher_authenticode_verified = $true
                release_ed25519_verified = $false
                release_assets_verified = $false
                owner_approved = $false
                executed = $false
                core_activated = $false
            }
            Write-Output (ConvertTo-Json -InputObject $result -Compress)
        } else {
            Write-Output 'RESULT=AUTHENTICODE_BINARY_ONLY'
            Write-Output ('BOOTSTRAP_SHA256=' + $digest)
            Write-Output 'PUBLISHER_SIGNATURE=AUTHENTICODE_VALID'
            Write-Output 'ED25519_RELEASE=NOT_VERIFIED'
            Write-Output 'ASSETS_VERIFIED=FALSE'
            Write-Output 'INSTALL_AUTHORITY=NOT_CONNECTED'
            Write-Output 'NO_CHANGES_MADE=TRUE'
        }
        exit 0
    } catch {
        [Console]::Error.WriteLine('Publisher signature or independently pinned executable rejected.')
        exit 3
    }
}

if ($VerifyPublisherBootstrap) {
    Test-AegisPublisherSignedBootstrap -Path $VerifyPublisherBootstrap -PublisherThumbprint $TrustedPublisherThumbprint -IndependentSha256 $TrustedBootstrapSha256
    exit 3
}

if ($VerifySeed) {
    Test-AegisOfflineSeedHash -Path $VerifySeed -ExternalSha256 $TrustedSeedSha256
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
