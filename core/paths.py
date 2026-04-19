import sys
from pathlib import Path


def get_base_dir() -> Path:
    """Retorna o diretório base correto em dev e no .exe empacotado."""
    if getattr(sys, "frozen", False):
        # rodando como .exe — usa o diretório do executável
        return Path(sys.executable).parent
    # rodando em dev — usa a raiz do projeto
    return Path(__file__).parent.parent


BASE_DIR = get_base_dir()
