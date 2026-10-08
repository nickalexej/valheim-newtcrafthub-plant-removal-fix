"""Create the addon's original 256x256 package icon; requires Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw

image = Image.new("RGBA", (256, 256), "#182b28")
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((10, 10, 246, 246), radius=40, outline="#74c8a5", width=6)
draw.rounded_rectangle((95, 114, 157, 210), radius=19, fill="#f4e8c9")
draw.pieslice((44, 42, 208, 174), 180, 360, fill="#ce694d")
draw.rounded_rectangle((43, 100, 209, 133), radius=15, fill="#ce694d")
draw.ellipse((91, 63, 112, 80), fill="#f4e8c9")
draw.ellipse((145, 84, 169, 100), fill="#f4e8c9")
draw.ellipse((62, 102, 82, 118), fill="#f4e8c9")
draw.ellipse((150, 152, 227, 229), fill="#74c8a5", outline="#182b28", width=6)
draw.line((169, 192, 185, 207, 209, 176), fill="#182b28", width=11, joint="curve")
destination = Path(__file__).resolve().parents[1] / "packaging" / "icon.png"
image.save(destination)
print(f"Created {destination.name}: {image.width}x{image.height} PNG")
