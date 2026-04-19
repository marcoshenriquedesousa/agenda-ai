"""Hook PyInstaller para incluir arquivos de modelo do Coqui TTS."""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("TTS")
hiddenimports = collect_submodules("TTS")
