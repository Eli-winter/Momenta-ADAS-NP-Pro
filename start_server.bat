@echo off
cd /d "%~dp0"
set CHAT_ID_OVERRIDE=oc_43fc8baacc8695fcc2854516af859179
set KEYCLOAK_USERNAME=cp_system_gpt
set KEYCLOAK_PASSWORD=csg_2025
set FEISHU_USER_UNION_ID=on_35098d6a6e132b5e8008fb2481b982cb
uvicorn backend.main:app --host 0.0.0.0 --port 8000
