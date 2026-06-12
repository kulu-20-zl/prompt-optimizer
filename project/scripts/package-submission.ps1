# Package submission per 实训要求 Section 5
# Usage: .\scripts\package-submission.ps1
# Default: 曾露-伍灵晰-吴芝-综合测试实践.zip

param(
    [string]$Members = "曾露-伍灵晰-吴芝"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$RepoRoot = Split-Path $ProjectRoot -Parent
$OutDir = Join-Path $RepoRoot "submission-package"
$ZipName = "$Members-综合测试实践.zip"
$ZipPath = Join-Path $RepoRoot $ZipName

$ExcludeDirs = @("venv", "__pycache__", ".pytest_cache", "htmlcov", "instance", "tests")

function Copy-ProjectTree {
    param([string]$Source, [string]$Dest)
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    Get-ChildItem -Path $Source -Force | ForEach-Object {
        if ($ExcludeDirs -contains $_.Name) { return }
        if ($_.Name -eq ".env") { return }
        $target = Join-Path $Dest $_.Name
        if ($_.PSIsContainer) {
            Copy-ProjectTree -Source $_.FullName -Dest $target
        } else {
            Copy-Item -Path $_.FullName -Destination $target -Force
        }
    }
}

function Copy-TestsClean {
    param([string]$Source, [string]$Dest)
    New-Item -ItemType Directory -Path $Dest -Force | Out-Null
    Get-ChildItem -Path $Source -Recurse -Force | ForEach-Object {
        if ($_.PSIsContainer) {
            if ($_.Name -eq "__pycache__") { return }
            return
        }
        if ($_.Extension -eq ".pyc") { return }
        $rel = $_.FullName.Substring($Source.Length).TrimStart("\")
        $target = Join-Path $Dest $rel
        $parent = Split-Path $target -Parent
        if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        Copy-Item $_.FullName $target -Force
    }
}

if (Test-Path $OutDir) { Remove-Item $OutDir -Recurse -Force }
New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

# project/ (backend + frontend only, no tests/)
Copy-ProjectTree -Source $ProjectRoot -Dest (Join-Path $OutDir "project")

# tests/ per requirement naming
$TestsRoot = Join-Path $OutDir "tests"
New-Item -ItemType Directory -Path $TestsRoot -Force | Out-Null
Copy-TestsClean (Join-Path $ProjectRoot "tests\unit") (Join-Path $TestsRoot "unit_tests")
Copy-TestsClean (Join-Path $ProjectRoot "tests\api") (Join-Path $TestsRoot "api_tests")
Copy-TestsClean (Join-Path $ProjectRoot "tests\auto") (Join-Path $TestsRoot "auto_tests")
Copy-TestsClean (Join-Path $ProjectRoot "tests\performance") (Join-Path $TestsRoot "performance_tests")
Copy-Item (Join-Path $ProjectRoot "tests\conftest.py") $TestsRoot -Force

# docx documents at package root
$PlanDocx = Join-Path $RepoRoot "$Members-综合测试计划.docx"
$ReportDocx = Join-Path $RepoRoot "$Members-综合测试报告.docx"
if (Test-Path $PlanDocx) {
    Copy-Item $PlanDocx $OutDir -Force
} else {
    Write-Warning "Missing: $PlanDocx"
}
if (Test-Path $ReportDocx) {
    Copy-Item $ReportDocx $OutDir -Force
} else {
    Write-Warning "Missing: $ReportDocx"
}

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
$items = Get-ChildItem -Path $OutDir | ForEach-Object { $_.FullName }
Compress-Archive -Path $items -DestinationPath $ZipPath -Force

Write-Host "==> Package created: $ZipPath"
Write-Host "    Structure: project/, tests/, plan docx, report docx"
