"""Offline 800x480 rice-leaf recognition UI using the supplied ASCII fonts."""
import numpy as np

from .peripherals import load_data


# Logical, unrotated coordinates. GT911 converts physical touch into these logical coordinates.
BUTTONS = {"detect": (20, 432, 244, 40), "light": (278, 432, 244, 40),
           "save": (536, 432, 244, 40)}

LABEL_TEXT = {
    "healthy": ("Healthy leaf", "No visible disease", "HEALTHY"),
    "bacterial_leaf_blight": ("Bacterial blight", "Rice leaf disease", "IDENTIFIED"),
    "brown_spot": ("Brown spot", "Rice leaf disease", "IDENTIFIED"),
    "leaf_blast": ("Leaf blast", "Rice leaf disease", "IDENTIFIED"),
    "leaf_scald": ("Leaf scald", "Rice leaf disease", "IDENTIFIED"),
    "narrow_brown": ("Narrow brown", "Rice leaf spot disease", "IDENTIFIED"),
}


class LeafUI:
    WIDTH, HEIGHT = 800, 480
    BUTTONS = BUTTONS
    BG = 0xF4F7F5
    WHITE = 0xFFFFFF
    INK = 0x16352F
    NAVY = 0x203C4B
    MUTED = 0x6B8178
    GREEN = 0x16704D
    BORDER = 0xDFE9E3
    PALE = 0xE9F3EC

    def __init__(self, data_dir=None):
        self._fonts = {}
        for size in (12, 16, 24, 32):
            width, groups = size // 2, (size + 7) // 8
            packed = np.frombuffer(load_data("font{}.bin".format(size), data_dir), np.uint8)
            columns = packed.reshape(95, width, groups)
            self._fonts[size] = np.unpackbits(columns, axis=2)[:, :, :size].transpose(0, 2, 1).astype(bool)
        self._pixels = np.zeros((self.HEIGHT, self.WIDTH, 3), np.uint8)

    @staticmethod
    def _bgr(color):
        return np.array([color & 255, (color >> 8) & 255, (color >> 16) & 255], dtype=np.float32)

    def _blend(self, x, y, mask, color):
        h, w = mask.shape
        x0, y0, x1, y1 = max(0, x), max(0, y), min(self.WIDTH, x + w), min(self.HEIGHT, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        alpha = mask[y0 - y:y1 - y, x0 - x:x1 - x, None]
        area = self._pixels[y0:y1, x0:x1]
        area[:] = np.clip(area * (1 - alpha) + self._bgr(color) * alpha, 0, 255).astype(np.uint8)

    def _rounded(self, x, y, w, h, radius, color, alpha=1.0):
        yy, xx = np.mgrid[:h, :w].astype(np.float32)
        qx = np.abs(xx + 0.5 - w / 2) - (w / 2 - radius)
        qy = np.abs(yy + 0.5 - h / 2) - (h / 2 - radius)
        distance = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - radius
        self._blend(x, y, np.clip(0.5 - distance, 0, 1) * alpha, color)

    def _line(self, x1, y1, x2, y2, color, width=1.5):
        pad = int(width + 2)
        x, y = int(min(x1, x2)) - pad, int(min(y1, y2)) - pad
        w, h = int(abs(x2 - x1)) + pad * 2 + 1, int(abs(y2 - y1)) + pad * 2 + 1
        yy, xx = np.mgrid[:h, :w].astype(np.float32)
        dx, dy = x2 - x1, y2 - y1
        denominator = dx * dx + dy * dy
        t = np.clip(((xx + x - x1) * dx + (yy + y - y1) * dy) / max(denominator, 0.001), 0, 1)
        distance = np.hypot(xx + x - (x1 + t * dx), yy + y - (y1 + t * dy))
        self._blend(x, y, np.clip(width / 2 + 0.5 - distance, 0, 1), color)

    def _text(self, x, y, text, size=16, color=None, bold=False):
        color = self.INK if color is None else color
        width = size // 2
        for char in str(text):
            if not 32 <= ord(char) <= 126:
                raise ValueError("LeafUI supports original offline ASCII fonts only")
            glyph = self._fonts[size][ord(char) - 32]
            # Extra weight crowds the tiny original 6/8-pixel glyph cells.
            if bold and size >= 24:
                glyph = np.pad(glyph, ((0, 0), (0, 1)))
                glyph[:, 1:] |= glyph[:, :-1].copy()
            self._blend(x, y, glyph.astype(np.float32), color)
            x += width

    def _center_text(self, x, y, width, text, size=16, color=None, bold=False):
        self._text(x + (width - len(text) * (size // 2)) // 2, y, text, size, color, bold)

    def _leaf(self, cx, cy, size, color, vein):
        side = int(size * 2)
        yy, xx = np.mgrid[:side, :side].astype(np.float32)
        xx, yy = xx - side / 2, yy - side / 2
        u, v = (xx + yy) / 1.4142, (yy - xx) / 1.4142
        radius = np.sqrt((u / (size * 0.32)) ** 2 + (v / (size * 0.65)) ** 2)
        self._blend(int(cx - side / 2), int(cy - side / 2), np.clip((1 - radius) * size / 2, 0, 1), color)
        self._line(cx - size * 0.36, cy + size * 0.36, cx + size * 0.36, cy - size * 0.36, vein, max(1.2, size / 35))
        for offset in (-0.2, 0.05, 0.28):
            px, py = cx + offset * size, cy - offset * size
            self._line(px, py, px - size * 0.22, py - size * 0.03, vein, max(1, size / 60))

    def hit_test(self, x, y):
        for action, (bx, by, width, height) in BUTTONS.items():
            if bx <= x < bx + width and by <= y < by + height:
                return action
        return None

    def render(self, frame_bgr=None, label=None, latency_ms=None, light=False,
               status="Ready", saved_count=0):
        if label is not None and label not in LABEL_TEXT:
            raise ValueError("Unknown model label: " + str(label))
        if latency_ms is not None and (not np.isfinite(latency_ms) or latency_ms < 0):
            raise ValueError("Latency must be finite and nonnegative")
        if saved_count < 0 or int(saved_count) != saved_count:
            raise ValueError("Saved count must be a nonnegative integer")
        self._pixels[:] = self._bgr(self.BG)

        # A compact header leaves room for the camera and finger-size actions.
        self._rounded(20, 10, 40, 40, 12, self.GREEN)
        self._leaf(40, 30, 24, 0xDCF1D9, 0x7CC092)
        self._text(72, 5, "Leaf Health", 32, self.INK, True)
        self._text(74, 39, "RICE DISEASE RECOGNITION", 12, self.MUTED)
        self._rounded(612, 15, 168, 30, 15, self.PALE)
        self._rounded(625, 26, 8, 8, 4, self.GREEN)
        self._text(643, 22, "PYNQ + FPGA", 16, self.GREEN, True)
        self._rounded(20, 59, 760, 1, 0, self.BORDER)

        # Preview has 336x336 visible pixels, sourced from the original 224x224.
        self._rounded(20, 70, 352, 352, 18, 0xDCE7E0, 0.35)
        self._rounded(20, 68, 352, 352, 18, self.WHITE)
        if frame_bgr is not None:
            frame = np.asarray(frame_bgr)
            if frame.shape != (224, 224, 3) or frame.dtype != np.uint8:
                raise ValueError("Camera preview expects (224,224,3) uint8 BGR888")
            index = np.arange(336) * 224 // 336
            preview = frame[index[:, None], index[None, :]]
            # Rounded image corners use the same coverage mask as the card.
            self._pixels[76:412, 28:364] = preview
            # Apply corners by restoring the card outside a rounded inner shape.
            yy, xx = np.mgrid[:336, :336].astype(np.float32)
            qx = np.abs(xx + .5 - 168) - 154
            qy = np.abs(yy + .5 - 168) - 154
            d = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - 14
            self._blend(28, 76, np.clip(d + .5, 0, 1), self.WHITE)
            self._rounded(40, 88, 116, 26, 13, self.WHITE, .92)
            self._rounded(50, 97, 7, 7, 4, self.GREEN)
            self._text(65, 94, "LIVE VIEW", 12, self.GREEN, True)
            self._rounded(40, 376, 196, 24, 12, self.NAVY, .80)
            self._text(52, 382, "224 x 224  |  BGR CAMERA", 12, self.WHITE)
        else:
            self._rounded(28, 76, 336, 336, 14, 0xEAF1E9)
            for x in range(52, 344, 32):
                self._line(x, 96, x, 392, 0xE0E9DF, 1)
            for y in range(100, 394, 32):
                self._line(48, y, 344, y, 0xE0E9DF, 1)
            self._rounded(112, 160, 168, 160, 28, 0xEAF1E9, .85)
            self._leaf(196, 218, 96, 0xA3C6A1, 0xEAF1E9)
            self._center_text(28, 290, 336, "CAMERA PREVIEW", 16, self.GREEN, True)
            self._center_text(28, 317, 336, "Waiting for the first frame", 12, self.MUTED)

        # The result is the visual focus, without inventing confidence scores.
        self._rounded(390, 68, 390, 204, 18, self.WHITE)
        self._text(412, 86, "LATEST SCAN", 16, self.MUTED, True)
        if label is None:
            self._rounded(652, 85, 108, 22, 11, 0xEDF2F4)
            self._center_text(652, 90, 108, "WAITING", 12, self.NAVY, True)
            self._text(412, 130, "Ready to scan", 32, self.NAVY, True)
            self._text(412, 177, "Place one rice leaf in view.", 16, self.MUTED)
            self._text(412, 202, "Tap Detect to identify it.", 16, self.MUTED)
            self._rounded(412, 245, 346, 3, 1, 0xE5EEEA)
        else:
            title, subtitle, tag = LABEL_TEXT[label]
            healthy = label == "healthy"
            self._rounded(652, 85, 108, 22, 11, self.PALE if healthy else 0xF8EEE0)
            self._center_text(652, 90, 108, tag, 12, self.GREEN if healthy else 0x9E6A26, True)
            # Long labels fit as two balanced lines rather than compressed text.
            if len(title) > 18:
                first, second = title.rsplit(" ", 1)
                self._text(412, 123, first, 32, self.NAVY, True)
                self._text(412, 157, second, 32, self.NAVY, True)
                subtitle_y = 205
            else:
                self._text(412, 135, title, 32, self.NAVY, True)
                subtitle_y = 187
            self._text(412, subtitle_y, subtitle, 16, self.MUTED)
            self._rounded(412, 245, 346, 3, 1, self.PALE if healthy else 0xF3E6D3)
            self._rounded(412, 245, 82, 3, 1, self.GREEN if healthy else 0xB88946)

        self._rounded(390, 286, 188, 76, 15, self.WHITE)
        self._rounded(592, 286, 188, 76, 15, self.WHITE)
        self._text(408, 297, "INFERENCE TIME", 12, self.MUTED, True)
        latency_text = "--" if latency_ms is None else "{:.0f}".format(latency_ms)
        self._text(408, 319, latency_text[:7], 24, self.NAVY, True)
        self._text(408 + min(len(latency_text), 7) * 12 + 8, 325, "ms", 16, self.MUTED)
        self._text(610, 297, "SAVED SAMPLES", 12, self.MUTED, True)
        self._text(610, 319, str(int(saved_count))[:9], 24, self.NAVY, True)

        self._rounded(390, 376, 390, 44, 14, self.PALE)
        self._rounded(406, 393, 8, 8, 4, self.GREEN)
        status_text = str(status).replace("\n", " ")
        status_text = status_text[:40] + ("..." if len(status_text) > 40 else "")
        self._text(425, 391, status_text, 16, self.GREEN)

        for action, (x, y, width, height) in BUTTONS.items():
            fill = self.GREEN if action == "detect" else (0xDCEEDC if action == "light" and light else self.WHITE)
            ink = self.WHITE if action == "detect" else self.GREEN
            self._rounded(x, y, width, height, 12, self.BORDER)
            self._rounded(x + 1, y + 1, width - 2, height - 2, 11, fill)
            title = {"detect": "Detect leaf", "light": "Light ON" if light else "Light OFF", "save": "Save sample"}[action]
            self._center_text(x, y + 8, width, title, 24, ink, True)
            if action == "light" and light:
                self._rounded(x + 18, y + 16, 8, 8, 4, self.GREEN)
        return self._pixels.copy()

    def physical_frame(self, frame=None):
        """Apply original LCD_FLIP_DISPLAY=1 rotation once, for MM2S output."""
        if frame is None:
            frame = self._pixels
        frame = np.asarray(frame)
        if frame.shape != (480, 800, 3) or frame.dtype != np.uint8:
            raise ValueError("Expected (480,800,3) uint8 BGR frame")
        return np.ascontiguousarray(frame[::-1, ::-1])
