@echo off
echo ================================================
echo  Agenda AI — Instalacao de dependencias
echo ================================================

cd /d %~dp0..

echo.
echo Instalando pacotes Python...
pip install -r requirements.txt

echo.
echo ================================================
echo  Pronto! Proximos passos:
echo.
echo  1. Gravar voz de referencia:
echo     python tools\gravar_voz_referencia.py
echo.
echo  2. Testar TTS:
echo     python core\voice_out.py
echo.
echo  3. Testar STT:
echo     python core\voice_in.py
echo.
echo  4. Iniciar o app:
echo     python main.py
echo ================================================
pause
