@echo off
cd /d "%~dp0backend"
call conda activate Qwen
python main.py
pause
