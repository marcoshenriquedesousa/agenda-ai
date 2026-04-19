import queue
import threading
import numpy as np
import sounddevice as sd

from core.config import get_config

_model = None
_silero_model = None
SAMPLE_RATE = 16000
BLOCK_SIZE = 3200  # 200ms por chunk
_VAD_SUBCHUNK = 512  # 32ms — tamanho exigido pelo Silero VAD


def _get_model():
    global _model
    if _model is not None:
        return _model

    from faster_whisper import WhisperModel

    config = get_config()["stt"]
    model_size = config.get("model", "small")
    device = config.get("device", "auto")
    if device == "auto":
        try:
            import ctranslate2
            # get_supported_compute_types retorna lista vazia se CUDA não disponível
            device = "cuda" if ctranslate2.get_supported_compute_types("cuda") else "cpu"
        except Exception:
            device = "cpu"
    compute = "int8" if device == "cpu" else "float16"

    print(f"[STT] Carregando faster-whisper ({model_size}) em {device}...")
    try:
        _model = WhisperModel(model_size, device=device, compute_type=compute)
    except Exception as e:
        if device == "cuda":
            print(f"[STT] CUDA falhou ({e}), usando CPU como fallback...")
            _model = WhisperModel(model_size, device="cpu", compute_type="int8")
        else:
            raise
    print(f"[STT] Modelo carregado em {_model.model.device}.")
    return _model


def pre_carregar_modelo():
    """Pré-carrega o Whisper em background para não travar na primeira escuta."""
    threading.Thread(target=_get_model, daemon=True).start()


def _get_silero():
    """Carrega Silero VAD (lazy). Retorna False se indisponível."""
    global _silero_model
    if _silero_model is not None:
        return _silero_model
    try:
        import torch
        model, _ = torch.hub.load(
            "snakers4/silero-vad",
            "silero_vad",
            onnx=True,
            verbose=False,
        )
        _silero_model = model
        print("[VAD] Silero VAD carregado.")
    except Exception as e:
        print(f"[VAD] Silero indisponível, usando threshold de volume. ({e})")
        _silero_model = False
    return _silero_model


def _e_voz_silero(model, sub: np.ndarray) -> bool:
    import torch
    return model(torch.from_numpy(sub).unsqueeze(0), SAMPLE_RATE).item() > 0.5


def _capturar_com_vad(max_duracao: int = 15) -> np.ndarray:
    """Grava com VAD: para automaticamente após silêncio detectado."""
    config = get_config()["stt"]
    device_id = config.get("input_device_id", None)
    threshold = config.get("silence_threshold", 0.003)

    silero = _get_silero()
    # com Silero: 0.7s de silêncio basta; sem ele mantém 1.5s para segurança
    silencio_segundos = 0.7 if silero else 1.5

    audio_q: queue.Queue = queue.Queue()

    def callback(indata, frames, time, status):
        audio_q.put(indata.copy())

    chunks = []
    voz_detectada = False
    silencio_consecutivo = 0
    max_silencio_chunks = int(silencio_segundos * SAMPLE_RATE / BLOCK_SIZE)
    max_chunks = int(max_duracao * SAMPLE_RATE / BLOCK_SIZE)
    min_chunks_voz = int(0.3 * SAMPLE_RATE / BLOCK_SIZE)

    with sd.InputStream(
        device=device_id,
        samplerate=SAMPLE_RATE,
        channels=1,
        blocksize=BLOCK_SIZE,
        callback=callback,
    ):
        while len(chunks) < max_chunks:
            try:
                chunk = audio_q.get(timeout=2.0)
            except queue.Empty:
                break

            chunks.append(chunk)
            flat = chunk.flatten()

            if silero:
                # divide o chunk de 200ms em sub-chunks de 32ms para o Silero
                sub_chunks = [
                    flat[i : i + _VAD_SUBCHUNK]
                    for i in range(0, len(flat) - _VAD_SUBCHUNK + 1, _VAD_SUBCHUNK)
                ]
                tem_voz = any(_e_voz_silero(silero, s) for s in sub_chunks)
            else:
                tem_voz = np.abs(flat).mean() > threshold

            if tem_voz:
                voz_detectada = True
                silencio_consecutivo = 0
            elif voz_detectada:
                silencio_consecutivo += 1
                if silencio_consecutivo >= max_silencio_chunks:
                    break

    if not chunks or len(chunks) < min_chunks_voz:
        return np.array([], dtype=np.float32)

    return np.concatenate(chunks).flatten().astype(np.float32)


def escutar(duracao_max: int = 15) -> str:
    """Escuta com VAD e retorna texto transcrito."""
    config = get_config()["stt"]
    language = config.get("language", "pt")

    audio = _capturar_com_vad(max_duracao=duracao_max)

    if audio.size == 0:
        return ""

    pico = np.abs(audio).max()
    if 0 < pico < 0.3:
        audio = audio * (0.3 / pico)

    model = _get_model()
    try:
        segments, _ = model.transcribe(
            audio,
            language=language,
            beam_size=3,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
    except RuntimeError as e:
        if "cublas" not in str(e).lower() and "cuda" not in str(e).lower():
            raise
        # CUDA disponível mas DLLs ausentes — recarrega em CPU e persiste
        global _model
        print("[STT] CUDA sem DLLs necessárias, recarregando em CPU...")
        from faster_whisper import WhisperModel
        _model = WhisperModel(
            get_config()["stt"].get("model", "small"),
            device="cpu",
            compute_type="int8",
        )
        segments, _ = _model.transcribe(
            audio,
            language=language,
            beam_size=3,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        return " ".join(seg.text.strip() for seg in segments).strip()


def registrar_hotkey(callback: callable):
    """Registra hotkey global. Roda em thread separada."""
    import keyboard

    config = get_config()
    hotkey = config["app"].get("hotkey", "ctrl+alt+a")

    def ao_pressionar():
        print(f"[STT] Hotkey '{hotkey}' pressionada...")
        callback()

    keyboard.add_hotkey(hotkey, ao_pressionar)
    print(f"[STT] Hotkey registrada: {hotkey}")
    keyboard.wait()


if __name__ == "__main__":
    _get_model()
    print("Fale algo (para automaticamente após silêncio)...\n")
    texto = escutar()
    print(f"Você disse: '{texto}'")
