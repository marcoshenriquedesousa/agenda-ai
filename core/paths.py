import sys
from pathlib import Path


def get_base_dir() -> Path:
    """Retorna o diretório base correto em dev e no .exe empacotado."""
    if getattr(sys, "frozen", False):
        # PyInstaller 6+ extrai dados em sys._MEIPASS (_internal/)
        return Path(sys._MEIPASS)
    return Path(__file__).parent.parent


BASE_DIR = get_base_dir()
