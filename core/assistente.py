from datetime import datetime
from core.voice_in import escutar
from core.voice_out import falar
from core.llm import interpretar_comando, formatar_agenda_para_fala, formatar_lembretes_para_fala, responder_livremente
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

    elif acao in ("cancelar_evento", "deletar_evento"):
        titulo_busca = resultado.get("titulo", "").strip()
        candidatos = db.buscar_eventos_por_titulo(titulo_busca)
        if not candidatos:
            return "Não encontrei nenhum evento com esse nome."
        for e in candidatos:
            db.deletar_evento(e.id)
        if len(candidatos) == 1:
            return f"Evento removido: {candidatos[0].titulo}."
        return f"{len(candidatos)} eventos removidos."

    elif acao == "editar_evento":
        titulo_busca = resultado.get("titulo_atual", "").strip()
        candidatos = db.buscar_eventos_por_titulo(titulo_busca)
        if not candidatos:
            return "Não encontrei nenhum evento com esse nome para editar."
        evento = candidatos[0]
        novo_titulo = resultado.get("novo_titulo") or None
        nova_data_hora = None
        nova_data_str = resultado.get("nova_data_hora")
        if nova_data_str and nova_data_str != "null":
            try:
                nova_data_hora = datetime.strptime(nova_data_str, "%Y-%m-%d %H:%M")
            except ValueError:
                pass
        nova_descricao = resultado.get("nova_descricao") or None
        db.editar_evento(evento.id, titulo=novo_titulo, data_hora=nova_data_hora, descricao=nova_descricao)
        nome_final = novo_titulo or evento.titulo
        if nova_data_hora:
            return f"Evento '{nome_final}' atualizado para {nova_data_hora.strftime('%d/%m às %H:%M')}."
        return f"Evento '{nome_final}' atualizado."

    elif acao == "criar_lembrete":
        texto_lembrete = resultado.get("texto", "").strip()
        if not texto_lembrete:
            return "Não entendi o que devo lembrar. Pode repetir?"
        data_limite = None
        data_str = resultado.get("data_limite")
        if data_str:
            try:
                data_limite = datetime.strptime(data_str, "%Y-%m-%d")
            except ValueError:
                pass
        lembrete = db.criar_lembrete(texto_lembrete, data_limite)
        if data_limite:
            return f"Anotado! Vou te lembrar de: {lembrete.texto} até {data_limite.strftime('%d/%m')}."
        return f"Anotado! Vou te lembrar sempre: {lembrete.texto}."

    elif acao == "remover_lembrete":
        texto_busca = resultado.get("texto", "").strip()
        candidatos = db.buscar_lembretes_por_texto(texto_busca)
        if not candidatos:
            return "Não encontrei nenhum lembrete com esse assunto."
        for l in candidatos:
            db.remover_lembrete_por_id(l.id)
        if len(candidatos) == 1:
            return f"Lembrete removido: {candidatos[0].texto}."
        return f"{len(candidatos)} lembretes removidos."

    elif acao == "editar_lembrete":
        texto_busca = resultado.get("texto_atual", "").strip()
        candidatos = db.buscar_lembretes_por_texto(texto_busca)
        if not candidatos:
            return "Não encontrei nenhum lembrete com esse assunto para editar."
        lembrete = candidatos[0]
        novo_texto = resultado.get("novo_texto") or None
        nova_data_limite = None
        nova_data_str = resultado.get("nova_data_limite")
        if nova_data_str and nova_data_str != "null":
            try:
                nova_data_limite = datetime.strptime(nova_data_str, "%Y-%m-%d")
            except ValueError:
                pass
        db.editar_lembrete(lembrete.id, texto=novo_texto, data_limite=nova_data_limite)
        texto_final = novo_texto or lembrete.texto
        return f"Lembrete atualizado: {texto_final}."

    elif acao == "listar_lembretes":
        lembretes = db.listar_lembretes_ativos()
        return formatar_lembretes_para_fala(lembretes)

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
