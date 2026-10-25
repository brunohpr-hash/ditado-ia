@echo off
chcp 65001 >nul
title Ditado IA — Instalador
echo ============================================
echo   DITADO IA — instalacao no Windows
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERRO] Python nao encontrado.
    echo Baixe em https://www.python.org/downloads/ e marque
    echo a opcao "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo [1/3] Criando ambiente virtual...
python -m venv "%~dp0venv"

echo [2/3] Instalando dependencias...
"%~dp0venv\Scripts\pip" install --quiet -r "%~dp0requirements.txt"

echo [3/3] Criando atalhos (inicializacao + area de trabalho)...
set SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DitadoIA.bat
echo @echo off > "%SHORTCUT%"
echo start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py" >> "%SHORTCUT%"

rem atalho .lnk na area de trabalho (com icone proprio)
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell;" ^
  "$lnk = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Ditado IA.lnk');" ^
  "$lnk.TargetPath = '%~dp0venv\Scripts\pythonw.exe';" ^
  "$lnk.Arguments = '\"%~dp0main.py\"';" ^
  "$lnk.WorkingDirectory = '%~dp0';" ^
  "$lnk.IconLocation = '%~dp0ditado.ico';" ^
  "$lnk.Description = 'Ditado IA - ditado por voz com correcao de IA';" ^
  "$lnk.Save()"

echo.
echo ============================================
echo   Instalado! Iniciando o Ditado IA...
echo   (icone azul de microfone na bandeja,
echo    perto do relogio)
echo ============================================
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py"
exit /b 0
