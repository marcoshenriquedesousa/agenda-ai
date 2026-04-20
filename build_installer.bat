@echo off
setlocal enabledelayedexpansion
title Agenda AI — Build Installer

echo.
echo ========================================
echo   Agenda AI — Build do Instalador
echo ========================================
echo.

:: ── 1. Verifica PyInstaller ──────────────────────────────────────────────────
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [ERRO] PyInstaller nao encontrado. Instale com:
    echo        pip install pyinstaller
    pause & exit /b 1
)

:: ── 2. Verifica Inno Setup ───────────────────────────────────────────────────
set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)

if %ISCC%=="" (
    echo [ERRO] Inno Setup 6 nao encontrado.
    echo        Baixe em: https://jrsoftware.org/isinfo.php
    pause & exit /b 1
)

:: ── 3. PyInstaller ───────────────────────────────────────────────────────────
echo [1/2] Gerando executavel com PyInstaller...
pyinstaller agenda_ai.spec --noconfirm
if errorlevel 1 (
    echo [ERRO] PyInstaller falhou.
    pause & exit /b 1
)
echo       OK — dist\AgendaAI pronto.
echo.

:: ── 4. Remove arquivos de desenvolvimento do dist ───────────────────────────
echo       Limpando arquivos de dev do dist...
if exist "dist\AgendaAI\agenda_ai.log" del /q "dist\AgendaAI\agenda_ai.log"
if exist "dist\AgendaAI\data\agenda.db"   del /q "dist\AgendaAI\data\agenda.db"

:: ── 5. Inno Setup ────────────────────────────────────────────────────────────
echo [2/2] Gerando instalador com Inno Setup...
%ISCC% "installer\agenda_ai.iss"
if errorlevel 1 (
    echo [ERRO] Inno Setup falhou.
    pause & exit /b 1
)

echo.
echo ========================================
echo   Instalador gerado com sucesso!
echo   installer\AgendaAI_Setup_1.0.0.exe
echo ========================================
echo.
pause
