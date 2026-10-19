@echo off
rem Windows: de dois cliques neste arquivo para abrir o assistente.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app.py %*
  goto :fim
)
where python >nul 2>nul
if %errorlevel%==0 (
  python app.py %*
  goto :fim
)
echo Python nao encontrado.
echo Use o executavel pronto (SGP-Cariap-windows.exe) ou instale o Python em
echo https://www.python.org/downloads/  marcando "Add python.exe to PATH".
pause
:fim
