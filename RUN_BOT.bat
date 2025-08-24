@echo off
REM Force Windows console and Python to use UTF-8 to avoid decode errors
chcp 65001 >NUL
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM (Optional) Activate venv if you use one
REM call .venv\Scripts\activate

python bot.py
pause
