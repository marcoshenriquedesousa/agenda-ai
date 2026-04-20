import queue
import tempfile
import threading
import os

os.environ.setdefault("COQUI_TOS_AGREED", "1")

# torchaudio 2.9+ usa torchcodec que exige FFmpeg shared DLLs no Windows.
# Patch para usar soundfile como backend de carregamento de áudio.
def _patch_torchaudio():
    try:
        import torchaudio
        import soundfile as sf
        import torch
        import numpy as np

        def _load_via_soundfile(filepath, frame_offset=0, num_frames=-1, normalize=True, channels_first=True, format=None, backend=None):
            data, sr = sf.read(str(filepath), dtype="float32", always_2d=True)
            if num_frames > 0:
                data = data[frame_offset: frame_offset + num_frames]
            elif frame_offset > 0:
                data = data[frame_offset:]
            tensor = torch.from_numpy(data.T if channels_first else data)
            return tensor, sr

        torchaudio.load = _load_via_soundfile
    except Exception:
        pass

_patch_torchaudio()

from core.paths import BASE_DIR
from core.config import get_config


def _preimport_tts_if_needed():
    """Importa TTS na thread principal para evitar race condition no import system."""
    try:
        cfg = get_config()
        if cfg["tts"]["provider"] == "xtts":
            from TTS.api import TTS  # noqa: carrega transformers antes das threads
    except Exception:
        pass

_preimport_tts_if_needed()

_tts_engine = None
_tts_engine_lock = threading.Lock()

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

    with _tts_engine_lock:
        if _tts_engine is not None:  # outra thread já inicializou enquanto esperava
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


def _normalizar_texto(texto: str) -> str:
    """Normalização aplicada a todos os providers — remove artefatos de pontuação."""
    import re
    texto = texto.strip()
    # remove ponto(s) e espaços no final — evita "ponto" falado pelo TTS
    texto = re.sub(r'[\s.]+$', '', texto)
    return texto.strip()


def _normalizar_para_xtts(texto: str) -> str:
    """Normalização extra para XTTS v2 — lê símbolos literalmente."""
    import re
    texto = _normalizar_texto(texto)
    # datas: 20/04 → "20 de 04"
    texto = re.sub(r'\b(\d{1,2})/(\d{1,2})\b', r'\1 de \2', texto)
    # horas: 14:00 → "14 e 00"
    texto = re.sub(r'\b(\d{1,2}):(\d{2})\b', r'\1 e \2', texto)
    return texto


def _chunkar_texto(texto: str) -> list:
    """Divide em frases curtas — XTTS v2 perde qualidade com textos longos."""
    import re
    partes = re.split(r'(?<=[.!?])\s+', texto.strip())
    chunks, buffer = [], ""
    for parte in partes:
        parte = parte.strip()
        if not parte:
            continue
        candidato = (buffer + " " + parte).strip()
        if len(candidato) <= 180:
            buffer = candidato
        else:
            if buffer:
                chunks.append(buffer)
            buffer = parte
    if buffer:
        chunks.append(buffer)
    return chunks or [texto]


class _XTTSEngine:
    def __init__(self, tts_config: dict):
        from TTS.api import TTS
        import torch

        self.config = tts_config
        self.language = tts_config.get("language", "pt")
        self.speed = tts_config.get("speed", 1.0)
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

    def _prepare_reference(self) -> str:
        """Converte a referência para mono 22050Hz num arquivo temporário se necessário."""
        import soundfile as sf
        import numpy as np

        data, sr = sf.read(str(self.voice_ref), dtype="float32", always_2d=True)

        # converte estéreo → mono
        if data.shape[1] > 1:
            data = data.mean(axis=1)
        else:
            data = data[:, 0]

        # reamostrar para 22050 se necessário
        target_sr = 22050
        if sr != target_sr:
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(sr, target_sr)
            data = resample_poly(data, target_sr // g, sr // g).astype("float32")

        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, data, target_sr)
        tmp.close()
        print(f"[TTS] Referência preparada: mono {target_sr}Hz, {len(data)/target_sr:.1f}s")
        return tmp.name

    def speak(self, texto: str):
        import sounddevice as sd
        import soundfile as sf
        import numpy as np

        texto = _normalizar_para_xtts(texto)
        chunks = _chunkar_texto(texto)
        ref_tmp = self._prepare_reference() if self.has_reference else None

        segmentos = []
        samplerate = 24000
        silencio_entre = np.zeros(int(samplerate * 0.18))  # 180ms de pausa entre frases

        try:
            for chunk in chunks:
                chunk = _normalizar_para_xtts(chunk)
                if not chunk:
                    continue
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    kwargs = dict(
                        text=chunk,
                        language=self.language,
                        file_path=tmp_path,
                        speed=self.speed,
                    )
                    if ref_tmp:
                        kwargs["speaker_wav"] = ref_tmp
                    self.tts.tts_to_file(**kwargs)
                    data, samplerate = sf.read(tmp_path)
                    segmentos.append(data)
                    segmentos.append(silencio_entre)
                finally:
                    os.unlink(tmp_path)
        finally:
            if ref_tmp:
                os.unlink(ref_tmp)

        if segmentos:
            audio_final = np.concatenate(segmentos[:-1])  # remove silêncio final
            sd.play(audio_final, samplerate)
            sd.wait()


def falar(texto: str):
    """Fala o texto usando a engine TTS configurada."""
    texto = _normalizar_texto(texto)
    if not texto:
        return
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
