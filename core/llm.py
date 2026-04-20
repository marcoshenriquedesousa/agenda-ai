import json
import re
from datetime import datetime

import ollama

from core.config import get_config


SYSTEM_PROMPT = """Você é {nome}, um assistente de agenda pessoal. Hoje é {hoje}, hora atual {hora}.

Responda com um JSON usando um destes formatos:

criar_evento — marcar, anotar, agendar (com data/hora específica):
{{"acao": "criar_evento", "titulo": "...", "data_hora": "YYYY-MM-DD HH:MM", "descricao": "...", "lembrete_minutos": 15}}

consultar_eventos — o que tenho hoje/amanhã/semana:
{{"acao": "consultar_eventos", "periodo": "hoje"}}

deletar_evento — excluir, deletar, remover, cancelar evento específico:
{{"acao": "deletar_evento", "titulo": "..."}}

editar_evento — alterar, mudar, reagendar, atualizar evento (informe só os campos que mudam):
{{"acao": "editar_evento", "titulo_atual": "...", "novo_titulo": "... ou null", "nova_data_hora": "YYYY-MM-DD HH:MM ou null", "nova_descricao": "... ou null"}}

criar_lembrete — me lembre sempre, me avisa, não deixa esquecer, preciso lembrar (sem data/hora fixa):
{{"acao": "criar_lembrete", "texto": "...", "data_limite": "YYYY-MM-DD ou null"}}

remover_lembrete — já fiz, pode remover lembrete, não precisa mais lembrar, já paguei, já resolvi:
{{"acao": "remover_lembrete", "texto": "..."}}

editar_lembrete — alterar, mudar, corrigir lembrete existente:
{{"acao": "editar_lembrete", "texto_atual": "...", "novo_texto": "... ou null", "nova_data_limite": "YYYY-MM-DD ou null"}}

listar_lembretes — quais são meus lembretes, o que preciso lembrar, minhas pendências:
{{"acao": "listar_lembretes"}}

nao_entendido — fora do escopo de agenda:
{{"acao": "nao_entendido", "mensagem": "resposta curta em português"}}

Regras: datas relativas → YYYY-MM-DD; sem data → hoje se hora não passou, senão amanhã; "manhã"=09:00, "tarde"=14:00, "noite"=19:00.
Diferença entre criar_evento e criar_lembrete: evento tem data/hora específica (reunião às 14h). Lembrete é recorrente/sem horário fixo (pagar boleto, tomar remédio).
Para editar/deletar: use titulo_atual/texto_atual para identificar o item — não precisa ser exato, apenas palavras-chave suficientes."""


def _montar_prompt() -> str:
    agora = datetime.now()
    nome = get_config()["app"].get("assistant_name", "Aria")
    return SYSTEM_PROMPT.format(
        nome=nome,
        hoje=agora.strftime("%Y-%m-%d (%A)"),
        hora=agora.strftime("%H:%M"),
    )


def _extrair_json(texto: str) -> dict:
    texto = texto.strip()
    # remove blocos markdown se o modelo insistir
    texto = re.sub(r"```(?:json)?", "", texto).strip()
    return json.loads(texto)


def _cliente() -> ollama.Client:
    config = get_config()["llm"]
    return ollama.Client(host=config.get("base_url", "http://localhost:11434"))


def interpretar_comando(texto: str) -> dict:
    """Envia o comando de voz para o Ollama e retorna o JSON interpretado."""
    config = get_config()["llm"]

    resposta = _cliente().chat(
        model=config["model"],
        format="json",
        options={"temperature": config.get("temperature", 0.1), "keep_alive": "30m"},
        messages=[
            {"role": "system", "content": _montar_prompt()},
            {"role": "user", "content": texto},
        ],
    )

    conteudo = resposta["message"]["content"]

    try:
        return _extrair_json(conteudo)
    except json.JSONDecodeError:
        return {"acao": "nao_entendido", "mensagem": "Não consegui entender o comando."}


def responder_livremente(texto: str) -> str:
    """Envia pergunta geral para o Ollama responder em linguagem natural."""
    cfg = get_config()
    config = cfg["llm"]
    nome = cfg["app"].get("assistant_name", "Aria")

    resposta = _cliente().chat(
        model=config["model"],
        options={"temperature": 0.7, "keep_alive": "30m"},
        messages=[
            {
                "role": "system",
                "content": (
                    f"Você é {nome}, uma assistente pessoal simpática e objetiva. "
                    "Responda em português, de forma curta e direta — máximo 2 frases. "
                    "Não mencione que é uma IA."
                ),
            },
            {"role": "user", "content": texto},
        ],
    )
    return resposta["message"]["content"].strip()


def formatar_agenda_para_fala(eventos: list) -> str:
    """Converte lista de eventos em texto natural para o TTS falar."""
    if not eventos:
        return "Você não tem compromissos agendados."

    if len(eventos) == 1:
        e = eventos[0]
        hora = e.data_hora.strftime("%H:%M")
        return f"Você tem um compromisso: {e.titulo} às {hora}."

    partes = []
    for e in eventos:
        hora = e.data_hora.strftime("%H:%M")
        partes.append(f"{e.titulo} às {hora}")

    lista = ", ".join(partes[:-1]) + f" e {partes[-1]}"
    return f"Você tem {len(eventos)} compromissos: {lista}."


def formatar_lembretes_para_fala(lembretes: list) -> str:
    if not lembretes:
        return "Você não tem lembretes pendentes."
    if len(lembretes) == 1:
        return f"Você tem um lembrete pendente: {lembretes[0].texto}."
    textos = [l.texto for l in lembretes]
    lista = ", ".join(textos[:-1]) + f" e {textos[-1]}"
    return f"Você tem {len(lembretes)} lembretes pendentes: {lista}."


def formatar_briefing_matinal(eventos: list) -> str:
    """Texto do briefing ao iniciar o sistema."""
    agora = datetime.now()
    nome = get_config()["app"].get("assistant_name", "Aria")
    saudacao = "Bom dia" if agora.hour < 12 else "Boa tarde" if agora.hour < 18 else "Boa noite"

    if not eventos:
        return f"{saudacao}! Aqui é {nome}. Você não tem compromissos para hoje."

    agenda = formatar_agenda_para_fala(eventos)
    return f"{saudacao}! Aqui é {nome}. {agenda}"


def formatar_briefing_com_lembretes(eventos: list, lembretes: list) -> str:
    base = formatar_briefing_matinal(eventos)
    if not lembretes:
        return base
    lembrete_texto = formatar_lembretes_para_fala(lembretes)
    return f"{base} Além disso, {lembrete_texto}"


if __name__ == "__main__":
    testes = [
        "Anota reunião com o João amanhã às 14h",
        "Tenho dentista sexta de manhã",
        "O que tenho hoje?",
        "Cancela a reunião com o João",
        "Qual é a capital da França?",
    ]

    for cmd in testes:
        print(f"\nComando: '{cmd}'")
        resultado = interpretar_comando(cmd)
        print(f"Resultado: {json.dumps(resultado, ensure_ascii=False, indent=2)}")
