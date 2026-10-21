@echo off
cd /d "%~dp0"
echo Starting KVM Host on Windows...
echo Failsafes: Press ScrollLock to toggle or Pause to emergency ungrab.
.venv\Scripts\python.exe host_windows.py %*
pause
