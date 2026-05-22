@echo off
echo 正在开放端口 8000...
netsh advfirewall firewall add rule name="AES Version Manager" dir=in action=allow protocol=TCP localport=8000
echo.
echo 完成！端口 8000 已对内网开放。
pause
