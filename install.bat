@echo off
setlocal
set "APPDIR=%~dp0"
set "APPDIR=%APPDIR:~0,-1%"

echo ============================================
echo  AES Version Manager - 一键安装
echo ============================================
echo.

echo [1/2] 开放防火墙端口 8000...
netsh advfirewall firewall delete rule name="AES Version Manager" >nul 2>&1
netsh advfirewall firewall add rule name="AES Version Manager" dir=in action=allow protocol=TCP localport=8000
echo 完成。
echo.

echo [2/2] 注册开机自启动任务...
schtasks /delete /tn "AES Version Manager" /f >nul 2>&1
schtasks /create /tn "AES Version Manager" /tr "wscript.exe \"%APPDIR%\start_server_hidden.vbs\"" /sc onlogon /ru "%USERNAME%" /f
echo 完成。
echo.

echo ============================================
echo  安装完成！
echo.
echo  团队访问地址：http://10.8.114.43:8000
echo.
echo  现在立即启动服务？(Y/N)
echo ============================================
set /p choice=
if /i "%choice%"=="Y" (
    start "" wscript.exe "%APPDIR%\start_server_hidden.vbs"
    echo 服务已在后台启动，等待约 10 秒后访问：
    echo http://10.8.114.43:8000
)
pause
