"""The Island pill as liquid glass, like Apple's: clear, not black. What's behind it shows
through, softly frosted, bent at the rim like light through a thick lens; a light tint keeps
it readable, bright specular light runs along the edge (strongest top-left and bottom-right),
there's a glow just inside the rim and a soft shadow under it. The words and icons turn dark
over a bright screen and white over a dark one, like Apple's.

How: the strip of screen behind the pill is read (in memory only, never saved or sent; our own
window is kept out of screen capture so it never sees itself), turned into glass with Pillow,
and shown in a layered window with per-pixel alpha (smooth edges, a real shadow). render() is
pure Pillow, so the previews and tests run anywhere; Window is the Windows part.

A side effect of keeping the pill out of screen capture: screenshots and recordings don't show
it. Where Windows can't do that (before Windows 10 2004), the screen is read only while the
pill is hidden, so it never sees itself, and the glass refreshes when the next message comes."""
import ctypes
import math
import sys
import time

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont

WINDOWS = sys.platform == "win32"
MARGIN = 18             # around the capsule, for the shadow and the lens (layout units)
H = 42                  # the capsule's height when open (layout units)
COMPACT = (120, 38)
ACCENT = {"listen": (229, 72, 77), "ok": (70, 167, 88), "error": (247, 107, 21), "info": (110, 120, 255),
          "busy": (120, 126, 140)}
BADGE = {"Discord": (88, 101, 242)}

_fonts = {}


def font(size, bold=False):
    """Segoe UI on Windows (Semibold for the words), a similar sans elsewhere (previews)."""
    key = (round(size), bold)
    if key not in _fonts:
        names = (["seguisb.ttf", "segoeuib.ttf"] if bold else ["segoeui.ttf"]) + \
                (["/usr/share/fonts/noto/NotoSans-SemiBold.ttf", "/usr/share/fonts/noto/NotoSans-Bold.ttf",
                  "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"] if bold else
                 ["/usr/share/fonts/noto/NotoSans-Medium.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf"])
        for n in names:
            try:
                _fonts[key] = ImageFont.truetype(n, key[0])
                break
            except OSError:
                continue
        else:
            _fonts[key] = ImageFont.load_default()
    return _fonts[key]


def _measure(text, size, bold=False):
    return font(size, bold).getlength(text)


def fit(text, size, room, bold=False):
    if _measure(text, size, bold) <= room:
        return text
    while text and _measure(text + "…", size, bold) > room:
        text = text[:-1]
    return text.rstrip() + "…"


def layout(m, room, show_timing=False):
    """(width, text, right) of the open capsule for message m, in layout units (100 %)."""
    kind = m["kind"]
    text = m["text"]
    if kind == "listen" and text == "Listening…":
        text = "Listening"
    elif kind == "ok" and m.get("title"):
        text = m["title"]
    elif kind == "ok" and len(m.get("chips") or []) > 1:
        text = " → ".join(m["chips"])
    elif kind == "error" and m.get("title"):
        text = f"{m['title']}: “{text}”"
    right = ""
    if kind == "ok" and m.get("footer") and show_timing:
        right = m["footer"].split(" · ")[0]
    badge = _measure(f"FROM {m['source'].upper()}", 9, True) + 24 if m.get("source") else 0
    extra = (40 if kind == "listen" else 0) + (_measure(right, 11) + 14 if right else 0)
    text = fit(text, 14, room - 70 - badge - extra, True)
    return min(room, max(210, 52 + badge + _measure(text, 14, True) + 22 + extra)), text, right


# ----------------------------------------------------------------- the glass
_cache = {}


def _cached(key, make):
    """Masks and lens meshes depend only on the size: made once per size (the morph goes
    through a few dozen; the cache is emptied when it gets big)."""
    key = key + (MARGIN_PX[0],)
    got = _cache.get(key)
    if got is None:
        if len(_cache) > 240:
            _cache.clear()
        got = _cache[key] = make()
    return got


def _shape(w, h, k=2):
    """The capsule's mask, smooth-edged (drawn 3x larger, then scaled down), with MARGIN around."""
    def make():
        W, Hh, M = w + 2 * MARGIN_PX[0], h + 2 * MARGIN_PX[0], MARGIN_PX[0]
        big = Image.new("L", (W * k, Hh * k), 0)
        ImageDraw.Draw(big).rounded_rectangle([M * k, M * k, (M + w) * k - 1, (M + h) * k - 1], radius=h * k / 2, fill=255)
        return big.resize((W, Hh), Image.BOX)
    return _cached(("shape", w, h), make)


MARGIN_PX = [MARGIN]  # MARGIN in pixels at the current scale (set by render)


def _ring(w, h, inset, width, k=2):
    """A thin ring just inside the capsule's edge (for the rim light)."""
    def make():
        M = MARGIN_PX[0]
        W, Hh = w + 2 * M, h + 2 * M
        big = Image.new("L", (W * k, Hh * k), 0)
        d = ImageDraw.Draw(big)
        x0, y0, x1, y1 = (M + inset) * k, (M + inset) * k, (M + w - inset) * k - 1, (M + h - inset) * k - 1
        d.rounded_rectangle([x0, y0, x1, y1], radius=(h / 2 - inset) * k, fill=255)
        d.rounded_rectangle([x0 + width * k, y0 + width * k, x1 - width * k, y1 - width * k],
                            radius=max(1, (h / 2 - inset - width) * k), fill=0)
        return big.resize((W, Hh), Image.BOX)
    return _cached(("ring", w, h, inset, width), make)


def _light(w, h, a, b, c):
    """A smooth diagonal light: a at the top-left, b in the middle, c at the bottom-right."""
    M = MARGIN_PX[0]
    tiny = Image.new("L", (3, 3))
    tiny.putdata([a, (a + b) // 2, b, (a + b) // 2, b, (b + c) // 2, b, (b + c) // 2, c])
    return tiny.resize((w + 2 * M, h + 2 * M), Image.BILINEAR)


def _lens(back, w, h, strength):
    """Bend the backdrop at the rim like a thick lens: near the edge each point shows what's a
    little further out, squeezed in (Pillow's mesh transform; the middle stays as it is)."""
    M = MARGIN_PX[0]
    W, Hh = w + 2 * M, h + 2 * M
    return back.transform((W, Hh), Image.MESH, _cached(("lens", w, h, round(strength, 1)), lambda: _mesh(w, h, strength)),
                          Image.BILINEAR)


def _mesh(w, h, strength):
    """The lens as mesh cells: small ones at the round ends and along the top and bottom rims,
    one wide column across the straight middle (there the bend is only up and down)."""
    M = MARGIN_PX[0]
    W, Hh = w + 2 * M, h + 2 * M
    r = h / 2
    band = r * 0.9
    step = max(4, int(h / 7))

    def src(x, y):
        px, py = x - M, y - M
        cx = min(max(px, r), w - r)   # nearest point on the capsule's middle line
        dx, dy = px - cx, py - r
        dist = math.hypot(dx, dy)
        d = r - dist                  # distance inside the edge
        if dist < 1e-6 or d < 0 or d > band:
            return x, y
        amt = strength * (1 - d / band) ** 2
        return x + dx / dist * amt, y + dy / dist * amt
    left, right = int(M + r), int(M + w - r)
    xs = sorted(set(list(range(0, left, step)) + [left] + ([right] if right > left else []) + list(range(right, W, step)) + [W]))
    ys = sorted(set(list(range(0, Hh, step)) + [Hh]))
    mesh = []
    for y, y1 in zip(ys, ys[1:]):
        for x, x1 in zip(xs, xs[1:]):
            mesh.append(((x, y, x1, y1), src(x, y) + src(x, y1) + src(x1, y1) + src(x1, y)))
    return mesh


def render(back, w, h, m, t=0.0, lv=0.0, fade=1.0, scale=1.0, show_timing=False, text=None, right=""):
    """The pill as an RGBA image (w x h capsule in screen pixels, MARGIN around it).
    back: the screen behind it, the same size as the result (RGB). fade 0..1: the words."""
    w, h = int(round(w)), int(round(h))
    MARGIN_PX[0] = M = int(round(MARGIN * scale))
    W, Hh = w + 2 * M, h + 2 * M
    back = back.convert("RGB").resize((W, Hh)) if back.size != (W, Hh) else back.convert("RGB")
    shape = _shape(w, h)
    # the glass: lens at the rim, a light frost, a little more colour, as Apple's does
    glass = _lens(back, w, h, strength=h * 0.45)
    glass = glass.filter(ImageFilter.GaussianBlur(2.6 * scale))
    glass = ImageEnhance.Color(glass).enhance(1.35)
    inside = glass.crop((M + h // 4, M + h // 4, M + w - h // 4, M + h - h // 4)).convert("L").resize((8, 2))
    lum = sum(inside.getdata()) / 16
    bright = lum > 140
    # a tint that keeps the words readable: white haze over a dark screen, a light one over a bright one
    haze = Image.new("RGB", (W, Hh), (255, 255, 255))
    glass = Image.blend(glass, haze, 0.20 if bright else 0.10)
    if not bright:
        glass = ImageEnhance.Brightness(glass).enhance(0.82)
    out = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    # the soft shadow under it
    shadow = _cached(("shadow", w, h), lambda: shape.filter(ImageFilter.GaussianBlur(8 * scale)).point(lambda v: int(v * 0.30)))
    out.paste((0, 0, 0, 255), (0, int(3 * scale)), shadow)
    gl = glass.convert("RGBA")
    gl.putalpha(shape)
    out = Image.alpha_composite(out, gl)
    # light: a glow just inside the edge, and the specular rim (top-left and bottom-right)
    def light():  # all of it depends only on the size: made once per size, then one paste each
        glow = ImageChops.subtract(shape, _shape_inset(w, h, 5 * scale).filter(ImageFilter.GaussianBlur(4 * scale)))
        rim = ImageChops.multiply(_ring(w, h, 0.6, 1.4 * scale), _light(w, h, 255, 70, 200))
        sheen = ImageChops.multiply(_top(W, Hh, M, h), shape)
        white = ImageChops.add(ImageChops.add(glow.point(lambda v: int(v * 0.28)), rim), sheen)
        edge = ImageChops.multiply(_ring(w, h, 0, 0.9 * scale), _light(w, h, 90, 40, 70))
        return white, edge
    white, edge = _cached(("light", w, h), light)
    out.paste((255, 255, 255), (0, 0), white)
    out.paste((0, 0, 0), (0, 0), edge)  # a faint dark outline, so it reads over white too
    if fade > 0:
        _content(out, m, w, h, M, t, lv, fade, scale, bright, show_timing, text, right)
    return out


def _shape_inset(w, h, inset, k=2):
    def make():
        M = MARGIN_PX[0]
        big = Image.new("L", ((w + 2 * M) * k, (h + 2 * M) * k), 0)
        ImageDraw.Draw(big).rounded_rectangle([(M + inset) * k, (M + inset) * k, (M + w - inset) * k, (M + h - inset) * k],
                                              radius=max(1, (h / 2 - inset) * k), fill=255)
        return big.resize((w + 2 * M, h + 2 * M), Image.BOX)
    return _cached(("inset", w, h, round(inset, 1)), make)


def _top(W, Hh, M, h):
    """A brighter top half, fading out by the middle (the glass catching the light from above)."""
    g = Image.new("L", (1, 64))
    g.putdata([int(46 * (1 - i / 63) ** 2) for i in range(64)])
    band = g.resize((W, int(h * 0.6)))
    out = Image.new("L", (W, Hh), 0)
    out.paste(band, (0, M))
    return out


# ----------------------------------------------------------------- what's on it
def _content(out, m, w, h, M, t, lv, fade, scale, bright, show_timing, text, right):
    """Icon, words, badge, waveform: drawn twice the size and scaled down, for smooth edges."""
    k = 2
    kind = m["kind"]
    ink = (18, 19, 24) if bright else (255, 255, 255)
    soft = (60, 63, 74) if bright else (225, 228, 238)
    accent = ACCENT.get(kind, ACCENT["info"])
    W, Hh = out.size
    layer = Image.new("RGBA", (W * k, Hh * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    s = scale * k
    cy = (M + h / 2) * k
    x0 = M * k
    ix = x0 + 26 * s
    r = 9 * s
    if kind == "listen":
        for i in range(4):
            amp = 0.3 + 0.7 * max(lv, 0.18 + 0.12 * math.sin(t * 4 + i))
            bh = r * 1.9 * amp * (0.55 + 0.45 * abs(math.sin(t * 7.5 + i * 1.3)))
            bx = ix - r + i * (r * 2 / 3.4)
            d.rounded_rectangle([bx, cy - bh / 2, bx + 3.2 * s, cy + bh / 2], radius=1.6 * s, fill=accent)
    elif kind == "busy":
        a = (t * 400) % 360
        d.ellipse([ix - r, cy - r, ix + r, cy + r], outline=soft + (90,), width=int(2.2 * s))
        d.arc([ix - r, cy - r, ix + r, cy + r], start=a, end=a + 100, fill=ink, width=int(2.2 * s))
    else:
        p = min(1.0, t / 0.32)
        kk = r * (1 + 2.2 * (p - 1) ** 3 + 1.2 * (p - 1) ** 2) if kind in ("ok", "error") else r * 0.6
        d.ellipse([ix - kk, cy - kk, ix + kk, cy + kk], fill=accent)
        if kind == "ok" and kk > r * 0.4:
            d.line([(ix - kk * 0.45, cy), (ix - kk * 0.1, cy + kk * 0.36), (ix + kk * 0.48, cy - kk * 0.34)],
                   fill=(255, 255, 255), width=int(2.4 * s), joint="curve")
        elif kind == "error" and kk > r * 0.4:
            d.line([(ix, cy - kk * 0.5), (ix, cy + kk * 0.12)], fill=(255, 255, 255), width=int(2.4 * s))
            d.ellipse([ix - 1.4 * s, cy + kk * 0.36, ix + 1.4 * s, cy + kk * 0.64], fill=(255, 255, 255))
    x = x0 + 46 * s
    if m.get("source"):
        label = f"FROM {m['source'].upper()}"
        f = font(9 * s, True)
        bw = f.getlength(label) + 16 * s
        d.rounded_rectangle([x, cy - 10 * s, x + bw, cy + 10 * s], radius=10 * s, fill=BADGE.get(m["source"], accent))
        d.text((x + bw / 2, cy), label, font=f, fill=(255, 255, 255), anchor="mm")
        x += bw + 8 * s
    if text:
        d.text((x, cy), text, font=font(14 * s, True), fill=ink, anchor="lm")
    xr = x0 + w * k - 20 * s
    if kind == "listen":
        for i in range(5):
            amp = 0.25 + 0.75 * max(lv, 0.12)
            bh = (4 + 16 * amp * (0.5 + 0.5 * math.sin(t * 8 + i * 1.1))) * s
            bx = xr - 30 * s + i * 7 * s
            d.rounded_rectangle([bx, cy - bh / 2, bx + 4 * s, cy + bh / 2], radius=2 * s, fill=accent)
        xr -= 42 * s
    if right:
        d.text((xr, cy), right, font=font(11 * s), fill=soft, anchor="rm")
    layer = layer.resize((W, Hh), Image.BOX)  # (exactly half: a box filter is as smooth, and quicker)
    if fade < 1:
        a = layer.getchannel("A").point(lambda v: int(v * fade))
        layer.putalpha(a)
    out.alpha_composite(layer)


# ----------------------------------------------------------------- the window (Windows)
_api = {}


def _win32():
    """Private copies of user32 / gdi32 / kernel32 with exact 64-bit types on every call used here
    (handles must not be cut to 32 bits), so other code's own types for these calls aren't touched."""
    if _api:
        return _api
    from ctypes import wintypes as wt
    u = ctypes.WinDLL("user32", use_last_error=True)
    g = ctypes.WinDLL("gdi32", use_last_error=True)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                    ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                    ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON)]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]

    class BLENDFUNCTION(ctypes.Structure):
        _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte), ("SourceConstantAlpha", ctypes.c_ubyte),
                    ("AlphaFormat", ctypes.c_ubyte)]

    def proto(fn, res, *args):
        fn.restype, fn.argtypes = res, list(args)
        return fn
    P = ctypes.POINTER
    _api.update(
        wt=wt, WNDPROC=WNDPROC, WNDCLASSEXW=WNDCLASSEXW, BITMAPINFOHEADER=BITMAPINFOHEADER, BLENDFUNCTION=BLENDFUNCTION,
        GetModuleHandleW=proto(k.GetModuleHandleW, wt.HMODULE, wt.LPCWSTR),
        DefWindowProcW=proto(u.DefWindowProcW, LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM),
        RegisterClassExW=proto(u.RegisterClassExW, wt.ATOM, P(WNDCLASSEXW)),
        CreateWindowExW=proto(u.CreateWindowExW, wt.HWND, wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int,
                              ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID),
        SetWindowDisplayAffinity=proto(u.SetWindowDisplayAffinity, wt.BOOL, wt.HWND, wt.DWORD),
        ShowWindow=proto(u.ShowWindow, wt.BOOL, wt.HWND, ctypes.c_int),
        SetWindowPos=proto(u.SetWindowPos, wt.BOOL, wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                           ctypes.c_int, wt.UINT),
        GetDC=proto(u.GetDC, wt.HDC, wt.HWND),
        ReleaseDC=proto(u.ReleaseDC, ctypes.c_int, wt.HWND, wt.HDC),
        UpdateLayeredWindow=proto(u.UpdateLayeredWindow, wt.BOOL, wt.HWND, wt.HDC, P(wt.POINT), P(wt.SIZE), wt.HDC,
                                  P(wt.POINT), wt.COLORREF, P(BLENDFUNCTION), wt.DWORD),
        CreateCompatibleDC=proto(g.CreateCompatibleDC, wt.HDC, wt.HDC),
        CreateDIBSection=proto(g.CreateDIBSection, wt.HBITMAP, wt.HDC, ctypes.c_void_p, wt.UINT, P(ctypes.c_void_p),
                               wt.HANDLE, wt.DWORD),
        SelectObject=proto(g.SelectObject, wt.HGDIOBJ, wt.HDC, wt.HGDIOBJ),
        DeleteObject=proto(g.DeleteObject, wt.BOOL, wt.HGDIOBJ),
        DeleteDC=proto(g.DeleteDC, wt.BOOL, wt.HDC),
    )
    return _api


class Window:
    """A click-through, never-focused, topmost layered window that shows an RGBA image with
    per-pixel alpha (UpdateLayeredWindow), and reads the screen behind it."""

    CLASS = "WvaLiquidGlass"

    def __init__(self):
        a = self.a = _win32()
        wt = a["wt"]
        self._proc = a["WNDPROC"](lambda hw, msg, wp, lp: a["DefWindowProcW"](hw, msg, wp, lp))
        hinst = a["GetModuleHandleW"](None)
        wc = a["WNDCLASSEXW"](ctypes.sizeof(a["WNDCLASSEXW"]), 0, self._proc, 0, 0, hinst, None, None, None, None,
                              self.CLASS, None)
        if not a["RegisterClassExW"](ctypes.byref(wc)) and ctypes.get_last_error() != 1410:  # 1410: already there
            raise OSError(f"RegisterClassExW failed ({ctypes.get_last_error()})")
        # WS_EX_LAYERED | TOPMOST | TOOLWINDOW | NOACTIVATE | TRANSPARENT (clicks go through), WS_POPUP
        self.hwnd = a["CreateWindowExW"](0x80000 | 0x8 | 0x80 | 0x08000000 | 0x20, self.CLASS, "", 0x80000000,
                                         0, 0, 1, 1, None, None, hinst, None)
        if not self.hwnd:
            raise OSError(f"CreateWindowExW failed ({ctypes.get_last_error()})")
        self.excluded = bool(a["SetWindowDisplayAffinity"](self.hwnd, 0x11))  # WDA_EXCLUDEFROMCAPTURE
        a["ShowWindow"](self.hwnd, 4)  # SW_SHOWNOACTIVATE (it's invisible until it gets an image)
        self.shown = False
        self.rect = (0, 0, 0, 0)
        self.wt = wt

    def backdrop(self, x, y, w, h):
        """The screen under (x, y, w, h), without this window in it."""
        from PIL import ImageGrab
        try:
            # the main screen (where the pill is), in its own pixels; layered windows (the pill
            # itself) aren't in it either way
            return ImageGrab.grab(bbox=(x, y, x + w, y + h)).convert("RGB")
        except Exception:
            return Image.new("RGB", (w, h), (90, 90, 100))

    def can_read_behind(self):
        return self.excluded or not self.shown

    def show(self, img, x, y, alpha=255):
        """Put the RGBA image on screen at (x, y) with an overall opacity (0..255). Raises if
        Windows refuses (the pill then falls back to the black island)."""
        a, wt = self.a, self.wt
        w, h = img.size
        data = img.convert("RGBa").tobytes("raw", "BGRa")
        bih = a["BITMAPINFOHEADER"](ctypes.sizeof(a["BITMAPINFOHEADER"]), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        screen = a["GetDC"](None)
        mem = a["CreateCompatibleDC"](screen)
        bits = ctypes.c_void_p()
        bmp = a["CreateDIBSection"](screen, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0)
        try:
            if not bmp or not bits.value:
                raise OSError(f"CreateDIBSection failed ({ctypes.get_last_error()})")
            ctypes.memmove(bits, data, len(data))
            old = a["SelectObject"](mem, bmp)
            pos, size, src = wt.POINT(int(x), int(y)), wt.SIZE(w, h), wt.POINT(0, 0)
            blend = a["BLENDFUNCTION"](0, 0, max(0, min(255, int(alpha))), 1)  # AC_SRC_ALPHA
            ok = a["UpdateLayeredWindow"](self.hwnd, screen, ctypes.byref(pos), ctypes.byref(size), mem,
                                          ctypes.byref(src), 0, ctypes.byref(blend), 2)  # ULW_ALPHA
            a["SelectObject"](mem, old)
            if not ok:
                raise OSError(f"UpdateLayeredWindow failed ({ctypes.get_last_error()})")
        finally:
            if bmp:
                a["DeleteObject"](bmp)
            a["DeleteDC"](mem)
            a["ReleaseDC"](None, screen)
        self.shown = alpha > 0
        self.rect = (int(x), int(y), w, h)

    def hide(self):
        if self.shown:
            self.show(Image.new("RGBA", (1, 1)), self.rect[0], self.rect[1], 0)
        self.shown = False

    def on_top(self):
        self.a["SetWindowPos"](self.hwnd, ctypes.c_void_p(-1 & 0xFFFFFFFFFFFFFFFF), 0, 0, 0, 0, 0x1 | 0x2 | 0x10)


def now():
    return time.monotonic()
