@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
py launcher.py
if errorlevel 1 pause
