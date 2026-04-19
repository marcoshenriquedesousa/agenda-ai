# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec para Agenda AI.
Gera um executável standalone para Windows.

Uso:
    pyinstaller agenda_ai.spec
"""

import sys
from pathlib import Path

BASE = Path(SPECPATH)

a = Analysis(
    [str(BASE / "main.py")],
    pathex=[str(BASE)],
    binaries=[],
    datas=[
        # arquivos de dados necessários em runtime
        (str(BASE / "config.json"), "."),
        (str(BASE / "assets"), "assets"),
    ],
    hiddenimports=[
        # ollama
        "ollama",
        # faster-whisper
        "faster_whisper",
        "faster_whisper.transcribe",
        # TTS / XTTS
        "TTS",
        "TTS.api",
        "TTS.tts.configs.xtts_config",
        "TTS.tts.models.xtts",
        # sounddevice / soundfile
        "sounddevice",
        "soundfile",
        # PyQt6
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        # scheduler
        "apscheduler",
        "apscheduler.schedulers.background",
        "apscheduler.triggers.date",
        "apscheduler.triggers.cron",
        # notificações
        "winotify",
        # hotkey
        "keyboard",
        # tray
        "pystray",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        # sqlalchemy
        "sqlalchemy",
        "sqlalchemy.dialects.sqlite",
    ],
    hookspath=[str(BASE / "build_hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "notebook",
        "IPython",
        "pytest",
        "tkinter",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AgendaAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # sem janela de console
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(BASE / "assets" / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AgendaAI",
)
