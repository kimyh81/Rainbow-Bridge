@echo off
chcp 65001 >nul
echo 기존 TTS 서버 종료 중...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8002') do taskkill /PID %%a /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8003') do taskkill /PID %%a /F 2>nul
timeout /t 2 >nul
echo TTS 서버 시작 중... (콘솔 표시 + ai\tts\tts.log 누적 저장)
rem 콘솔에 그대로 보이면서 ai\tts\tts.log 에도 저장(분석기 analyze_tts_log.py 용).
rem  - pwsh(7) 고정: Windows PowerShell 5.1 의 Tee-Object 는 UTF-16 로 써서 분석기가 깨짐.
rem    pwsh 7 은 UTF-8(BOM 없음)로 저장해 안전.
rem  - python -u : 파이프 버퍼링 방지(실시간 반영).
rem  - -Append : 이전 로그 안 지우고 계속 누적(파일 커지면 직접 비우면 됨).
pwsh -NoProfile -Command "conda run --no-capture-output -n qwen3-tts python -u ai/tts/server.py 2>&1 | Tee-Object -FilePath ai\tts\tts.log -Append"
pause