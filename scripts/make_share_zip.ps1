<#
.SYNOPSIS
    Build a shareable source zip for VideoRefiner Studio.

.DESCRIPTION
    Copies only the files a recipient needs to run setup.bat, excludes local
    environments, model weights, test data, caches, and logs, then writes a
    zip under dist\.

.EXAMPLE
    .\scripts\make_share_zip.ps1
#>
[CmdletBinding()]
param(
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

if (-not $OutputPath) {
    $OutputPath = Join-Path $Root "dist\VideoRefinerStudio-share.zip"
} elseif (-not [System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $Root $OutputPath
}

$StageParent = Join-Path $env:TEMP "VideoRefinerStudio-share"
$StageRoot = Join-Path $StageParent "VideoRefinerStudio"
$IncludeFiles = @(
    ".gitignore",
    "LICENSE",
    "NOTICE",
    "README.md",
    "SHARING.md",
    "THIRD_PARTY_NOTICES.md",
    "main.py",
    "run.bat",
    "setup.bat"
)
$IncludeDirs = @(
    "docs",
    "scripts",
    "videorefiner"
)

if (Test-Path -LiteralPath $StageParent) {
    Remove-Item -LiteralPath $StageParent -Recurse -Force
}
New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null

foreach ($name in $IncludeFiles) {
    $source = Join-Path $Root $name
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Missing required file: $name"
    }
    Copy-Item -LiteralPath $source -Destination (Join-Path $StageRoot $name) -Force
}

foreach ($name in $IncludeDirs) {
    $source = Join-Path $Root $name
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Missing required directory: $name"
    }
    Copy-Item -LiteralPath $source -Destination $StageRoot -Recurse -Force
}

Get-ChildItem -LiteralPath $StageRoot -Recurse -Force -Directory |
    Where-Object { $_.Name -in @("__pycache__", ".pytest_cache", ".idea", ".vscode", ".jasna") } |
    Remove-Item -Recurse -Force

Get-ChildItem -LiteralPath $StageRoot -Recurse -Force -File |
    Where-Object { $_.Extension -in @(".pyc", ".log", ".part", ".tmp") -or $_.Name -in @("Thumbs.db", ".DS_Store") } |
    Remove-Item -Force

$required = @(
    "setup.bat",
    "scripts\setup.ps1",
    "scripts\bootstrap.ps1",
    "scripts\download_models.py",
    "videorefiner\app.py",
    "main.py",
    "run.bat"
)
foreach ($relative in $required) {
    if (-not (Test-Path -LiteralPath (Join-Path $StageRoot $relative))) {
        throw "The staged package is missing: $relative"
    }
}

$forbidden = @(".venv", "vendor", "model_weights", "test_input", "test_output", ".git", "dist")
foreach ($name in $forbidden) {
    if (Test-Path -LiteralPath (Join-Path $StageRoot $name)) {
        throw "The staged package unexpectedly contains: $name"
    }
}

$outputDir = Split-Path -Parent $OutputPath
if (-not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}
if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}

Compress-Archive -Path $StageRoot -DestinationPath $OutputPath -CompressionLevel Optimal

Remove-Item -LiteralPath $StageParent -Recurse -Force

$sizeMB = [math]::Round((Get-Item -LiteralPath $OutputPath).Length / 1MB, 2)
Write-Host "Created: $OutputPath ($sizeMB MB)" -ForegroundColor Green
