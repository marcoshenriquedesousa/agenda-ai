# Agenda AI 🎙️

> Assistente de agenda pessoal com voz, rodando 100% local no Windows.

---

## Por que esse projeto existe?

Esse projeto nasceu de um problema real: eu não consigo me organizar usando agendas digitais ou ferramentas de produtividade. Eu começo a usar, mas logo elas ficam no esquecimento — nenhuma delas me busca, todas esperam que eu vá até elas.

A única coisa que funciona pra mim é ser alertado automaticamente, de forma fácil e natural. Daí surgiu a ideia: **e se eu pudesse simplesmente falar?** Sem abrir app, sem digitar, sem lembrar de checar algo. A assistente fala comigo, eu falo com ela.

Assim nasceu esse projeto.

---

## Como funciona

O app sobe silenciosamente na bandeja do Windows ao ligar o PC. De manhã ele já fala sua agenda do dia. Durante o dia, você aciona com uma hotkey ou pelo botão flutuante e simplesmente fala:

```
"Anota reunião com o João amanhã às 14h"
"O que tenho hoje?"
"Cancela o dentista de sexta"
```

Ele entende, confirma em voz e agenda automaticamente. 15 minutos antes de cada evento, uma notificação e a voz avisam — sem que você precise lembrar de checar nada.

---

## Demonstração

```
Windows inicia
  └─► Agenda AI sobe no system tray
        └─► "Bom dia! Você tem 2 compromissos hoje: Reunião às 10h e Dentista às 15h."

Usuário pressiona Ctrl+Alt+A (ou clica no botão flutuante)
  └─► 🎤 Escuta...
        └─► "Anota academia toda segunda, quarta e sexta às 7h"
              └─► LLM interpreta → salva no banco
                    └─► "Anotado! Academia às 07:00."

15 minutos antes do evento
  └─► 🔔 Notificação Windows + voz: "Lembrete: Reunião em 15 minutos, às 10h."
```

---

## Stack

| Camada | Tecnologia | Detalhe |
|--------|-----------|---------|
| **LLM** | Ollama — `qwen2.5:7b-instruct` | Local, extrai intenção e datas em PT-BR |
| **STT** | `faster-whisper` | Transcrição local, suporte CUDA automático |
| **TTS** | `edge-tts` (Microsoft Neural) | Voz PT-BR neural, streaming sem arquivo temp |
| **Banco** | SQLite + SQLAlchemy | Local, sem instalação extra |
| **Tray** | pystray + Pillow | Ícone na bandeja com menu de ações |
| **Botão flutuante** | PyQt6 | Sempre visível, com estados visuais animados |
| **UI** | PyQt6 | Janela de configurações completa |
| **Agendador** | APScheduler | Lembretes automáticos com antecedência configurável |
| **Notificações** | winotify | Notificações nativas do Windows |
| **Hotkey** | keyboard | Ativação global (`Ctrl+Alt+A` por padrão) |

Tudo roda **localmente** — nenhum dado sai do seu computador.

---

## Botão flutuante

Um círculo sempre visível no canto da tela com feedback visual em tempo real:

| Estado | Cor | Significado |
|--------|-----|-------------|
| ⚙️ Roxo | Carregando | Inicializando modelos |
| 🎙️ Azul | Pronto | Aguardando comando |
| 🎤 Vermelho | Escutando | Captando sua voz |
| ⏳ Laranja | Pensando | Processando com IA |
| 🔊 Verde | Falando | Reproduzindo resposta |

---

## Instalação

### Pré-requisitos

- Windows 10/11
- Python 3.11+
- [Ollama](https://ollama.com) instalado e rodando

### 1. Clone e instale dependências

```bash
git clone https://github.com/marcoshenriquedesousa/agenda-ai.git
cd agenda-ai
pip install -r requirements.txt
```

### 2. Baixe o modelo LLM

```bash
ollama pull qwen2.5:7b-instruct
```

### 3. Configure (opcional)

Edite o `config.json` para ajustar microfone, voz, hotkey e horário do briefing.
Ou use a interface gráfica de configurações pelo menu da bandeja.

### 4. Execute

```bash
python main.py
```

O app inicia na bandeja do sistema e o botão flutuante aparece no canto da tela.

---

## Configuração principal (`config.json`)

```json
{
  "app": {
    "hotkey": "ctrl+alt+a",
    "morning_briefing": true,
    "morning_briefing_time": "08:00"
  },
  "llm": {
    "model": "qwen2.5:7b-instruct"
  },
  "tts": {
    "provider": "edge-tts",
    "edge_voice": "pt-BR-FranciscaNeural"
  },
  "stt": {
    "model": "small",
    "device": "auto"
  }
}
```

`"device": "auto"` detecta CUDA automaticamente e usa GPU se disponível.

---

## Estrutura do projeto

```
agenda-ai/
├── core/
│   ├── assistente.py      # Orquestrador voz → LLM → banco → voz
│   ├── voice_in.py        # STT com faster-whisper + VAD
│   ├── voice_out.py       # TTS com edge-tts streaming
│   ├── llm.py             # Integração Ollama
│   ├── agenda.py          # CRUD de eventos (SQLite)
│   ├── scheduler.py       # Lembretes automáticos
│   └── config.py          # Cache de configuração
├── ui/
│   ├── floating_button.py # Botão flutuante com estados animados
│   └── settings.py        # Interface de configurações (PyQt6)
├── assets/
│   └── voice_reference/   # Áudio de referência para voz clonada (XTTS)
├── tools/
│   ├── build.bat          # Build do .exe com PyInstaller
│   └── debug_mic.py       # Diagnóstico de microfone
├── config.json            # Configurações centralizadas
├── main.py                # Entry point + system tray
└── requirements.txt
```

---

## Comandos de voz suportados

| Intenção | Exemplos |
|----------|---------|
| Criar evento | "Anota reunião amanhã às 14h" · "Lembra de academia toda segunda às 7h" |
| Consultar agenda | "O que tenho hoje?" · "Qual minha agenda de amanhã?" |
| Conversa livre | "Quanto é 49 mais 100?" · "Qual a capital da França?" |

---

## Licença

MIT — use, modifique e distribua à vontade.
