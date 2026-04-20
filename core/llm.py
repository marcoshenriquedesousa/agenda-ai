import json
import re
from datetime import datetime

import ollama

from core.config import get_config


SYSTEM_PROMPT = """Você é {nome}, um assistente de agenda pessoal.
Hoje é {hoje}, hora atual {hora}.

Calendário desta semana e próxima para referência:
{calendario}

Responda com um JSON usando um destes formatos:

criar_evento — marcar, anotar, agendar (com data/hora específica):
{{"acao": "criar_evento", "titulo": "...", "data_hora": "YYYY-MM-DD HH:MM", "descricao": "...", "lembrete_minutos": 15}}

consultar_eventos — o que tenho hoje/amanhã/semana/mês/próximos/dia específico:
{{"acao": "consultar_eventos", "periodo": "hoje|amanha|semana|mes|proximos|YYYY-MM-DD"}}
Quando o usuário mencionar um dia da semana ("sexta", "segunda", etc.), use a data exata do calendário acima como valor de periodo (ex: "periodo": "2026-04-24").

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

limpar_agenda — limpar, apagar tudo, remover todos os eventos de um período ou todos os lembretes:
{{"acao": "limpar_agenda", "periodo": "hoje|amanha|semana|mes|tudo", "alvo": "eventos|lembretes|tudo"}}

corrigir_textos — corrigir ortografia, corrigir textos salvos, revisar agenda:
{{"acao": "corrigir_textos"}}

nao_entendido — fora do escopo de agenda:
{{"acao": "nao_entendido", "mensagem": "resposta curta em português"}}

Regras de data:
- Use SEMPRE as datas do calendário acima para resolver dias da semana ("sexta", "segunda", etc.)
- "amanhã" = dia seguinte ao hoje
- Sem data mencionada: use hoje se a hora ainda não passou, senão amanhã

Regras de hora — PRIORIDADE ESTRITA:
1. Hora explícita ("8h", "oito horas", "08:00", "8 da manhã") → use EXATAMENTE essa hora (08:00)
2. Só use os padrões abaixo quando NENHUMA hora for mencionada:
   - "manhã" sem hora = 09:00
   - "tarde" sem hora = 14:00
   - "noite" sem hora = 19:00
   - sem hora e sem período = 09:00

Diferença entre criar_evento e criar_lembrete: evento tem data/hora específica (reunião às 14h). Lembrete é recorrente/sem horário fixo (pagar boleto, tomar remédio).
Para editar/deletar: use titulo_atual/texto_atual para identificar o item — não precisa ser exato, apenas palavras-chave suficientes.
Capitalize o titulo e o texto corretamente ao salvar (ex: "Reunião com João", "Pagar boleto")."""


_DIAS_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}


def _montar_prompt() -> str:
    from datetime import timedelta
    agora = datetime.now()
    nome = get_config()["app"].get("assistant_name", "Aria")

    # gera calendário dos próximos 14 dias com nome do dia
    linhas = []
    for i in range(14):
        dia = agora.date() + timedelta(days=i)
        nome_dia = _DIAS_PT[dia.weekday()]
        if i == 0:
            rotulo = f"hoje ({nome_dia})"
        elif i == 1:
            rotulo = f"amanhã ({nome_dia})"
        else:
            rotulo = nome_dia
        linhas.append(f"  {rotulo}: {dia.strftime('%Y-%m-%d')}")
    calendario = "\n".join(linhas)

    return SYSTEM_PROMPT.format(
        nome=nome,
        hoje=agora.strftime("%Y-%m-%d (%A)"),
        hora=agora.strftime("%H:%M"),
        calendario=calendario,
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


_PROMPT_CORRIGIR_STT = """Você é um corretor de reconhecimento de voz em português brasileiro.
O texto foi gerado por um sistema de transcrição automática (STT) e pode conter erros fonéticos — palavras que soam parecido mas estão erradas.

Corrija APENAS erros claros de transcrição ou ortografia. Não altere o sentido, não adicione palavras, não resuma.
Retorne SOMENTE o texto corrigido, sem explicações, sem aspas, sem pontuação extra.

Exemplos de correções esperadas:
- "autopedista" → "ortopedista"
- "cardiologista amanha" → "cardiologista amanhã"
- "reuniao com o joao" → "reunião com o João"
- "paga o boleto do cartao" → "pagar o boleto do cartão"
- "consulta no otorrino" → "consulta no otorrinolaringologista" (só se fizer sentido contextual)
- "anota dentista sexta de manha" → "anota dentista sexta de manhã"

Se o texto já estiver correto, retorne-o exatamente como está."""


def corrigir_transcricao(texto: str) -> str:
    """Corrige erros fonéticos de STT antes de interpretar o comando."""
    cfg = get_config()
    try:
        resposta = _cliente().chat(
            model=cfg["llm"]["model"],
            options={"temperature": 0.0, "keep_alive": "30m"},
            messages=[
                {"role": "system", "content": _PROMPT_CORRIGIR_STT},
                {"role": "user", "content": texto},
            ],
        )
        corrigido = resposta["message"]["content"].strip().strip('"').strip("'")
        return corrigido if corrigido else texto
    except Exception as e:
        return texto


def corrigir_texto(texto: str) -> str:
    """Corrige ortografia e normaliza um texto já salvo no banco."""
    cfg = get_config()
    resposta = _cliente().chat(
        model=cfg["llm"]["model"],
        options={"temperature": 0.0, "keep_alive": "30m"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Você é um corretor ortográfico. Recebe um texto curto em português "
                    "que pode ter erros de digitação, fala ou falta de acentuação. "
                    "Retorne APENAS o texto corrigido, sem explicações, sem aspas, sem pontuação extra. "
                    "Capitalize corretamente. Exemplos: "
                    "'reuniao com joao' → 'Reunião com João'; "
                    "'paga boleto cartao' → 'Pagar boleto do cartão'."
                ),
            },
            {"role": "user", "content": texto},
        ],
    )
    corrigido = resposta["message"]["content"].strip().strip('"').strip("'")
    return corrigido if corrigido else texto


_DIAS_FALA = ["segunda-feira", "terça-feira", "quarta-feira",
              "quinta-feira", "sexta-feira", "sábado", "domingo"]


def _formatar_data_fala(dt: datetime) -> str:
    """Retorna data legível para TTS: 'sexta-feira, dia 24 de abril'."""
    hoje = datetime.now().date()
    amanha = hoje + __import__("datetime").timedelta(days=1)
    if dt.date() == hoje:
        return "hoje"
    if dt.date() == amanha:
        return "amanhã"
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
             "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    nome_dia = _DIAS_FALA[dt.weekday()]
    return f"{nome_dia}, dia {dt.day} de {meses[dt.month - 1]}"


def formatar_agenda_para_fala(eventos: list, incluir_data: bool = False) -> str:
    """Converte lista de eventos em texto natural para o TTS falar."""
    if not eventos:
        return "Você não tem compromissos agendados."

    if len(eventos) == 1:
        e = eventos[0]
        hora = e.data_hora.strftime("%H:%M")
        if incluir_data:
            data = _formatar_data_fala(e.data_hora)
            return f"Você tem um compromisso: {e.titulo}, {data} às {hora}."
        return f"Você tem um compromisso: {e.titulo} às {hora}."

    partes = []
    for e in eventos:
        hora = e.data_hora.strftime("%H:%M")
        if incluir_data:
            data = _formatar_data_fala(e.data_hora)
            partes.append(f"{e.titulo}, {data} às {hora}")
        else:
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
