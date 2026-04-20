import json
import sys
import threading
import winreg
from datetime import datetime
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from core.paths import BASE_DIR
CONFIG_PATH = BASE_DIR / "config.json"
APP_NAME = "AgendaAI"

_escuta_pausada = False


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Autostart ──────────────────────────────────────────────────────────────

def _registro_autostart():
    return winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
    )


def ativar_autostart():
    exe = sys.executable
    script = str(BASE_DIR / "main.py")
    cmd = f'"{exe}" "{script}"'
    with _registro_autostart() as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)


def desativar_autostart():
    try:
        with _registro_autostart() as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass


def autostart_ativo() -> bool:
    try:
        with _registro_autostart() as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def sincronizar_autostart():
    config = load_config()
    if config["app"].get("autostart", True):
        ativar_autostart()
    else:
        desativar_autostart()


# ── Ícone ──────────────────────────────────────────────────────────────────

def _criar_icone(pausado: bool = False) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cor = (120, 120, 120) if pausado else (80, 160, 255)
    draw.ellipse([4, 4, 60, 60], fill=cor)
    # microfone simplificado
    draw.rectangle([26, 18, 38, 38], fill=(255, 255, 255))
    draw.ellipse([22, 30, 42, 44], fill=(255, 255, 255))
    draw.line([32, 44, 32, 52], fill=(255, 255, 255), width=3)
    draw.line([24, 52, 40, 52], fill=(255, 255, 255), width=3)
    return img


# ── Briefing matinal ───────────────────────────────────────────────────────

def _fazer_briefing():
    from core.agenda import init_db, listar_eventos_hoje
    from core.llm import formatar_briefing_matinal
    from core.voice_out import falar

    init_db()
    eventos = listar_eventos_hoje()
    texto = formatar_briefing_matinal(eventos)
    print(f"[Briefing] {texto}")
    falar(texto)


def _agendar_briefing_matinal():
    config = load_config()
    if not config["app"].get("morning_briefing", True):
        return

    horario = config["app"].get("morning_briefing_time", "08:00")
    hora, minuto = map(int, horario.split(":"))

    agora = datetime.now()
    alvo = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)

    segundos = (alvo - agora).total_seconds()
    if segundos < 0:
        segundos += 86400  # amanhã

    print(f"[Briefing] Agendado para {horario} (em {int(segundos)}s)")
    threading.Timer(segundos, _loop_briefing_diario).start()


def _loop_briefing_diario():
    _fazer_briefing()
    _agendar_briefing_matinal()  # agenda o próximo dia


# ── Hotkey ─────────────────────────────────────────────────────────────────

def _ciclo_escuta():
    global _escuta_pausada
    if _escuta_pausada:
        return
    from core.assistente import ouvir_e_responder
    threading.Thread(target=ouvir_e_responder, daemon=True).start()


def _iniciar_hotkey():
    from core.voice_in import registrar_hotkey
    threading.Thread(
        target=registrar_hotkey,
        args=(_ciclo_escuta,),
        daemon=True,
    ).start()


def _iniciar_watcher_config():
    """Detecta mudanças em config.json e recarrega componentes sem reiniciar."""
    import time

    try:
        mtime_anterior = CONFIG_PATH.stat().st_mtime
    except Exception:
        return

    hotkey_anterior = load_config()["app"].get("hotkey", "ctrl+alt+a")
    stt_anterior = (
        load_config()["stt"].get("model"),
        load_config()["stt"].get("device"),
    )

    def _watch():
        nonlocal mtime_anterior, hotkey_anterior, stt_anterior
        while True:
            time.sleep(2)
            try:
                mtime = CONFIG_PATH.stat().st_mtime
                if mtime == mtime_anterior:
                    continue

                mtime_anterior = mtime
                from core.config import invalidate
                invalidate()

                novo_cfg = load_config()

                # recarrega TTS (sempre — pode ter mudado provedor, voz ou velocidade)
                from core.voice_out import recarregar_engine
                recarregar_engine()

                # recarrega STT só se mudou modelo ou device
                novo_stt = (
                    novo_cfg["stt"].get("model"),
                    novo_cfg["stt"].get("device"),
                )
                if novo_stt != stt_anterior:
                    from core.voice_in import recarregar_modelo_stt
                    recarregar_modelo_stt()
                    stt_anterior = novo_stt

                # re-registra hotkey se mudou
                novo_hotkey = novo_cfg["app"].get("hotkey", "ctrl+alt+a")
                if novo_hotkey != hotkey_anterior:
                    from core.voice_in import atualizar_hotkey
                    atualizar_hotkey(novo_hotkey)
                    hotkey_anterior = novo_hotkey

                print("[Config] Configurações aplicadas sem reiniciar.")
            except Exception as e:
                print(f"[Config] Erro no watcher: {e}")

    threading.Thread(target=_watch, daemon=True).start()


# ── Tray menu ──────────────────────────────────────────────────────────────

def _on_briefing_agora(icon, item):
    threading.Thread(target=_fazer_briefing, daemon=True).start()


def _on_toggle_pausa(icon, item):
    global _escuta_pausada
    _escuta_pausada = not _escuta_pausada
    status = "pausada" if _escuta_pausada else "ativa"
    icon.icon = _criar_icone(pausado=_escuta_pausada)
    icon.title = f"Agenda AI ({status})"
    print(f"[Tray] Escuta {status}")


def _on_settings(icon, item):
    import subprocess
    import logging
    import traceback
    try:
        exe = sys.executable
        subprocess.Popen([exe, __file__, "--settings"])
    except Exception:
        logging.error("Erro ao abrir configurações:\n" + traceback.format_exc())


def _on_escutar_agora(icon, item):
    """Escuta via menu — alternativa ao hotkey."""
    if not _escuta_pausada:
        _ciclo_escuta()


def _on_ajuda(icon, item):
    import ctypes
    config = load_config()
    hotkey = config["app"].get("hotkey", "Ctrl+Alt+A").upper()
    msg = (
        f"Como usar o Agenda AI:\n\n"
        f"1. Clique em 'Escutar agora' neste menu\n"
        f"   (ou pressione {hotkey})\n\n"
        f"2. Fale seu comando:\n"
        f'   "Anota reuniao amanha as 14h"\n'
        f'   "O que tenho hoje?"\n'
        f'   "Qual e a capital da Franca?"\n\n'
        f"3. Aguarde a resposta em voz\n\n"
        f"Icone AZUL = escutando | CINZA = pausado"
    )
    threading.Thread(
        target=lambda: ctypes.windll.user32.MessageBoxW(0, msg, "Agenda AI - Ajuda", 0x40),
        daemon=True,
    ).start()


def _on_quit(icon, item):
    icon.stop()


def _build_menu():
    return pystray.Menu(
        pystray.MenuItem("Escutar agora", _on_escutar_agora),
        pystray.MenuItem("Agenda de hoje", _on_briefing_agora),
        pystray.MenuItem(
            "Pausar escuta",
            _on_toggle_pausa,
            checked=lambda item: _escuta_pausada,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Configurações", _on_settings),
        pystray.MenuItem("Ajuda", _on_ajuda),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sair", _on_quit),
    )


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    from core.agenda import init_db
    from core.scheduler import iniciar as iniciar_scheduler

    config = load_config()
    print(f"[App] Iniciando Agenda AI (modelo: {config['llm']['model']})")

    init_db()
    sincronizar_autostart()
    iniciar_scheduler()
    _agendar_briefing_matinal()
    _iniciar_hotkey()
    _iniciar_watcher_config()

    # pré-carrega Whisper em background para não travar na primeira escuta
    from core.voice_in import pre_carregar_modelo
    pre_carregar_modelo()

    # pré-aquece TTS para eliminar delay no primeiro falar()
    from core.voice_out import _get_engine
    threading.Thread(target=_get_engine, daemon=True).start()

    # pré-aquece Ollama para evitar reload do modelo no primeiro comando
    import ollama as _ollama
    _ollama_client = _ollama.Client(host=config["llm"].get("base_url", "http://localhost:11434"))
    threading.Thread(
        target=lambda: _ollama_client.chat(
            model=config["llm"]["model"],
            messages=[{"role": "user", "content": "ok"}],
            options={"keep_alive": "30m"},
        ),
        daemon=True,
    ).start()

    # briefing imediato se for o horário certo (±5 min)
    agora = datetime.now()
    horario = config["app"].get("morning_briefing_time", "08:00")
    hora, minuto = map(int, horario.split(":"))
    diff = abs((agora.hour * 60 + agora.minute) - (hora * 60 + minuto))
    if config["app"].get("morning_briefing") and diff <= 5:
        threading.Thread(target=_fazer_briefing, daemon=True).start()

    # lança botão flutuante como subprocesso independente
    import subprocess
    subprocess.Popen([sys.executable, __file__, "--floating"])

    icon = pystray.Icon(
        name=APP_NAME,
        icon=_criar_icone(),
        title="Agenda AI",
        menu=_build_menu(),
    )
    icon.run()


if __name__ == "__main__":
    import logging
    import traceback
    import ctypes

    # modo configurações — abre só a janela de settings
    if "--settings" in sys.argv:
        from ui.settings import abrir_configuracoes
        abrir_configuracoes()
        sys.exit(0)

    # modo botão flutuante — roda só a janela flutuante
    if "--floating" in sys.argv:
        from ui.floating_button import main as floating_main
        floating_main()
        sys.exit(0)

    log_path = BASE_DIR / "agenda_ai.log"
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # garante instância única via mutex do Windows
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "AgendaAI_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        logging.info("Outra instancia ja esta rodando. Encerrando.")
        sys.exit(0)

    try:
        logging.info("Iniciando Agenda AI...")
        main()
    except Exception:
        logging.error("Erro fatal:\n" + traceback.format_exc())
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Erro ao iniciar:\n\n{traceback.format_exc()}",
            "Agenda AI — Erro",
            0x10,
        )
