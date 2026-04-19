from datetime import datetime
from core.voice_in import escutar
from core.voice_out import falar
from core.llm import interpretar_comando, formatar_agenda_para_fala, responder_livremente
from core import agenda as db


def processar_comando(texto: str) -> str:
    """Interpreta o texto e executa a ação correspondente. Retorna a resposta em texto."""
    if not texto.strip():
        return "Não ouvi nada. Tente novamente."

    resultado = interpretar_comando(texto)
    acao = resultado.get("acao")

    if acao == "criar_evento":
        try:
            data_hora = datetime.strptime(resultado["data_hora"], "%Y-%m-%d %H:%M")
            evento = db.criar_evento(
                titulo=resultado["titulo"],
                data_hora=data_hora,
                descricao=resultado.get("descricao", ""),
                lembrete_minutos=resultado.get("lembrete_minutos", 15),
            )
            hora = data_hora.strftime("%H:%M")
            data = data_hora.strftime("%d/%m")

            # agenda notificação imediata no scheduler
            try:
                from core.scheduler import agendar_notificacao_imediata
                agendar_notificacao_imediata(evento.id, evento.titulo, hora)
            except Exception:
                pass

            return f"Anotado! {evento.titulo} em {data} às {hora}."
        except (KeyError, ValueError):
            return "Não consegui entender a data ou hora do evento. Pode repetir?"

    elif acao == "consultar_eventos":
        periodo = resultado.get("periodo", "hoje")
        if periodo == "hoje":
            eventos = db.listar_eventos_hoje()
            return formatar_agenda_para_fala(eventos)
        else:
            eventos = db.listar_proximos_eventos(limite=5)
            return formatar_agenda_para_fala(eventos)

    elif acao == "cancelar_evento":
        return "Cancelamento de eventos ainda não implementado. Em breve!"

    elif acao == "nao_entendido":
        return responder_livremente(texto)

    return responder_livremente(texto)


def ouvir_e_responder(continuo: bool = False):
    """Ciclo completo: escuta → processa → fala. Se continuo=True, repete automaticamente."""
    import traceback
    try:
        print("[Assistente] Escutando...")
        import winsound
        winsound.Beep(1000, 80)

        texto = escutar(duracao_max=20)
        print(f"[Assistente] Transcrito: '{texto}'")

        if not texto.strip():
            falar("Nao ouvi nada.")
        else:
            resposta = processar_comando(texto)
            print(f"[Assistente] Resposta: '{resposta}'")
            falar(resposta)

    except Exception:
        print("[Assistente] ERRO: " + traceback.format_exc())

    if continuo:
        ouvir_e_responder(continuo=True)


if __name__ == "__main__":
    db.init_db()
    print("Testando ciclo completo: voz > LLM > banco > voz")
    print("Fale um comando após o prompt...\n")
    ouvir_e_responder()
