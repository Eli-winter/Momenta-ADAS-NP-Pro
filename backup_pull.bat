@echo off
setlocal

set BACKUP_DIR=C:\Users\eli.mao\Desktop\aes-version-manager\backend\backups
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

:: 生成时间戳 YYYYMMDD_HHMMSS
for /f "tokens=1-3 delims=/-" %%a in ("%date%") do (
    set YMD=%%a%%b%%c
)
for /f "tokens=1-3 delims=:." %%a in ("%time: =0%") do (
    set HMS=%%a%%b%%c
)
set TIMESTAMP=%YMD%_%HMS%

set TARGET=%BACKUP_DIR%\data_%TIMESTAMP%.json

echo [%date% %time%] 从服务器拉取备份...
scp -i "%USERPROFILE%\.ssh\id_rsa" -o StrictHostKeyChecking=no root@10.21.163.215:/opt/aes-version-manager/backend/data.json "%TARGET%"

if %errorlevel% == 0 (
    echo [%date% %time%] 备份成功: %TARGET%
) else (
    echo [%date% %time%] 备份失败，请检查网络或 SSH 连接
)

:: 清理 30 天前的本地备份
forfiles /p "%BACKUP_DIR%" /m "data_*.json" /d -30 /c "cmd /c del @path" 2>nul

endlocal
