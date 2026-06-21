"""
Run this ONCE to generate the camp QR code.
Usage:  python generate_qr.py https://your-app.onrender.com
"""
import sys
import qrcode
from PIL import Image, ImageDraw, ImageFont

URL = sys.argv[1] if len(sys.argv) > 1 else "https://your-app.onrender.com"

qr = qrcode.QRCode(
    version=3,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=12,
    border=3,
)
qr.add_data(URL)
qr.make(fit=True)

img = qr.make_image(fill_color="#B91C1C", back_color="white").convert("RGB")

# Add label below QR
W, H = img.size
label_height = 60
canvas = Image.new("RGB", (W, H + label_height), "white")
canvas.paste(img, (0, 0))

draw = ImageDraw.Draw(canvas)
text = "Scan to get your Blood Donation Certificate"
# use default font as fallback
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
except:
    font = ImageFont.load_default()

bbox = draw.textbbox((0, 0), text, font=font)
tw = bbox[2] - bbox[0]
draw.text(((W - tw) // 2, H + 10), text, fill="#7F1D1D", font=font)

canvas.save("static/qr.png")
print(f"✅  QR saved to static/qr.png  →  {URL}")