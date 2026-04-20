import threading
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from core.config import get_config

_scheduler: BackgroundScheduler | None = None
_eventos_notificados: set[int] = set()


def _notificar(evento_id: int, titulo: str, hora_str: str):
    """Dispara notificação visual + TTS para um evento."""
    from core.voice_out import falar

    config = get_config()
    minutos = config["notifications"]["reminder_minutes_before"]

    texto = f"Lembrete: {titulo} em {minutos} minutos, às {hora_str}."
    print(f"[Scheduler] {texto}")

    # notificação Windows
    try:
        from winotify import Notification, audio

        toast = Notification(
            app_id="Agenda AI",
            title=f"⏰ {titulo}",
            msg=f"Começa às {hora_str} — em {minutos} minutos",
            duration="short",
        )
        if config["notifications"].get("sound", True):
            toast.set_audio(audio.Reminder, loop=False)
        toast.show()
    except Exception as e:
        print(f"[Scheduler] Erro na notificação visual: {e}")

    # TTS fala o lembrete
    threading.Thread(target=falar, args=(texto,), daemon=True).start()

    _eventos_notificados.add(evento_id)


def _verificar_eventos():
    """Executado a cada minuto — agenda notificações para eventos próximos."""
    from core.agenda import listar_proximos_eventos

    config = get_config()
    antecedencia = config["notifications"]["reminder_minutes_before"]

    eventos = listar_proximos_eventos(limite=20)
    agora = datetime.now()

    for evento in eventos:
        if evento.id in _eventos_notificados:
            continue

        janela_inicio = evento.data_hora - timedelta(minutes=antecedencia + 1)
        janela_fim = evento.data_hora - timedelta(minutes=antecedencia - 1)

        if janela_inicio <= agora <= janela_fim:
            hora_str = evento.data_hora.strftime("%H:%M")
            _scheduler.add_job(
                _notificar,
                trigger=DateTrigger(run_date=datetime.now()),
                args=[evento.id, evento.titulo, hora_str],
                id=f"notif_{evento.id}",
                replace_existing=True,
            )


def _notificar_lembrete(lembrete_id: int, texto: str):
    """Dispara notificação visual + TTS para um lembrete recorrente."""
    from core.voice_out import falar
    from core.agenda import atualizar_notificacao_lembrete

    mensagem = f"Lembrete: {texto}"
    print(f"[Scheduler] {mensagem}")

    try:
        from winotify import Notification, audio

        toast = Notification(
            app_id="Agenda AI",
            title="📌 Lembrete",
            msg=texto,
            duration="short",
        )
        config = get_config()
        if config["notifications"].get("sound", True):
            toast.set_audio(audio.Reminder, loop=False)
        toast.show()
    except Exception as e:
        print(f"[Scheduler] Erro na notificação de lembrete: {e}")

    threading.Thread(target=falar, args=(mensagem,), daemon=True).start()
    atualizar_notificacao_lembrete(lembrete_id)


def _verificar_lembretes():
    """Executado a cada 3 horas — anuncia lembretes ativos que não foram notificados recentemente."""
    from core.agenda import listar_lembretes_ativos
    from datetime import timedelta

    lembretes = listar_lembretes_ativos()
    agora = datetime.now()

    for lembrete in lembretes:
        # só notifica se nunca foi notificado ou se faz mais de 3h desde a última vez
        if lembrete.ultima_notificacao is None or (agora - lembrete.ultima_notificacao) >= timedelta(hours=3):
            _scheduler.add_job(
                _notificar_lembrete,
                trigger=DateTrigger(run_date=agora),
                args=[lembrete.id, lembrete.texto],
                id=f"lembrete_{lembrete.id}_{int(agora.timestamp())}",
                replace_existing=False,
            )


def _resetar_notificados():
    """Limpa set de notificados todo dia à meia-noite."""
    _eventos_notificados.clear()
    print("[Scheduler] Set de notificações resetado para o novo dia.")


def iniciar():
    """Inicia o scheduler em background. Chamar uma vez no main."""
    global _scheduler

    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")

    # verifica eventos a cada minuto
    _scheduler.add_job(_verificar_eventos, "interval", minutes=1, id="verificar_eventos")

    # anuncia lembretes recorrentes a cada 3 horas
    _scheduler.add_job(_verificar_lembretes, "interval", hours=3, id="verificar_lembretes")

    # reseta notificados à meia-noite
    _scheduler.add_job(_resetar_notificados, "cron", hour=0, minute=0, id="reset_notificados")

    _scheduler.start()
    print("[Scheduler] Iniciado — verificando eventos a cada minuto.")


def parar():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[Scheduler] Parado.")


def agendar_notificacao_imediata(evento_id: int, titulo: str, hora_str: str):
    """Agenda notificação no tempo exato do lembrete (usado ao criar evento)."""
    if not _scheduler or not _scheduler.running:
        return

    config = get_config()
    antecedencia = config["notifications"]["reminder_minutes_before"]

    from core.agenda import listar_proximos_eventos
    for e in listar_proximos_eventos(limite=50):
        if e.id == evento_id:
            disparo = e.data_hora - timedelta(minutes=antecedencia)
            if disparo > datetime.now():
                _scheduler.add_job(
                    _notificar,
                    trigger=DateTrigger(run_date=disparo),
                    args=[evento_id, titulo, hora_str],
                    id=f"notif_{evento_id}",
                    replace_existing=True,
                )
                print(f"[Scheduler] Notificação agendada: '{titulo}' às {disparo.strftime('%H:%M')}")
            break
