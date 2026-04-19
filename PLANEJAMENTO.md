# Agenda AI — Planejamento do Projeto

Assistente de agenda pessoal com voz, rodando localmente no Windows.

## Conceito

- Inicia com o Windows (system tray)
- Ao ligar, fala a agenda do dia
- Você fala com ela para anotar compromissos
- Notifica eventos com antecedência configurável
- Voz clonada do próprio usuário (XTTS v2)

---

## Stack

| Camada | Tecnologia | Detalhe |
|--------|-----------|---------|
| LLM | Ollama — `qwen2.5:14b` | Local, extração de eventos em PT-BR |
| STT | `faster-whisper` | Transcrição local, modelo `small` ou `medium` |
| TTS | `XTTS v2 (Coqui)` | Voz clonada com ~12s de áudio de referência |
| Banco | `SQLite + SQLAlchemy` | Local, sem instalação extra |
| Tray | `pystray + Pillow` | Ícone discreto na bandeja |
| UI | `PyQt6` | Janela de configurações |
| Agendador | `APScheduler` | Lembretes automáticos |
| Notificações | `winotify` | Notificações nativas do Windows |
| Hotkey | `keyboard` | Ativação global (padrão: `Ctrl+Alt+A`) |
| Autostart | `winreg` | Inicia com o sistema via registro do Windows |
| Empacotamento | `PyInstaller` | Gera `.exe` standalone |

---

## Fluxo principal

```
Windows inicia
  └─► App sobe no system tray (ícone discreto)
        └─► TTS fala: "Bom dia! Agenda de hoje: ..."

Usuário pressiona Ctrl+Alt+A
  └─► faster-whisper começa a escutar
        └─► "Anota reunião com a equipe sexta às 14h"
              └─► Ollama extrai: { titulo, data, hora }
                    └─► Salva no SQLite
                          └─► TTS confirma: "Anotado!"

APScheduler (em background)
  └─► 15min antes do evento → winotify + TTS avisa
```

---

## Etapas

### ✅ Etapa 1 — Estrutura base
- [x] Estrutura de pastas do projeto
- [x] `config.json` com todas as preferências
- [x] `requirements.txt` com dependências
- [x] `main.py` com entry point e system tray básico
- [x] `core/__init__.py` e `ui/__init__.py`

### ✅ Etapa 2 — Banco de dados
- [x] Modelo `Evento` com SQLAlchemy
- [x] `init_db()` — cria o banco na primeira execução
- [x] `criar_evento()` — salva evento no SQLite
- [x] `listar_eventos_hoje()` — eventos do dia
- [x] `listar_proximos_eventos()` — próximos N eventos
- [x] `marcar_concluido()` — marca evento como feito

### ✅ Etapa 3 — TTS com XTTS v2 (voz clonada)
- [x] `core/voice_out.py` com engine XTTS v2
- [x] Suporte a GPU (automático) com fallback para CPU
- [x] `falar(texto)` pronta para uso em qualquer módulo
- [x] Fallback para voz padrão se referência não existir
- [x] `recarregar_engine()` para trocar voz sem reiniciar
- [x] `tools/gravar_voz_referencia.py` — grava os ~12s de referência

### ✅ Etapa 4 — STT com faster-whisper + hotkey
- [x] `core/voice_in.py` com captura de microfone
- [x] Transcrição local com faster-whisper
- [x] Ativação por hotkey global (`Ctrl+Alt+A`)
- [x] Para automaticamente após silêncio detectado
- [x] `escutar()` retorna texto transcrito
- [x] `registrar_hotkey(callback)` para integrar ao app principal

### ✅ Etapa 5 — Integração Ollama (extração de eventos)
- [x] `core/llm.py` com cliente Ollama
- [x] Prompt de sistema para extrair eventos em PT-BR
- [x] Parser de resposta: `{ titulo, data, hora, descricao }`
- [x] Datas relativas: "amanhã", "sexta", "de manhã" convertidas automaticamente
- [x] Comandos suportados: criar, consultar, cancelar, não entendido
- [x] `formatar_briefing_matinal()` para leitura ao iniciar
- [x] `core/assistente.py` — orquestrador do ciclo completo voz → LLM → banco → voz

### ✅ Etapa 6 — System tray + autostart Windows
- [x] Ícone personalizado na bandeja (com microfone)
- [x] Menu: Agenda de hoje, Pausar escuta, Configurações, Sair
- [x] Ícone muda de cor quando escuta está pausada
- [x] Registro no Windows para autostart (`winreg`)
- [x] `core/autostart.py` — utilitário standalone (ativar/desativar/status)
- [x] Briefing matinal agendado no horário configurado
- [x] Loop diário automático do briefing
- [x] Briefing imediato se iniciar próximo ao horário configurado (±5min)

### ✅ Etapa 7 — Notificações e lembretes
- [x] `core/scheduler.py` com APScheduler em background
- [x] Verifica eventos a cada minuto
- [x] Notificação nativa Windows (`winotify`) com som
- [x] TTS fala o lembrete automaticamente
- [x] Antecedência configurável via `config.json`
- [x] `agendar_notificacao_imediata()` ao criar evento via voz
- [x] Reset automático à meia-noite para o próximo dia
- [x] Scheduler integrado no `main.py` e `assistente.py`

### ✅ Etapa 8 — UI de configurações (PyQt6)
- [x] Aba **Geral**: autostart, briefing matinal, horário, hotkey
- [x] Aba **Voz**: importar WAV, gravar agora, velocidade, teste ao vivo
- [x] Aba **Modelo**: modelo Ollama, URL, temperatura, Whisper, dispositivo
- [x] Aba **Agenda**: antecedência dos lembretes, som
- [x] Salva em `config.json` e sincroniza autostart automaticamente
- [x] Integrada ao menu do system tray

### ✅ Etapa 9 — Empacotamento
- [x] `agenda_ai.spec` configurado para gerar `.exe` sem console
- [x] `build_hooks/hook-TTS.py` para incluir modelos Coqui corretamente
- [x] `tools/gerar_icone.py` — gera `icon.ico` em múltiplos tamanhos
- [x] `tools/build.bat` — build completo em 4 passos com um clique
- [x] `tools/instalar_dependencias.bat` — setup inicial para novos usuários
- [x] Assets (data, voice_reference) copiados automaticamente no build

---

## Estrutura de pastas

```
agenda-ai/
├── .claude/
│   └── commands/
│       └── ai-dev.md          # skill especialista do projeto
├── assets/
│   └── voice_reference/
│       └── minha_voz.wav      # áudio de referência (gravar com tools/)
├── core/
│   ├── agenda.py              # ✅ CRUD de eventos (SQLite)
│   ├── voice_out.py           # ✅ TTS com XTTS v2
│   ├── voice_in.py            # ✅ STT com faster-whisper
│   ├── llm.py                 # ✅ Integração Ollama
│   ├── assistente.py          # ✅ Orquestrador voz → LLM → banco → voz
│   ├── scheduler.py           # ✅ Lembretes automáticos
│   └── autostart.py           # ✅ Gerencia autostart Windows
├── data/
│   └── agenda.db              # banco gerado automaticamente
├── tools/
│   └── gravar_voz_referencia.py  # ✅ grava áudio de referência
├── ui/
│   └── settings.py            # ✅ UI PyQt6 configurações
├── config.json                # ✅ configurações centralizadas
├── main.py                    # ✅ entry point + system tray
├── requirements.txt           # ✅ dependências
└── PLANEJAMENTO.md            # este arquivo
```

---

## O que falta (próxima sessão)

### ✅ Resposta geral (fora de agenda)
- [x] `responder_livremente()` em `core/llm.py` — responde qualquer pergunta
- [x] Assistente híbrida: agenda + conversa geral

### ✅ Dispositivo de microfone na UI
- [x] Aba Voz — dropdown lista todos os dispositivos de entrada disponíveis
- [x] Salva `input_device_id` no `config.json` ao salvar

### ✅ Build final `.exe`
- [x] Ícone gerado em múltiplos tamanhos
- [x] Build PyInstaller concluído sem erros
- [x] `dist/AgendaAI/AgendaAI.exe` gerado com sucesso

---

## Configuração atual (testada e funcionando)

```json
{
  "llm": { "model": "qwen2.5:14b" },
  "tts": { "provider": "pyttsx3" },
  "stt": { "input_device_id": 7, "silence_threshold": 0.003 }
}
```

- **Microfone:** JBL Quantum Stream Talk (device 7)
- **Voz:** Microsoft Maria Desktop PT-BR (pyttsx3)
- **LLM:** qwen2.5:14b instalado e validado
- **Ciclo completo testado:** voz → Whisper → Ollama → banco → Maria fala

---

## Bugs corrigidos durante os testes

| Bug | Causa | Fix |
|-----|-------|-----|
| `KeyError` no prompt LLM | `{}` do JSON conflitavam com `.format()` | Escapados para `{{}}` |
| STT retornava vazio | Silêncio detectado antes da fala | Trocado para `sd.rec()` de duração fixa |
| Volume muito baixo | Ganho do JBL reduzido | Amplificação automática antes do Whisper |
| `UnicodeEncodeError` | Caractere `→` no terminal Windows | Substituído por `>` |
| Modelo não encontrado | `qwen2.5:14b` não estava instalado | Instalado via `ollama pull` |

---

## Como rodar (desenvolvimento)

```bash
cd c:/Git/agenda-ai
pip install -r requirements.txt

# Testar STT (microfone)
python core/voice_in.py

# Testar ciclo completo
python -m core.assistente

# Iniciar o app completo
python main.py
```
