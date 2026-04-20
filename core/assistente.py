from datetime import datetime, timedelta
from core.voice_in import escutar
from core.voice_out import falar
from core.llm import interpretar_comando, formatar_agenda_para_fala, formatar_lembretes_para_fala, responder_livremente, corrigir_texto, corrigir_transcricao
from core import agenda as db


def processar_comando(texto: str) -> str:
    """Interpreta o texto e executa a ação correspondente. Retorna a resposta em texto."""
    if not texto.strip():
        return "Não ouvi nada. Tente novamente."

    texto = corrigir_transcricao(texto)
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
        agora = datetime.now()

        if periodo == "amanha":
            eventos = db.listar_eventos_amanha()
            prefixo = "Amanhã"
            incluir_data = False
        elif periodo == "semana":
            inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            fim = inicio + timedelta(days=7)
            eventos = db.listar_eventos_periodo(inicio, fim)
            prefixo = "Esta semana"
            incluir_data = True
        elif periodo == "mes":
            inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            fim = inicio + timedelta(days=30)
            eventos = db.listar_eventos_periodo(inicio, fim)
            prefixo = "Nos próximos 30 dias"
            incluir_data = True
        elif periodo == "proximos":
            eventos = db.listar_proximos_eventos(limite=10)
            prefixo = "Próximos eventos"
            incluir_data = True
        elif len(periodo) == 10 and periodo[4] == "-":
            # data específica no formato YYYY-MM-DD
            try:
                dia = datetime.strptime(periodo, "%Y-%m-%d")
                inicio = dia.replace(hour=0, minute=0, second=0, microsecond=0)
                fim = inicio + timedelta(days=1)
                eventos = db.listar_eventos_periodo(inicio, fim)
                nome_dia = ["segunda-feira", "terça-feira", "quarta-feira",
                            "quinta-feira", "sexta-feira", "sábado", "domingo"][dia.weekday()]
                prefixo = f"Na {nome_dia}, dia {dia.strftime('%d/%m')}"
                incluir_data = False
            except ValueError:
                eventos = db.listar_eventos_hoje()
                prefixo = "Hoje"
                incluir_data = False
        else:
            eventos = db.listar_eventos_hoje()
            prefixo = "Hoje"
            incluir_data = False

        if not eventos:
            return f"{prefixo} você não tem nenhum compromisso agendado."
        return formatar_agenda_para_fala(eventos, incluir_data=incluir_data)

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

    elif acao == "limpar_agenda":
        periodo = resultado.get("periodo", "hoje")
        alvo = resultado.get("alvo", "eventos")
        agora = datetime.now()
        total = 0

        if alvo in ("eventos", "tudo"):
            if periodo == "hoje":
                inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
                fim = inicio + timedelta(days=1)
                label = "de hoje"
            elif periodo == "amanha":
                inicio = (agora + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                fim = inicio + timedelta(days=1)
                label = "de amanhã"
            elif periodo == "semana":
                inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
                fim = inicio + timedelta(days=7)
                label = "desta semana"
            elif periodo == "mes":
                inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
                fim = inicio + timedelta(days=30)
                label = "deste mês"
            else:  # tudo
                inicio = agora.replace(hour=0, minute=0, second=0, microsecond=0)
                fim = inicio + timedelta(days=3650)
                label = "futuros"

            total += db.deletar_eventos_periodo(inicio, fim)

        if alvo in ("lembretes", "tudo"):
            total += db.deletar_todos_lembretes()

        if total == 0:
            if alvo == "lembretes":
                return "Não havia lembretes ativos para remover."
            return f"Não havia eventos {label} para remover."

        if alvo == "lembretes":
            return f"Removi {total} lembrete{'s' if total > 1 else ''}."
        if alvo == "tudo":
            return f"Limpei {total} item{'ns' if total > 1 else ''} da sua agenda e lembretes."
        return f"Removi {total} evento{'s' if total > 1 else ''} {label}."

    elif acao == "corrigir_textos":
        corrigidos = 0

        eventos = db.listar_proximos_eventos(limite=50)
        for evento in eventos:
            titulo_novo = corrigir_texto(evento.titulo)
            descricao_nova = corrigir_texto(evento.descricao) if evento.descricao else None
            if titulo_novo != evento.titulo or descricao_nova != evento.descricao:
                db.editar_evento(evento.id, titulo=titulo_novo, descricao=descricao_nova)
                corrigidos += 1

        lembretes = db.listar_lembretes_ativos()
        for lembrete in lembretes:
            texto_novo = corrigir_texto(lembrete.texto)
            if texto_novo != lembrete.texto:
                db.editar_lembrete(lembrete.id, texto=texto_novo)
                corrigidos += 1

        if corrigidos == 0:
            return "Todos os textos já estão corretos, não precisei alterar nada."
        return f"Corrigi {corrigidos} item{'ns' if corrigidos > 1 else ''}. Sua agenda está organizada."

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
