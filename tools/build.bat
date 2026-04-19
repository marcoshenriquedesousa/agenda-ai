@echo off
echo ================================================
echo  Agenda AI — Build PyInstaller
echo ================================================

cd /d %~dp0..

echo.
echo [1/4] Gerando icone...
python tools\gerar_icone.py
if errorlevel 1 ( echo ERRO ao gerar icone && pause && exit /b 1 )

echo.
echo [2/4] Instalando dependencias de build...
pip install pyinstaller --quiet
if errorlevel 1 ( echo ERRO no pip && pause && exit /b 1 )

echo.
echo [3/4] Compilando executavel...
pyinstaller agenda_ai.spec --clean --noconfirm
if errorlevel 1 ( echo ERRO no PyInstaller && pause && exit /b 1 )

echo.
echo [4/4] Copiando arquivos de dados...
if not exist "dist\AgendaAI\data" mkdir "dist\AgendaAI\data"
if not exist "dist\AgendaAI\assets\voice_reference" mkdir "dist\AgendaAI\assets\voice_reference"

echo.
echo ================================================
echo  Build concluido!
echo  Executavel: dist\AgendaAI\AgendaAI.exe
echo ================================================
pause
