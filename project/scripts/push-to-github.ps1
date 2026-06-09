# 将代码推送到 GitHub，供 Render 部署使用
# 用法: .\scripts\push-to-github.ps1 -RepoUrl "https://github.com/你的用户名/仓库名.git"

param(
    [Parameter(Mandatory = $true)]
    [string]$RepoUrl
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

Write-Host "==> 当前分支与最近提交"
git status -sb
git log -1 --oneline

if (-not (git remote get-url origin 2>$null)) {
    git remote add origin $RepoUrl
    Write-Host "==> 已添加 remote: origin -> $RepoUrl"
} else {
    git remote set-url origin $RepoUrl
    Write-Host "==> 已更新 remote: origin -> $RepoUrl"
}

Write-Host "==> 推送到 GitHub..."
git push -u origin main

Write-Host ""
Write-Host "推送完成。请到 Render 创建 Web Service："
Write-Host "  https://dashboard.render.com"
Write-Host "  Root Directory: project"
Write-Host "  详见 project/DEPLOY.md"
