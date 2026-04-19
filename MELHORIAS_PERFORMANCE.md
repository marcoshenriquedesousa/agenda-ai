# Agenda AI — Melhorias de Performance

Análise detalhada de oportunidades de otimização no pipeline voz → LLM → voz,
priorizadas pelo impacto na latência percebida (tempo entre apertar a hotkey e
ouvir a resposta).

---

## Pipeline atual e onde está o tempo

```
Hotkey pressionada
  ├─ [1] TTS "Ouvindo..."            ~500ms  (bloqueia abertura do mic)
  ├─ [2] Abrir InputStream + VAD     ~100ms
  ├─ [3] Captura de áudio            variável (fala do usuário)
  ├─ [4] Espera silêncio (1.5s)      1500ms  (fixo, desperdício)
  ├─ [5] Transcrição Whisper small   ~1200-2500ms  (beam_size=5 na CPU)
  ├─ [6] Chamada Ollama qwen2.5:14b  ~2500-6000ms  (modelo grande)
  ├─ [7] edge-tts gera MP3 completo  ~600-1200ms  (sem streaming)
  └─ [8] Lê arquivo + toca           ~200ms
```

**Latência total estimada atual:** ~7 a 12 segundos entre fim da fala do usuário
e início da resposta em áudio.

**Latência alvo após melhorias:** ~2 a 4 segundos.

---

## 🔴 Alto impacto (ganho de segundos)

### 1. LLM — modelo 14B é exagerado para classificação de intenção

- **Arquivo:** [config.json:11](config.json#L11)
- **Atual:** `qwen2.5:14b`
- **Problema:** Para extrair JSON `{acao, titulo, data_hora}` um modelo 14B é
  subutilizado. Cada comando gasta 2.5–6s apenas no LLM.
- **Proposta:**
  - Trocar para `qwen2.5:7b-instruct` → ~2–3x mais rápido, qualidade praticamente
    igual em PT-BR para esse uso.
  - Ou `qwen2.5:3b-instruct` → ~5x mais rápido, testar qualidade em comandos
    complexos (datas relativas, horários implícitos).
  - Alternativa: usar `qwen2.5:3b` apenas para `interpretar_comando` e manter
    `qwen2.5:7b` para `responder_livremente` (conversa geral).
- **Esforço:** trivial — alterar `config.json` + `ollama pull`.

### 2. LLM — não usa o modo JSON nativo do Ollama

- **Arquivo:** [core/llm.py:75-82](core/llm.py#L75-L82)
- **Problema:** O modelo fica livre para gerar markdown/explicações, que depois
  são removidos com regex ([core/llm.py:64-68](core/llm.py#L64-L68)). Isso gasta
  tokens desnecessários (mais lento) e pode falhar no parse.
- **Proposta:** adicionar `format="json"` na chamada:
  ```python
  resposta = ollama.chat(
      model=config["model"],
      format="json",
      options={"temperature": config.get("temperature", 0.1), "keep_alive": "30m"},
      messages=[...],
  )
  ```
- **Benefício:** resposta mais curta, parse 100% confiável, menos tokens gerados.

### 3. LLM — modelo pode estar descarregando entre comandos

- **Arquivos:** [core/llm.py:75](core/llm.py#L75) e
  [core/llm.py:96](core/llm.py#L96)
- **Problema:** Sem `keep_alive`, o Ollama descarrega o modelo após alguns
  minutos inativos. Primeiro comando depois da inatividade paga 5–15s de reload.
- **Proposta:**
  - Passar `options={"keep_alive": "30m"}` em toda chamada `ollama.chat`.
  - Fazer warm-up no `main()` de [main.py](main.py) (depois do
    `pre_carregar_modelo()` do Whisper):
    ```python
    # pré-aquece o Ollama
    threading.Thread(
        target=lambda: ollama.chat(
            model=config["llm"]["model"],
            messages=[{"role": "user", "content": "ok"}],
            options={"keep_alive": "30m"},
        ),
        daemon=True,
    ).start()
    ```
- **Benefício:** elimina reload no primeiro comando do dia.

### 4. STT — `beam_size=5` é o maior custo do Whisper na CPU

- **Arquivo:** [core/voice_in.py:110](core/voice_in.py#L110)
- **Atual:** `model.transcribe(audio, language=language, beam_size=5)`
- **Problema:** Beam search com 5 caminhos é ~3x mais lento que greedy
  (`beam_size=1`). Ganho de qualidade em PT para frases curtas de comando é
  marginal.
- **Proposta:**
  ```python
  segments, _ = model.transcribe(
      audio,
      language=language,
      beam_size=1,
      vad_filter=True,
      condition_on_previous_text=False,
      without_timestamps=True,
  )
  ```
  - `beam_size=1` → 2–3x mais rápido.
  - `vad_filter=True` → ignora trechos sem voz dentro do áudio.
  - `condition_on_previous_text=False` → reduz alucinação entre comandos.
  - `without_timestamps=True` → não gastamos tempo gerando timestamps que não
    são usados.

### 5. TTS — edge-tts não está fazendo streaming

- **Arquivo:** [core/voice_out.py:104-130](core/voice_out.py#L104-L130)
- **Atual:** `communicate.save(path)` gera o MP3 inteiro, salva em arquivo
  temporário, lê com `soundfile`, toca com `sounddevice`. Usuário espera todo
  o áudio antes de ouvir o primeiro fonema.
- **Proposta:** usar `communicate.stream()` do edge-tts, decodificar chunks
  conforme chegam e tocar em um `RawOutputStream` do `sounddevice`. Esboço:
  ```python
  async def _gerar_e_tocar():
      communicate = edge_tts.Communicate(texto, self.voice, rate=rate)
      # primeiro passo: coletar bytes completos via stream
      audio_bytes = bytearray()
      async for chunk in communicate.stream():
          if chunk["type"] == "audio":
              audio_bytes.extend(chunk["data"])
      # decodifica e toca (ideal: pipelinear decode + play)
  ```
  Para true streaming com latência mínima, usar `pydub` + `sounddevice.OutputStream`
  consumindo chunks à medida que são decodificados.
- **Benefício:** primeiro som sai em ~300ms em vez de 600–1200ms. UX muito mais
  responsiva.

---

## 🟡 Médio impacto

### 6. "Ouvindo..." falado atrasa o início da captura

- **Arquivo:** [core/assistente.py:62-64](core/assistente.py#L62-L64)
- **Problema:** O `falar("Ouvindo...")` bloqueia o fluxo até o TTS terminar.
  Usuário solta a hotkey, ainda ouve "Ouvindo..." e só depois o microfone abre.
  Risco do usuário começar a falar antes do mic ligar e a primeira palavra ser
  cortada.
- **Proposta:** substituir por:
  - Beep curto e não bloqueante:
    ```python
    import winsound
    winsound.Beep(1000, 80)  # 80ms — quase imperceptível como delay
    ```
  - Ou mudar o ícone da tray para amarelo/vermelho indicando "escutando".
  - Abrir o `InputStream` imediatamente após o beep.
- **Benefício:** economiza ~500ms e elimina risco de corte no início.

### 7. VAD caseiro baseado em volume médio é frágil

- **Arquivo:** [core/voice_in.py:78-87](core/voice_in.py#L78-L87)
- **Atual:** `volume = np.abs(chunk).mean()` comparado com `silence_threshold`
  fixo em 0.003.
- **Problema:**
  - Em ambiente com ruído de fundo (ar condicionado, ventilador, rua) o
    threshold fixo falha.
  - Detecção de fim de fala é grosseira — por isso precisa de 1.5s de silêncio
    para ter confiança.
- **Proposta:** trocar por **Silero VAD** (ONNX, ~5MB, rodando em CPU em
  tempo real) ou **webrtcvad**. Esboço com Silero:
  ```python
  import torch
  model, utils = torch.hub.load(
      repo_or_dir='snakers4/silero-vad',
      model='silero_vad',
      onnx=True,
  )
  (get_speech_timestamps, _, _, _, _) = utils
  # aplicar por chunk de 30ms → decisão binária fala/silêncio
  ```
- **Benefício:** permite reduzir `max_silencio_chunks` para ~0.6–0.8s sem
  cortar o usuário → economiza ~700–900ms por comando.

### 8. `config.json` é lido do disco a cada chamada

- **Arquivos:**
  - [core/voice_in.py:16-19](core/voice_in.py#L16-L19)
  - [core/voice_out.py:18-20](core/voice_out.py#L18-L20)
  - [core/llm.py:12-14](core/llm.py#L12-L14)
- **Problema:** cada módulo abre o JSON toda vez que precisa de um valor. Custo
  individual baixo, mas é desperdício puro no hot path.
- **Proposta:** cache em memória com invalidação manual. Exemplo centralizado
  em `core/config.py`:
  ```python
  _cache = None

  def get_config() -> dict:
      global _cache
      if _cache is None:
          with open(CONFIG_PATH, "r", encoding="utf-8") as f:
              _cache = json.load(f)
      return _cache

  def invalidate():
      global _cache
      _cache = None
  ```
  Chamar `invalidate()` depois de salvar pela UI de configurações.

### 9. Silêncio de 1.5s antes de encerrar a escuta é generoso

- **Arquivo:** [core/voice_in.py:61](core/voice_in.py#L61)
- **Atual:** `max_silencio_chunks = int(1.5 * SAMPLE_RATE / BLOCK_SIZE)`
- **Proposta:** depende do VAD. Com o volume-based atual, 1.5s é razoável para
  evitar corte. Com Silero VAD decente, 0.6–0.8s é seguro.
- **Benefício combinado com #7:** até 900ms a menos por comando.

---

## 🟢 Baixo impacto / polish

### 10. TTS worker pyttsx3 não é pré-aquecido

- **Arquivo:** [core/voice_out.py:63-68](core/voice_out.py#L63-L68)
- **Problema:** `_garantir_worker()` só inicia a thread no primeiro `falar()`.
  Primeiro uso paga init do engine + carregamento de voz (~500ms–1s).
- **Proposta:** chamar `_get_engine()` no boot de [main.py](main.py), junto com
  o `pre_carregar_modelo()` do Whisper:
  ```python
  # em main()
  from core.voice_out import _get_engine
  threading.Thread(target=_get_engine, daemon=True).start()
  ```

### 11. Whisper "small" na CPU — considerar GPU ou modelo menor

- **Arquivo:** [config.json:25](config.json#L25)
- **Proposta A (tem GPU NVIDIA):** mudar `"device": "cuda"` — ~5x mais rápido.
  Ajustar também `compute_type="float16"` (já faz isso em
  [core/voice_in.py:31](core/voice_in.py#L31)).
- **Proposta B (só CPU):** testar modelo `"base"` — qualidade um pouco menor
  mas aceitável para comandos curtos e em PT bem articulado. Modelo `"tiny"` é
  rápido demais mas tende a errar mais em comandos com datas e nomes próprios.

### 12. System prompt pode encolher com `format="json"`

- **Arquivo:** [core/llm.py:17-53](core/llm.py#L17-L53)
- **Proposta:** com `format="json"` ativado, remover:
  - "responda SOMENTE com um JSON válido"
  - "Responda APENAS o JSON, sem explicações, sem markdown"
  - Exemplos de blocos ` ```json `
- **Benefício:** menos tokens de prompt = menos tempo de prefill. Pequeno,
  mas grátis.

### 13. `asyncio.run` dentro do TTS cria event loop a cada fala

- **Arquivo:** [core/voice_out.py:120](core/voice_out.py#L120)
- **Problema:** `asyncio.run(_gerar(tmp_path))` cria e destrói event loop em
  toda chamada. Overhead baixo, mas evitável se migrar para streaming (item 5).
- **Proposta:** manter um event loop dedicado numa thread (padrão já usado
  no worker pyttsx3 em [core/voice_out.py:23](core/voice_out.py#L23)).

---

## Ordem sugerida de implementação

1. **Quick wins** (edição de 2–5 linhas, impacto imediato):
   - Item 2 — `format="json"` no Ollama
   - Item 3 — `keep_alive` + warm-up
   - Item 4 — `beam_size=1` + flags do Whisper
   - Item 6 — beep em vez de "Ouvindo..." falado
   - Item 10 — pré-aquecimento do TTS

2. **Trocas de config** (validar qualidade):
   - Item 1 — `qwen2.5:7b` (ou `3b`)
   - Item 11 — modelo Whisper (se necessário)

3. **Refatores maiores** (mais trabalho, ganho grande de UX):
   - Item 5 — streaming edge-tts
   - Item 7 — Silero VAD
   - Item 9 — silêncio mais curto (acompanha #7)

4. **Limpeza** (não urgente):
   - Item 8 — cache de config
   - Item 12 — encolher system prompt
   - Item 13 — event loop persistente

---

## Métricas sugeridas para validar

Adicionar logs de tempo em cada etapa (dá para usar `time.perf_counter()` em
cada função) e registrar por ciclo:

| Etapa | Log key | Meta |
|-------|---------|------|
| Captura + VAD | `t_capture_ms` | < 500ms de cauda de silêncio |
| Whisper transcribe | `t_stt_ms` | < 800ms para comando de ~3s |
| Ollama chat | `t_llm_ms` | < 1500ms para JSON simples |
| TTS (primeiro áudio) | `t_tts_first_audio_ms` | < 400ms |
| **Total percebido** | `t_total_ms` | **< 3000ms** |

Logar em [agenda_ai.log](agenda_ai.log) permite comparar antes/depois com
dados reais em vez de sensação.
