# 一键启动：本地 Flask + 内网穿透（localtunnel）
# 用法: 在 project 目录下执行  .\scripts\start-tunnel.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $ProjectRoot

# 若 5000 已被占用，先结束旧进程
$conn = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    Write-Host "==> 端口 5000 已被占用，正在重启服务..."
    Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Write-Host "==> 启动 Flask（后台）..."
$python = Join-Path $ProjectRoot "venv\Scripts\python.exe"
Start-Process -WindowStyle Hidden -FilePath $python -ArgumentList "backend/app.py" -WorkingDirectory $ProjectRoot
Start-Sleep -Seconds 3

Write-Host "==> 本机访问: http://127.0.0.1:5000"
Write-Host "==> 正在创建公网临时链接（localtunnel）..."
Write-Host "    下方会显示 your url is: https://xxxx.loca.lt"
Write-Host "    首次打开可能需点击 Continue 或输入本机 IP"
Write-Host ""

npx --yes localtunnel --port 5000
