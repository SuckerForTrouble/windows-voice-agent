"""The microphone icon, coloured by state (tray, installer, .exe)."""
from PIL import Image, ImageDraw

COLOR = {"loading": (140, 146, 160), "ready": (99, 110, 230), "listen": (229, 72, 77), "busy": (245, 166, 35),
         "error": (194, 65, 12)}


def icon_image(kind="ready", size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = COLOR.get(kind, COLOR["ready"])
    d.ellipse((2, 2, size - 2, size - 2), fill=c)
    s = size / 64  # a microphone
    d.rounded_rectangle((25 * s, 12 * s, 39 * s, 38 * s), radius=7 * s, fill="white")
    d.arc((18 * s, 22 * s, 46 * s, 46 * s), 0, 180, fill="white", width=int(3 * s))
    d.line((32 * s, 46 * s, 32 * s, 52 * s), fill="white", width=int(3 * s))
    d.line((24 * s, 52 * s, 40 * s, 52 * s), fill="white", width=int(3 * s))
    return img
