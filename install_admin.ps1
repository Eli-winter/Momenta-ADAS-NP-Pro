$AppDir = "C:\Users\eli.mao\Desktop\aes-version-manager"
$VbsPath = "$AppDir\start_server_hidden.vbs"

Write-Host "=== AES Version Manager 安装 ===" -ForegroundColor Cyan

# 1. 防火墙
Write-Host "[1/2] 开放端口 8000..." -ForegroundColor Yellow
netsh advfirewall firewall delete rule name="AES Version Manager" 2>$null | Out-Null
netsh advfirewall firewall add rule name="AES Version Manager" dir=in action=allow protocol=TCP localport=8000
Write-Host "防火墙规则已添加。" -ForegroundColor Green

# 2. 开机自启（Task Scheduler，用户登录时运行）
Write-Host "[2/2] 注册开机自启任务..." -ForegroundColor Yellow
$Action  = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$VbsPath`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "AES Version Manager" -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Highest -Force
Write-Host "开机自启任务已注册。" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " 安装完成！团队访问地址：" -ForegroundColor Cyan
Write-Host " http://10.8.114.43:8000" -ForegroundColor White
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 3. 立即启动
Write-Host "正在启动服务..." -ForegroundColor Yellow
Start-Process wscript.exe -ArgumentList "`"$VbsPath`""
Write-Host "服务已在后台启动，10 秒后访问 http://10.8.114.43:8000" -ForegroundColor Green
Write-Host ""
Read-Host "按 Enter 关闭"
