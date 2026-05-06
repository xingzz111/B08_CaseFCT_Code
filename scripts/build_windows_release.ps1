param(
  [string]$RepoRoot = (Resolve-Path ".").Path,
  [string]$Python = "python",
  [string]$ReleaseDir = "code_Release_CaseFCT",
  [string]$Version = ""
)

$ErrorActionPreference = "Stop"

function Ensure-Dir([string]$Path) {
  if (!(Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Sync-Dir([string]$Source, [string]$Dest) {
  Ensure-Dir $Dest
  # Exclude build outputs and VCS metadata to keep release clean/small
  $excludeDirs = @(
    ".git",
    ".github",
    "__pycache__",
    "build",
    "dist",
    "OSENSTester"
  )
  $xd = @()
  foreach ($d in $excludeDirs) { $xd += @("/XD", (Join-Path $Source $d)) }

  robocopy $Source $Dest /MIR /R:2 /W:2 /NFL /NDL /NJH /NJS /NP @xd | Out-Null
  if ($LASTEXITCODE -ge 8) {
    throw "robocopy failed syncing '$Source' -> '$Dest' (exit=$LASTEXITCODE)"
  }
}

$repo = (Resolve-Path $RepoRoot).Path
$common = Join-Path $repo "CommonPlatform"
$engine = Join-Path $repo "engine"
$release = Join-Path $repo $ReleaseDir

if (!(Test-Path -LiteralPath $common)) { throw "Missing CommonPlatform at $common" }
if (!(Test-Path -LiteralPath $engine)) { throw "Missing engine at $engine" }
if (!(Test-Path -LiteralPath $release)) { throw "Missing release dir at $release" }

if ([string]::IsNullOrWhiteSpace($Version)) {
  $tag = $env:GITHUB_REF_NAME
  if (![string]::IsNullOrWhiteSpace($tag)) {
    $Version = $tag.TrimStart("v")
  }
}
if ([string]::IsNullOrWhiteSpace($Version)) {
  $Version = "0.0.0-dev"
}

Write-Host "RepoRoot: $repo"
Write-Host "ReleaseDir: $release"
Write-Host "Version: $Version"

#
# Step 1: Build OSENSTester (PyInstaller)
#
Push-Location $common
try {
  if (Test-Path -LiteralPath ".\dist") { Remove-Item -Recurse -Force ".\dist" }
  if (Test-Path -LiteralPath ".\build") { Remove-Item -Recurse -Force ".\build" }
  if (Test-Path -LiteralPath ".\OSENSTester") { Remove-Item -Recurse -Force ".\OSENSTester" }

  & $Python -m pip install --upgrade pip | Out-Null
  & $Python -m pip install -r ".\requirements-build.txt"

  & $Python -m PyInstaller ".\src\spec\Tester_windows.spec"

  Ensure-Dir ".\dist\configure"
  Ensure-Dir ".\dist\profile"
  Ensure-Dir ".\dist\engine"

  Copy-Item ".\src\configure\*.json" ".\dist\configure\" -Force
  Copy-Item (Join-Path $engine "*") ".\dist\engine\" -Recurse -Force
  Copy-Item (Join-Path $engine "profile\*.csv") ".\dist\profile\" -Force -ErrorAction SilentlyContinue

  & ".\src\signer\signer_win.exe" -d ".\dist"

  Move-Item ".\dist" ".\OSENSTester"
  Copy-Item ".\killport.bat" ".\OSENSTester\" -Force
  Copy-Item ".\__init__.py" ".\OSENSTester\" -Force
}
finally {
  Pop-Location
}

#
# Step 1 output: sync OSENSTester into code_Release_CaseFCT
#
$releaseOsens = Join-Path $release "OSENSTester"
if (Test-Path -LiteralPath $releaseOsens) { Remove-Item -Recurse -Force $releaseOsens }
Copy-Item (Join-Path $common "OSENSTester") $releaseOsens -Recurse -Force
if (Test-Path -LiteralPath (Join-Path $common "OSENSTester")) {
  Remove-Item -Recurse -Force (Join-Path $common "OSENSTester")
}

#
# Step 2: Sync Overlay sources into code_Release_CaseFCT/Overlay
#
$releaseOverlay = Join-Path $release "Overlay"
Ensure-Dir $releaseOverlay
Sync-Dir $common (Join-Path $releaseOverlay "CommonPlatform")
Sync-Dir $engine (Join-Path $releaseOverlay "engine")

#
# Step 2: Build installer via Inno Setup (expects iscc.exe in PATH)
#
Push-Location $release
try {
  Ensure-Dir ".\Output"
  & iscc.exe "/DMyAppVersion=$Version" ".\CodeExample_code_testplan.iss"
}
finally {
  Pop-Location
}

Write-Host "Done. Outputs:"
Write-Host " - $release\\Output\\SetupCaseFCTCode_$Version.exe (or similar)"
Write-Host " - $release (folder to zip for code release)"
