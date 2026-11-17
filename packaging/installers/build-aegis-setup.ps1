#Requires -Version 5.1
<#
Compile the double-clickable Aegis-Setup.exe Windows launcher and optionally
Authenticode-sign it.

The launcher only locates the adjacent signed release bundle and invokes
Install-Aegis.ps1 with the approved UAC elevation mechanism. It never accepts a
manual hash, approval id, Python path or service command.

Signing uses a caller-supplied certificate in the caller's Windows certificate
store. No private key, PFX password or key material is read, copied or embedded
by this script. If csc.exe is unavailable the build fails with a precise message
and the PowerShell fallback launcher remains available at Start-AegisSetup.ps1.
#>
[CmdletBinding()]
param(
    [string]$OutputPath = (Join-Path $PSScriptRoot 'Aegis-Setup.exe'),
    [string]$SigningThumbprint,
    [string]$SigningStore = 'My',
    [string]$TimestampUrl,
    [string]$SigntoolPath,
    [switch]$SkipSignatureVerification
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$source = Join-Path $PSScriptRoot 'AegisSetupLauncher.cs'
$fallback = Join-Path $PSScriptRoot 'Start-AegisSetup.ps1'
if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    [Console]::Error.WriteLine(
        'Aegis-Setup.exe was not built: launcher source is missing at ' + $source + '.')
    exit 2
}
if (-not (Test-Path -LiteralPath $fallback -PathType Leaf)) {
    [Console]::Error.WriteLine(
        'Aegis-Setup.exe was not built: the PowerShell fallback launcher is missing at ' +
        $fallback + '.')
    exit 2
}

$outputFull = [IO.Path]::GetFullPath($OutputPath)
$outputDirectory = [IO.Path]::GetDirectoryName($outputFull)
if ([string]::IsNullOrWhiteSpace($outputDirectory) -or
    -not (Test-Path -LiteralPath $outputDirectory -PathType Container)) {
    [Console]::Error.WriteLine(
        'Aegis-Setup.exe was not built: output directory does not exist: ' + $outputDirectory)
    exit 2
}

$windows = $env:WINDIR
if ([string]::IsNullOrWhiteSpace($windows)) {
    $windows = $env:SystemRoot
}
$compilerCandidates = @(
    (Join-Path $windows 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'),
    (Join-Path $windows 'Microsoft.NET\Framework\v4.0.30319\csc.exe')
)
$compiler = $null
foreach ($candidate in $compilerCandidates) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $compiler = $candidate
        break
    }
}
if ($null -eq $compiler) {
    [Console]::Error.WriteLine(
        'Aegis-Setup.exe was not built: the OS C# compiler csc.exe is unavailable. ' +
        'Install the .NET Framework 4.x targeting tools, or use the PowerShell fallback ' +
        'launcher: ' + $fallback)
    exit 2
}

$compilerArguments = @(
    '/nologo',
    '/target:winexe',
    '/platform:anycpu',
    '/optimize+',
    '/r:System.dll',
    '/r:System.Windows.Forms.dll',
    ('/out:' + $outputFull),
    $source
)
& $compiler @compilerArguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $outputFull -PathType Leaf)) {
    [Console]::Error.WriteLine(
        'Aegis-Setup.exe compilation failed with exit code ' + $LASTEXITCODE + '.')
    exit 2
}

if (-not [string]::IsNullOrWhiteSpace($SigningThumbprint)) {
    if ($SigningThumbprint -notmatch '^[0-9A-Fa-f]{40}$') {
        [Console]::Error.WriteLine(
            'Authenticode signing requires an exact 40-hex certificate thumbprint.')
        exit 2
    }
    $signtool = $null
    if (-not [string]::IsNullOrWhiteSpace($SigntoolPath)) {
        if (-not (Test-Path -LiteralPath $SigntoolPath -PathType Leaf)) {
            [Console]::Error.WriteLine('Requested signtool.exe path does not exist: ' + $SigntoolPath)
            exit 2
        }
        $signtool = $SigntoolPath
    } else {
        $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            $signtool = $command.Source
        }
    }
    if ($null -eq $signtool) {
        $programFilesX86 = ${env:ProgramFiles(x86)}
        if (-not [string]::IsNullOrWhiteSpace($programFilesX86)) {
            $kits = Join-Path $programFilesX86 'Windows Kits\10\bin'
            if (Test-Path -LiteralPath $kits -PathType Container) {
                $candidate = Get-ChildItem -Path (Join-Path $kits '*\x64\signtool.exe') `
                    -File -ErrorAction SilentlyContinue |
                    Sort-Object -Property FullName -Descending |
                    Select-Object -First 1
                if ($null -ne $candidate) { $signtool = $candidate.FullName }
            }
        }
    }
    if ($null -eq $signtool) {
        [Console]::Error.WriteLine(
            'Aegis-Setup.exe was built but could not be signed: signtool.exe is unavailable. ' +
            'Install the Windows SDK or pass -SigntoolPath.')
        exit 2
    }

    $signArguments = @(
        'sign',
        '/sha1', $SigningThumbprint,
        '/s', $SigningStore,
        '/fd', 'SHA256',
        '/v'
    )
    if (-not [string]::IsNullOrWhiteSpace($TimestampUrl)) {
        $signArguments += @('/tr', $TimestampUrl, '/td', 'SHA256')
    }
    $signArguments += $outputFull
    & $signtool @signArguments
    if ($LASTEXITCODE -ne 0) {
        [Console]::Error.WriteLine(
            'Authenticode signing failed with exit code ' + $LASTEXITCODE + '.')
        exit 2
    }
    if ($SkipSignatureVerification) {
        Write-Output 'AUTHENTICODE_VERIFICATION=SKIPPED_BY_CALLER'
    } else {
        & $signtool verify /pa /v $outputFull
        if ($LASTEXITCODE -ne 0) {
            [Console]::Error.WriteLine(
                'Authenticode verification failed after signing with exit code ' + $LASTEXITCODE + '.')
            exit 2
        }
    }
}

Write-Output ('AEGIS_SETUP_BUILT=' + $outputFull)
Write-Output ('POWERSHELL_FALLBACK=' + $fallback)
if ([string]::IsNullOrWhiteSpace($SigningThumbprint)) {
    Write-Output 'AUTHENTICODE=NOT_SIGNED'
} else {
    Write-Output ('AUTHENTICODE_SIGNED_WITH_THUMBPRINT=' + $SigningThumbprint.ToLowerInvariant())
}
exit 0
