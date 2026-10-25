@echo off
rem Inicia o Ditado IA (sem janela de console)
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0
