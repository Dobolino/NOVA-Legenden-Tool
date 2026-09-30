"""Create packaging/app.ico (blue rounded square with "NL")."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

size = 256
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.rounded_rectangle((8, 8, size - 8, size - 8), radius=56, fill=(11, 107, 203, 255))
try:
    font = ImageFont.truetype("arialbd.ttf", 120)
except OSError:
    font = ImageFont.load_default(size=120)
box = draw.textbbox((0, 0), "NL", font=font)
w, h = box[2] - box[0], box[3] - box[1]
draw.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1]), "NL", font=font, fill="white")
out = Path(__file__).with_name("app.ico")
img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print(out)
