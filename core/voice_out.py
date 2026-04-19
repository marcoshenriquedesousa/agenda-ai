import queue
import tempfile
import threading
import os

from core.paths import BASE_DIR
from core.config import get_config

_tts_engine = None

# fila e thread dedicada para pyttsx3 (COM thread-safe)
_fala_queue: queue.Queue = queue.Queue()
_tts_thread_started = False


def _worker_pyttsx3():
    """Thread dedicada com COM inicializado corretamente para Windows."""
    import pyttsx3
    try:
        import pythoncom
        pythoncom.CoInitialize()
    except Exception:
        pass

    try:
        config = get_config()["tts"]
        engine = pyttsx3.init()
        engine.setProperty("rate", int(180 * config.get("speed", 1.0)))
        voices = engine.getProperty("voices")
        pt_voice = next(
            (v for v in voices if "brazil" in v.name.lower() or "portuguese" in v.name.lower()),
            None,
        )
        if pt_voice:
            engine.setProperty("voice", pt_voice.id)
            print(f"[TTS] Voz: {pt_voice.name}")
        else:
            print("[TTS] Usando voz padrao do sistema")
    except Exception as e:
        print(f"[TTS] Erro ao inicializar: {e}")
        return

    while True:
        texto = _fala_queue.get()
        if texto is None:
            break
        try:
            print(f"[TTS] Falando: '{texto}'")
            engine.say(texto)
            engine.runAndWait()
            print("[TTS] Fala concluida")
        except Exception as e:
            print(f"[TTS] ERRO: {e}")


def _garantir_worker():
    global _tts_thread_started
    if not _tts_thread_started:
        t = threading.Thread(target=_worker_pyttsx3, daemon=True)
        t.start()
        _tts_thread_started = True


def _get_engine():
    global _tts_engine
    if _tts_engine is not None:
        return _tts_engine

    config = get_config()
    provider = config["tts"]["provider"]

    if provider == "xtts":
        _tts_engine = _XTTSEngine(config["tts"])
    elif provider == "pyttsx3":
        _garantir_worker()
        _tts_engine = "pyttsx3"  # usa a fila diretamente
    elif provider == "edge-tts":
        _tts_engine = _EdgeTTSEngine(config["tts"])
    else:
        raise ValueError(f"Provedor TTS não suportado: {provider}")

    return _tts_engine


class _Pyttsx3Engine:
    pass  # substituído pelo worker com fila acima


class _EdgeTTSEngine:
    """Microsoft Edge TTS — PT-BR neural, streaming MP3 via sounddevice."""
    def __init__(self, tts_config: dict):
        self.voice = tts_config.get("edge_voice", "pt-BR-FranciscaNeural")
        self.speed = tts_config.get("speed", 1.0)
        self.output_device = None
        # event loop dedicado — evita criar/destruir loop a cada fala
        import asyncio
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop.run_forever, daemon=True).start()
        print(f"[TTS] edge-tts — voz: {self.voice}")

    def speak(self, texto: str):
        import asyncio
        future = asyncio.run_coroutine_threadsafe(self._falar_async(texto), self._loop)
        future.result()  # aguarda a fala terminar antes de retornar

    async def _falar_async(self, texto: str):
        import edge_tts
        import sounddevice as sd
        import soundfile as sf
        import io

        rate = f"+{int((self.speed - 1) * 100)}%" if self.speed >= 1 else f"{int((self.speed - 1) * 100)}%"

        # coleta chunks via stream (primeiro chunk chega em ~200-400ms)
        audio_bytes = bytearray()
        communicate = edge_tts.Communicate(texto, self.voice, rate=rate)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.extend(chunk["data"])

        if not audio_bytes:
            return

        # decodifica e toca em memória — sem arquivo temporário
        data, sr = sf.read(io.BytesIO(bytes(audio_bytes)))
        print(f"[TTS] Reproduzindo no dispositivo padrao...")
        sd.play(data, sr, device=self.output_device)
        sd.wait()
        print("[TTS] Fala concluida")


class _XTTSEngine:
    def __init__(self, tts_config: dict):
        from TTS.api import TTS
        import torch

        self.config = tts_config
        self.language = tts_config.get("language", "pt")
        self.voice_ref = BASE_DIR / tts_config.get("voice_reference", "")
        self.has_reference = self.voice_ref.exists()

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[TTS] Carregando XTTS v2 no dispositivo: {device}")

        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        if not self.has_reference:
            print(
                "[TTS] Aviso: áudio de referência não encontrado. "
                f"Coloque um arquivo WAV em: {self.voice_ref}\n"
                "[TTS] Usando voz padrão do modelo."
            )

    def speak(self, texto: str):
        import sounddevice as sd
        import soundfile as sf
        import numpy as np

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            if self.has_reference:
                self.tts.tts_to_file(
                    text=texto,
                    speaker_wav=str(self.voice_ref),
                    language=self.language,
                    file_path=tmp_path,
                )
            else:
                self.tts.tts_to_file(
                    text=texto,
                    language=self.language,
                    file_path=tmp_path,
                )

            data, samplerate = sf.read(tmp_path)
            sd.play(data, samplerate)
            sd.wait()
        finally:
            os.unlink(tmp_path)


def falar(texto: str):
    """Fala o texto usando a engine TTS configurada."""
    engine = _get_engine()
    if engine == "pyttsx3":
        _fala_queue.put(texto)
    else:
        engine.speak(texto)


def recarregar_engine():
    """Força recarga da engine (após trocar voz de referência nas configurações)."""
    global _tts_engine, _tts_thread_started
    _tts_engine = None
    _tts_thread_started = False


if __name__ == "__main__":
    print("Testando TTS...")
    falar("Olá! Sou sua assistente de agenda. Estou pronta para ajudar.")
