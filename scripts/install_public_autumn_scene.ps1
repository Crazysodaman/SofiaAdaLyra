# Installs and optionally publishes the new PUBLIC Autumn Cyber illustrated scene.
# Requires an existing Public-V2 base character pack. Does not change sofia.db.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string] $Archive,
    [switch] $PublishToGit
)
$ErrorActionPreference = "Stop"
$Expected = "b9cfad0b604f68fc659c9e0f07f598c57d5838444951a387c4557c348de14f68"
$Archive = (Resolve-Path -LiteralPath $Archive).Path
$Actual = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $Expected) {
    throw "Scene ZIP SHA256 differs from the known reviewed package. Installation refused."
}
$Art = Join-Path $env:LOCALAPPDATA "SofiaAdaLyra\Avatar2D\Public-V2"
if (-not (Test-Path -LiteralPath (Join-Path $Art "character\manifest.json"))) {
    throw "Install Sofía's Public-V2 character pack first."
}
$Repo = (& git rev-parse --show-toplevel)
if ($LASTEXITCODE -ne 0) { throw "Run inside the Sofía Git checkout." }
$Repo = $Repo.Trim()
if ((& git -C $Repo branch --show-current).Trim() -ne "main") {
    throw "Only main is supported."
}
if ($PublishToGit -and (& git -C $Repo status --porcelain)) {
    throw "Working tree must be clean before publishing binary assets."
}
& python -m sofia.avatar.scene_install --archive "$Archive" --root "$Art" --verify-only
if ($LASTEXITCODE -ne 0) { throw "Public scene validation failed before installation." }
& python -m sofia.avatar.scene_install --archive "$Archive" --root "$Art"
if ($LASTEXITCODE -ne 0) { throw "Public scene installation failed." }
Write-Host "Autumn Cyber illustrated static portrait and independently editable background installed."

if ($PublishToGit) {
    $DestDir = Join-Path $Repo "assets\avatar2d\scenes\public_autumn_v1"
    New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
    $Dest = Join-Path $DestDir "sofia2d_scene_autumn_cyber_v1.zip"
    if (Test-Path -LiteralPath $Dest) { throw "Git asset already exists. No overwrite." }
    Copy-Item -LiteralPath $Archive -Destination $Dest
    & git -C $Repo add -- "assets/avatar2d/scenes/public_autumn_v1/sofia2d_scene_autumn_cyber_v1.zip"
    if ($LASTEXITCODE -ne 0) { throw "git add failed" }
    & git -C $Repo commit -m "assets(avatar2d): add public Autumn Cyber scene and background"
    if ($LASTEXITCODE -ne 0) { throw "git commit failed" }
    & git -C $Repo push origin main
    if ($LASTEXITCODE -ne 0) { throw "git push failed; local commit remains for retry" }
    Write-Host "Autumn Cyber ZIP published to main."
}
Write-Host "Relaunch the desktop (python -m sofia). Choose 2D, then Scene... to edit."
