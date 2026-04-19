"""
Utilitário para gravar o áudio de referência da sua voz para o XTTS v2.
Execute este script uma vez para criar o arquivo de referência.

Dica: fale de forma clara e natural por 8 a 15 segundos.
Exemplo: "Olá, eu sou o assistente de agenda pessoal. Vou te ajudar a organizar
seus compromissos e lembretes ao longo do dia."
"""

import sounddevice as sd
import soundfile as sf
import numpy as np
from pathlib import Path

SAMPLE_RATE = 22050
DURACAO_SEGUNDOS = 12
OUTPUT_PATH = Path(__file__).parent.parent / "assets" / "voice_reference" / "minha_voz.wav"


def gravar():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("GRAVAÇÃO DE VOZ DE REFERÊNCIA — XTTS v2")
    print("=" * 50)
    print(f"\nVocê terá {DURACAO_SEGUNDOS} segundos para falar.")
    print("Fale de forma clara, natural e em volume normal.")
    print("\nSugestão de texto:")
    print("  'Olá, sou seu assistente de agenda pessoal.")
    print("   Vou te ajudar a organizar seus compromissos")
    print("   e lembretes ao longo do dia.'")
    print()
    input("Pressione ENTER quando estiver pronto...")

    print("\nGravando... FALE AGORA!")
    audio = sd.rec(
        int(DURACAO_SEGUNDOS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    print("Gravação concluída!")

    sf.write(str(OUTPUT_PATH), audio, SAMPLE_RATE)
    print(f"\nArquivo salvo em: {OUTPUT_PATH}")
    print("\nAgora você pode testar o TTS executando:")
    print("  python core/voice_out.py")


if __name__ == "__main__":
    gravar()
