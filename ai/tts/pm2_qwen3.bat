@echo off
chcp 65001 >nul
rem pm2 가 호출하는 런처 — start_tts.bat 과 달리 taskkill/pause 없음.
rem  (프로세스 수명은 pm2 가 관리하므로 여기서 죽이거나 멈추면 안 됨)
cd /d C:\Rainbow_Bridge\Rainbow-Bridge
conda run --no-capture-output -n qwen3-tts python -u ai\tts\server.py
