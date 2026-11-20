#Requires -Version 5.1
<#
Aegis Platform one-step installer.

Default invocation performs the real guided installation through the bundled
Python runtime and the canonical guided orchestrator. The launcher only:

  - locates the adjacent signed release bundle and its bundled runtime,
  - requires the independently provisioned installer trust anchor
    (installer/trusted-publisher.pem and installer/trust.json),
  - elevates once through the approved Windows UAC mechanism when required,
  - forwards -Check, -Operation, -Json and -NoColor to the orchestrator.

Signature, publisher, revocation, SAFE/STOP, owner approval and lifecycle
semantics remain mandatory in the orchestrator. This launcher never accepts a
manual hash, approval id, Python path or service command, never disables
execution policy/anti-malware, and never performs a service action itself.

Safe read-only -VerifySeed / -VerifyPublisherBootstrap paths remain available
for independent offline media checks; they are not the default installer.
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$NoColor,
    [switch]$LineMode,
    [switch]$Json,
    [switch]$DryRun,
    [string]$BundleRoot,
    [string]$InstallRoot,
    [string]$TrustRoot,
    [ValidateSet('verify','status','doctor','install','update','repair','rollback','uninstall','reinstall','reconcile','purge')]
    [string]$Operation,
    [string]$VerifySeed,
    [string]$TrustedSeedSha256,
    [string]$VerifyPublisherBootstrap,
    [string]$TrustedPublisherThumbprint,
    [string]$TrustedBootstrapSha256
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($DryRun) { $Check = $true }
if ($Check -and $Operation) {
    [Console]::Error.WriteLine('-Check cannot be combined with -Operation.')
    exit 2
}
if (($VerifySeed -and ($Check -or $Operation -or $VerifyPublisherBootstrap -or
        -not [string]::IsNullOrWhiteSpace($BundleRoot))) -or
    ((-not [string]::IsNullOrEmpty($TrustedSeedSha256)) -and -not $VerifySeed) -or
    ($VerifyPublisherBootstrap -and ($Check -or $Operation -or
        -not [string]::IsNullOrWhiteSpace($BundleRoot))) -or
    ((-not [string]::IsNullOrEmpty($TrustedPublisherThumbprint) -or
      -not [string]::IsNullOrEmpty($TrustedBootstrapSha256)) -and
      -not $VerifyPublisherBootstrap)) {
    [Console]::Error.WriteLine('Conflicting or incomplete protected verifier arguments.')
    exit 2
}

$script:repoRoot = $PSScriptRoot
if (-not (Test-Path -LiteralPath (Join-Path $script:repoRoot 'contracts\ui\aegis-theme-v1.json') -PathType Leaf)) {
    $script:repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}
$script:themePath = Join-Path $script:repoRoot 'contracts\ui\aegis-theme-v1.json'
$script:useColor = (-not $NoColor) -and (-not $LineMode) -and (-not $Json) -and
    (-not (Test-Path Env:NO_COLOR)) -and ($Host.Name -eq 'ConsoleHost')
$script:theme = $null
if (Test-Path -LiteralPath $script:themePath -PathType Leaf) {
    try {
        $document = Get-Content -LiteralPath $script:themePath -Encoding UTF8 -Raw |
            ConvertFrom-Json -ErrorAction Stop
        if ($document.schema -eq 'aegis.ui.theme.v1') {
            $script:theme = $document.tokens
        }
    } catch {
        $script:theme = $null
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

function Write-AegisFailure {
    param([string]$Message)
    if ($Json) {
        $record = [ordered]@{
            schema = 'aegis.installer.guided-launcher.v1'
            result = 'BLOCKED'
            message = $Message
            executed = $false
            owner_approved = $false
            core_activated = $false
        }
        Write-Output (ConvertTo-Json -InputObject $record -Compress)
        return
    }
    [Console]::Error.WriteLine('AEGIS SETUP BLOCKED: ' + $Message)
}

function Assert-AegisLocalPath {
    param([string]$Path, [switch]$Directory)
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'Local installer path required.' }
    $absolute = [IO.Path]::GetFullPath($Path)
    if ($absolute.StartsWith('\\')) { throw 'Network/UNC paths are not allowed for installer media.' }
    # A redirected parent can silently relocate an otherwise ordinary leaf.
    # Walk to the volume root so junctions/reparse points fail closed.
    $cursor = $absolute
    while ($cursor) {
        $node = Get-Item -LiteralPath $cursor -Force -ErrorAction Stop
        if (($node.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'Installer media path contains a symbolic link, junction or reparse point.'
        }
        $parent = [IO.Directory]::GetParent($cursor)
        if ($null -eq $parent) { break }
        $cursor = $parent.FullName
    }
    $item = Get-Item -LiteralPath $absolute -Force -ErrorAction Stop
    if ($Directory -and -not $item.PSIsContainer) { throw 'Installer release root is not a directory.' }
    if (-not $Directory -and $item.PSIsContainer) { throw 'Installer file path is a directory.' }
    if (-not $Directory -and -not ($item -is [IO.FileInfo])) {
        throw 'Installer file path is not a regular file.'
    }
    return $absolute
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

function Get-AegisPinnedFileSha256 {
    param([IO.FileInfo]$File, [long]$MaxBytes, [string]$AllowedExtension)
    # Stock .NET streaming works in Windows PowerShell 5.1 even when the
    # Utility module (and Get-FileHash cmdlet) cannot be autoloaded.
    $stream = $null
    $algorithm = $null
    try {
        $stream = [IO.File]::Open($File.FullName, [IO.FileMode]::Open,
            [IO.FileAccess]::Read, [IO.FileShare]::Read)
        if ($stream.Length -ne $File.Length -or $stream.Length -lt 1 -or
            $stream.Length -gt $MaxBytes) { throw 'Offline file changed before hashing' }
        $algorithm = [Security.Cryptography.SHA256]::Create()
        $hash = $algorithm.ComputeHash($stream)
        $checked = Assert-AegisPinnedLocalFile -Path $File.FullName -MaxBytes $MaxBytes -AllowedExtension $AllowedExtension
        if ($checked.Length -ne $stream.Length -or
            $checked.LastWriteTimeUtc -ne $File.LastWriteTimeUtc -or
            $checked.CreationTimeUtc -ne $File.CreationTimeUtc) {
            throw 'Offline file changed during hashing'
        }
        return [BitConverter]::ToString($hash).Replace('-', '').ToLowerInvariant()
    } finally {
        if ($null -ne $algorithm) { $algorithm.Dispose() }
        if ($null -ne $stream) { $stream.Dispose() }
    }
}

function Test-AegisOfflineSeedHash {
    param([string]$Path, [string]$ExternalSha256)
    if ($ExternalSha256 -cnotmatch '^[0-9a-f]{64}$') {
        [Console]::Error.WriteLine('Independently pinned lowercase SHA-256 required.')
        exit 2
    }
    try {
        $file = Assert-AegisPinnedLocalFile -Path $Path -MaxBytes 1073741824 -AllowedExtension ''
        $digest = Get-AegisPinnedFileSha256 -File $file -MaxBytes 1073741824 -AllowedExtension ''
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
        $observed = Get-AegisPinnedFileSha256 -File $file -MaxBytes 67108864 -AllowedExtension '.exe'
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

function Resolve-AegisBundleRoot {
    param([string]$Explicit)
    if (-not [string]::IsNullOrWhiteSpace($Explicit)) {
        return Assert-AegisLocalPath -Path $Explicit -Directory
    }
    $scriptDir = [IO.Path]::GetFullPath($PSScriptRoot)
    $candidates = New-Object 'System.Collections.Generic.List[string]'
    $parent = [IO.Directory]::GetParent($scriptDir)
    # Installable bundles keep signed media in <bundle>/release and independent
    # installer trust in <bundle>/installer. Prefer the outer bundle root so the
    # orchestrator can see both, rather than resolving to release/ itself.
    $outerCandidates = @($scriptDir)
    if ($null -ne $parent) { $outerCandidates += $parent.FullName }
    foreach ($outer in $outerCandidates) {
        $nested = Join-Path $outer 'release/release-manifest.json'
        if (Test-Path -LiteralPath $nested -PathType Leaf) {
            return Assert-AegisLocalPath -Path $outer -Directory
        }
    }
    $candidates.Add($scriptDir)
    $candidates.Add((Join-Path $scriptDir 'release'))
    $candidates.Add((Join-Path $scriptDir 'bundle'))
    if ($null -ne $parent) {
        $candidates.Add($parent.FullName)
        $candidates.Add((Join-Path $parent.FullName 'release'))
        $candidates.Add((Join-Path $parent.FullName 'bundle'))
    }
    foreach ($candidate in $candidates) {
        $manifest = Join-Path $candidate 'release-manifest.json'
        if (Test-Path -LiteralPath $manifest -PathType Leaf) {
            return Assert-AegisLocalPath -Path $candidate -Directory
        }
    }
    throw ('Aegis release bundle not found. Expected release-manifest.json next to the ' +
        'installer, in its parent directory, or in ./release or ./bundle. Re-download the ' +
        'complete signed setup media; do not assemble or extract individual files.')
}

function Resolve-AegisTrustDirectory {
    param([string]$Root)
    $candidates = New-Object 'System.Collections.Generic.List[string]'
    $candidates.Add((Join-Path $Root 'installer'))
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        $candidates.Add([IO.Path]::GetFullPath($PSScriptRoot))
        $candidates.Add([IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'installer')))
    }
    foreach ($candidate in $candidates) {
        $pem = Join-Path $candidate 'trusted-publisher.pem'
        $policy = Join-Path $candidate 'trust.json'
        if ((Test-Path -LiteralPath $pem -PathType Leaf) -and
            (Test-Path -LiteralPath $policy -PathType Leaf)) {
            return Assert-AegisLocalPath -Path $candidate -Directory
        }
    }
    throw ('Independent installer trust anchor missing. Provision installer/trusted-publisher.pem ' +
        'and installer/trust.json out of band before running setup. Do not derive publisher trust ' +
        'from the release bundle or its signature.')
}

function Assert-AegisTrustAnchor {
    param([string]$BundleRoot)
    $directory = Resolve-AegisTrustDirectory -Root $BundleRoot
    $null = Assert-AegisPinnedLocalFile -Path (Join-Path $directory 'trusted-publisher.pem') `
        -MaxBytes 16384 -AllowedExtension '.pem'
    $null = Assert-AegisPinnedLocalFile -Path (Join-Path $directory 'trust.json') `
        -MaxBytes 65536 -AllowedExtension '.json'
    return $directory
}

function Resolve-AegisBundledPython {
    param([string]$Root)
    # Discovery is limited to the reviewed runtime layout inside the release
    # root. There is no PATH search, environment lookup or system interpreter
    # fallback, and every filesystem redirection fails closed.
    $rootPath = Assert-AegisLocalPath -Path $Root -Directory
    $nestedRelease = Join-Path $rootPath 'release'
    if (Test-Path -LiteralPath (Join-Path $nestedRelease 'release-manifest.json') -PathType Leaf) {
        $rootPath = Assert-AegisLocalPath -Path $nestedRelease -Directory
    }
    $windows = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
    if ($windows) {
        $relative = @('runtime\python\python.exe')
        $foreign = @('runtime/python/bin/python3.12', 'runtime/python/bin/python3')
    } else {
        $relative = @('runtime/python/bin/python3.12', 'runtime/python/bin/python3')
        $foreign = @('runtime\python\python.exe')
    }
    foreach ($item in $foreign) {
        $candidate = [IO.Path]::GetFullPath((Join-Path $rootPath $item))
        try {
            $null = Get-Item -LiteralPath $candidate -Force -ErrorAction Stop
        } catch [System.Management.Automation.ItemNotFoundException] {
            continue
        }
        throw 'Bundled runtime layout does not match the host operating system'
    }
    $separator = [IO.Path]::DirectorySeparatorChar
    $prefix = $rootPath.TrimEnd([IO.Path]::DirectorySeparatorChar,
        [IO.Path]::AltDirectorySeparatorChar) + $separator
    $comparison = if ($windows) {
        [StringComparison]::OrdinalIgnoreCase
    } else {
        [StringComparison]::Ordinal
    }
    $found = New-Object 'System.Collections.Generic.List[string]'
    foreach ($item in $relative) {
        $candidate = [IO.Path]::GetFullPath((Join-Path $rootPath $item))
        if (-not $candidate.StartsWith($prefix, $comparison)) {
            throw 'Bundled runtime path escapes the release root'
        }
        $present = $false
        try {
            $null = Get-Item -LiteralPath $candidate -Force -ErrorAction Stop
            $present = $true
        } catch [System.Management.Automation.ItemNotFoundException] {
            $present = $false
        }
        if (-not $present) { continue }
        $checked = Assert-AegisLocalPath -Path $candidate
        if (-not $checked.StartsWith($prefix, $comparison)) {
            throw 'Bundled runtime resolves outside the release root'
        }
        $found.Add($checked)
    }
    if ($found.Count -ne 1) {
        throw 'Exactly one bundled Python runtime must exist inside the release root'
    }
    return $found[0]
}

function Test-AegisElevated {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { return $false }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Test-AegisNeedsElevation {
    if ($Check) { return $false }
    if ($Operation -in @('verify','status','doctor')) { return $false }
    return $true
}

function ConvertTo-AegisQuotedArgument {
    param([string]$Value)
    if ($Value -match '["\r\n]') {
        throw 'Installer path contains an unsupported quote or line break.'
    }
    return '"' + $Value + '"'
}

function Invoke-AegisElevatedRelaunch {
    param([string]$Root)
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Elevation through UAC is only available on Windows. Run the platform installer as an administrator.'
    }
    $hostPath = $null
    try { $hostPath = (Get-Process -Id $PID).Path } catch { $hostPath = $null }
    if ([string]::IsNullOrWhiteSpace($hostPath)) {
        $candidate = Join-Path $PSHOME 'powershell.exe'
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $hostPath = $candidate }
    }
    if ([string]::IsNullOrWhiteSpace($hostPath)) {
        throw 'Unable to locate the current PowerShell host for an approved UAC relaunch.'
    }
    $parts = New-Object 'System.Collections.Generic.List[string]'
    $parts.Add('-NoProfile')
    $parts.Add('-File')
    $parts.Add((ConvertTo-AegisQuotedArgument -Value $PSCommandPath))
    $parts.Add('-BundleRoot')
    $parts.Add((ConvertTo-AegisQuotedArgument -Value $Root))
    if (-not [string]::IsNullOrWhiteSpace($InstallRoot)) {
        $parts.Add('-InstallRoot')
        $parts.Add((ConvertTo-AegisQuotedArgument -Value $InstallRoot))
    }
    if (-not [string]::IsNullOrWhiteSpace($TrustRoot)) {
        $parts.Add('-TrustRoot')
        $parts.Add((ConvertTo-AegisQuotedArgument -Value $TrustRoot))
    }
    if ($Operation) {
        $parts.Add('-Operation')
        $parts.Add($Operation)
    }
    if ($Check) { $parts.Add('-Check') }
    if ($Json) { $parts.Add('-Json') }
    if ($NoColor) { $parts.Add('-NoColor') }
    if ($LineMode) { $parts.Add('-LineMode') }
    $argumentLine = $parts -join ' '
    try {
        $process = Start-Process -FilePath $hostPath -Verb RunAs -ArgumentList $argumentLine `
            -Wait -PassThru -ErrorAction Stop
    } catch {
        throw ('Administrator approval was not granted or the elevated installer could not start. ' +
            'Approve the Windows UAC prompt and run setup again.')
    }
    if ($null -eq $process) {
        throw 'Elevated installer did not return a process result.'
    }
    exit $process.ExitCode
}

function Show-AegisGuidedBanner {
    param([string]$Root)
    if ($Json) { return }
    Write-AegisText 'AEGIS GUIDED PLATFORM INSTALLER' primary
    Write-AegisText ('RELEASE_BUNDLE=' + $Root) text_main
    if ($Check) {
        Write-AegisText 'MODE=CHECK (read-only preview)' accent
    } elseif ($Operation) {
        Write-AegisText ('MODE=OPERATION ' + $Operation) accent
    } else {
        Write-AegisText 'MODE=INSTALL' accent
    }
}

function Invoke-AegisGuidedInstaller {
    param([string]$Root, [string]$Python)
    # Isolation without -I: -E/-s ignore ambient Python configuration and user
    # site packages, -P keeps the working directory off sys.path, and -B avoids
    # writing bytecode into a read-only release. The bundled runtime still
    # resolves its own signed site-packages.
    $arguments = New-Object 'System.Collections.Generic.List[string]'
    foreach ($value in @('-E', '-s', '-P', '-B', '-m',
            'sofia.platform.ops.platform_installer_guided', '--bundle-root', $Root)) {
        $arguments.Add($value)
    }
    if ($Check) { $arguments.Add('--check') }
    if ($InstallRoot) {
        $arguments.Add('--install-root')
        $arguments.Add($InstallRoot)
    }
    if ($TrustRoot) {
        $arguments.Add('--trust-root')
        $arguments.Add($TrustRoot)
    }
    if ($Operation) {
        $arguments.Add('--operation')
        $arguments.Add($Operation)
    }
    if ($Json) { $arguments.Add('--json') }
    if ($NoColor -or $LineMode -or (Test-Path Env:NO_COLOR)) {
        $arguments.Add('--no-color')
    }
    & $Python @arguments
    $exitCode = 0
    if (Test-Path Variable:LASTEXITCODE) { $exitCode = $LASTEXITCODE }
    if ($exitCode -ne 0 -and -not $Json) {
        [Console]::Error.WriteLine(
            'AEGIS SETUP FAILED: the guided installer exited with code ' + $exitCode +
            '. Review the message above; setup did not retry or hide a failed step.')
    }
    exit $exitCode
}

if ($VerifySeed) {
    Test-AegisOfflineSeedHash -Path $VerifySeed -ExternalSha256 $TrustedSeedSha256
    exit 3
}
if ($VerifyPublisherBootstrap) {
    Test-AegisPublisherSignedBootstrap -Path $VerifyPublisherBootstrap `
        -PublisherThumbprint $TrustedPublisherThumbprint `
        -IndependentSha256 $TrustedBootstrapSha256
    exit 3
}

try {
    $resolvedRoot = Resolve-AegisBundleRoot -Explicit $BundleRoot
    $null = Assert-AegisTrustAnchor -BundleRoot $resolvedRoot
    $resolvedPython = Resolve-AegisBundledPython -Root $resolvedRoot
} catch {
    Write-AegisFailure -Message $_.Exception.Message
    exit 2
}

if ((Test-AegisNeedsElevation) -and -not (Test-AegisElevated)) {
    try {
        Invoke-AegisElevatedRelaunch -Root $resolvedRoot
    } catch {
        Write-AegisFailure -Message $_.Exception.Message
        exit 2
    }
}

Show-AegisGuidedBanner -Root $resolvedRoot
Invoke-AegisGuidedInstaller -Root $resolvedRoot -Python $resolvedPython
