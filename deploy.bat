@echo off
echo Deploying...

for %%F in (backend\main.py) do set SIZE=%%~zF
if "%SIZE%"=="0" (
    echo ABORT: backend\main.py is empty, refusing to deploy
    pause
    exit /b 1
)
if not defined SIZE (
    echo ABORT: backend\main.py not found
    pause
    exit /b 1
)

scp -i %USERPROFILE%\.ssh\id_rsa backend\main.py root@10.21.163.215:/opt/aes-version-manager/backend/main.py
if errorlevel 1 goto fail
echo backend ok

for %%F in (frontend\index.html) do set SIZE2=%%~zF
if "%SIZE2%"=="0" (
    echo ABORT: frontend\index.html is empty, refusing to deploy
    pause
    exit /b 1
)

scp -i %USERPROFILE%\.ssh\id_rsa frontend\index.html root@10.21.163.215:/opt/aes-version-manager/frontend/index.html
if errorlevel 1 goto fail
echo frontend ok
ssh -i %USERPROFILE%\.ssh\id_rsa root@10.21.163.215 "systemctl restart aes-version-manager"
echo Done!
goto end
:fail
echo FAILED - check SSH connection
:end
pause
