# Install Sofía's illustrated PUBLIC static-candidate pack. Never changes sofia.db.
# Optional -PublishToGit commits the original ZIP asset to main from Venus.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string] $Archive,
    [switch] $PublishToGit
)

$ErrorActionPreference = 'Stop'
$ExpectedSha256 = '299bd7f9d80682ca0a27877595b1be915eaf0061eb81053d328fbb672caf6855'
$ExpectedOutfits = @(
    'day.default', 'night.lounge', 'outfit.violet_casual',
    'outfit.rainy_engineer', 'outfit.summer_violet'
)
$Repository = (& git rev-parse --show-toplevel)
if ($LASTEXITCODE -ne 0 -or -not $Repository) { throw 'Run inside the Sofía Git checkout.' }
$Repository = $Repository.Trim()
if ((& git -C $Repository branch --show-current).Trim() -ne 'main') {
    throw 'Only the main branch is supported.'
}
if ($PublishToGit) {
    $Dirty = & git -C $Repository status --porcelain
    if ($Dirty) { throw 'Git working tree must be clean before publishing an asset.' }
}

$Archive = (Resolve-Path -LiteralPath $Archive).Path
$ActualSha256 = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualSha256 -ne $ExpectedSha256) {
    throw 'ZIP SHA-256 mismatch. Refusing an unreviewed or modified archive.'
}

$Art = Join-Path $env:LOCALAPPDATA 'SofiaAdaLyra\Avatar2D\Public-V2'
if (-not (Test-Path -LiteralPath $Art)) {
    python -m sofia.avatar.vtuber_public_setup --output "$Art" --all-public
    if ($LASTEXITCODE -ne 0) { throw 'Public 2D baseline setup failed.' }
}
if (-not (Test-Path -LiteralPath (Join-Path $Art 'character\manifest.json'))) {
    throw 'Existing Public-V2 root has no character pack. Do not overwrite it.'
}
if (Test-Path -LiteralPath (Join-Path $Art 'portraits')) {
    throw 'An illustrated portraits folder already exists. Choose a new versioned root.'
}
if (Test-Path -LiteralPath (Join-Path $Art 'illustrated_drafts')) {
    throw 'Illustrated draft artwork already exists. Refusing overwrite.'
}

$Stage = Join-Path $env:TEMP ('sofia-illustrated-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $Stage | Out-Null
try {
    Expand-Archive -LiteralPath $Archive -DestinationPath $Stage
    foreach ($Outfit in $ExpectedOutfits) {
        $Folder = Join-Path $Stage ('portraits\' + $Outfit)
        $ManifestFile = Join-Path $Folder 'manifest.json'
        $PngFile = Join-Path $Folder 'portrait.png'
        if (-not (Test-Path -LiteralPath $ManifestFile) -or -not (Test-Path -LiteralPath $PngFile)) {
            throw "Missing illustrated portrait for $Outfit"
        }
        $Manifest = Get-Content -LiteralPath $ManifestFile -Raw | ConvertFrom-Json
        if ($Manifest.outfit_id -ne $Outfit -or $Manifest.public_only -ne $true -or
            $Manifest.animation -ne 'static' -or
            $Manifest.schema -ne 'sofia-public-illustrated-static-v1') {
            throw "Invalid manifest metadata: $Outfit"
        }
        $Digest = (Get-FileHash -LiteralPath $PngFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Digest -ne $Manifest.portrait_sha256) { throw "Portrait hash mismatch: $Outfit" }
    }
    Move-Item -LiteralPath (Join-Path $Stage 'portraits') -Destination (Join-Path $Art 'portraits')
    Move-Item -LiteralPath (Join-Path $Stage 'illustrated_drafts') -Destination (Join-Path $Art 'illustrated_drafts')
}
finally {
    if (Test-Path -LiteralPath $Stage) {
        Remove-Item -LiteralPath $Stage -Recurse -Force
    }
}
Write-Host 'Illustrated public portraits installed and hash-checked:' $Art

if ($PublishToGit) {
    $Destination = Join-Path $Repository 'assets\avatar2d\illustrated_public_v1'
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $GitZip = Join-Path $Destination 'sofia2d_public_illustrated_candidates_v1.zip'
    if (Test-Path -LiteralPath $GitZip) { throw 'Existing repository asset will not be overwritten.' }
    Copy-Item -LiteralPath $Archive -Destination $GitZip
    & git -C $Repository add -- 'assets/avatar2d/illustrated_public_v1/sofia2d_public_illustrated_candidates_v1.zip'
    if ($LASTEXITCODE -ne 0) { throw 'git add failed.' }
    & git -C $Repository commit -m 'assets(avatar2d): add illustrated public static candidate pack'
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed.' }
    & git -C $Repository push origin main
    if ($LASTEXITCODE -ne 0) { throw 'git push failed. Local commit remains for retry.' }
    Write-Host 'Asset ZIP committed and pushed to main.'
}
Write-Host 'Launch Sofía normally: python -m sofia'
