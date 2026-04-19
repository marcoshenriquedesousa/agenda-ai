"""
Gera o ícone assets/icon.ico usado pelo executável.
Execute uma vez antes do build.
"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).parent.parent / "assets" / "icon.ico"
OUT.parent.mkdir(parents=True, exist_ok=True)

sizes = [16, 32,48, 64, 128, 256]
frames = []

for size in sizes:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = size // 8
    # fundo azul
    draw.ellipse([pad, pad, size - pad, size - pad], fill=(80, 160, 255, 255))
    # microfone
    cx = size // 2
    mw = max(2, size // 6)
    mh = max(4, size // 3)
    draw.rectangle(
        [cx - mw, size // 4, cx + mw, size // 4 + mh],
        fill=(255, 255, 255, 255),
    )
    draw.ellipse(
        [cx - mw * 2, size // 4 + mh // 2, cx + mw * 2, size // 4 + mh + mh // 2],
        fill=(255, 255, 255, 255),
    )
    frames.append(img)

frames[0].save(OUT, format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[1:])
print(f"Ícone gerado: {OUT}")
