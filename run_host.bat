@echo off
cd /d "%~dp0"
echo Starting KVM Host on Windows...
echo Failsafes: Press ScrollLock to toggle or Pause to emergency ungrab.
set PYTHONPATH=%~dp0src
.venv\Scripts\python.exe -m buftogether.host %*
pause
