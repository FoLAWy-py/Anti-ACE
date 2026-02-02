[CmdletBinding()]
param(
    [switch]$NoClean
)

$ErrorActionPreference = 'Stop'

# Run from repo root regardless of current working directory.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

$spec = Join-Path $repoRoot "Anti-ACE.spec"
if (-not (Test-Path $spec)) {
    throw "Spec not found: $spec"
}

$cleanArgs = @()
if (-not $NoClean) {
    $cleanArgs = @("--clean")
}

Write-Host "Building Anti-ACE.exe with PyInstaller..."
Write-Host "  Repo: $repoRoot"
Write-Host "  Spec: $spec"

# Use uv-managed environment if available.
# If you don't use uv, replace `uv run` with `py -m`.
uv run pyinstaller @cleanArgs --noconfirm $spec

$exe = Join-Path $repoRoot "dist\Anti-ACE.exe"
if (Test-Path $exe) {
    Write-Host "OK: $exe"
} else {
    Write-Warning "Build finished, but exe not found at: $exe"
    Write-Warning "Check dist/ and PyInstaller output above."
}
