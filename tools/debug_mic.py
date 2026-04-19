"""Debug do microfone — mostra volume em tempo real e testa transcrição."""
import sounddevice as sd
import numpy as np
import time

SAMPLE_RATE = 16000
DURACAO = 8

print("=== TESTE DE MICROFONE ===")
print(f"Gravando {DURACAO} segundos... FALE AGORA!\n")

chunks = []

def callback(indata, frames, time, status):
    volume = np.abs(indata).mean()
    barra = "#" * int(volume * 300)
    print(f"\rVolume: {volume:.4f} |{barra:<30}|", end="", flush=True)
    chunks.append(indata.copy())

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=callback):
    time.sleep(DURACAO)

print("\n\nGravacao concluida!")

audio = np.concatenate(chunks).flatten().astype("float32")
volume_medio = np.abs(audio).mean()
print(f"Volume medio: {volume_medio:.4f}")

if volume_medio < 0.001:
    print("PROBLEMA: microfone nao esta capturando audio.")
    print("Verifique se o microfone certo esta selecionado no Windows.")
else:
    print("Microfone OK! Testando transcricao...")
    from faster_whisper import WhisperModel
    model = WhisperModel("small", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(audio, language="pt")
    texto = " ".join(s.text.strip() for s in segments)
    print(f"Transcricao: '{texto}'")
