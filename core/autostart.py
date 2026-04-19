"""Utilitário standalone para gerenciar autostart via linha de comando."""
import sys
import winreg
from pathlib import Path

APP_NAME = "AgendaAI"
BASE_DIR = Path(__file__).parent.parent


def _chave():
    return winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
    )


def ativar():
    cmd = f'"{sys.executable}" "{BASE_DIR / "main.py"}"'
    with _chave() as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
    print(f"Autostart ativado: {cmd}")


def desativar():
    try:
        with _chave() as key:
            winreg.DeleteValue(key, APP_NAME)
        print("Autostart desativado.")
    except FileNotFoundError:
        print("Autostart já estava desativado.")


def status():
    try:
        with _chave() as key:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
        print(f"Autostart ATIVO: {val}")
    except FileNotFoundError:
        print("Autostart INATIVO.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"ativar": ativar, "desativar": desativar, "status": status}.get(cmd, status)()
