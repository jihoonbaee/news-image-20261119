#!/usr/bin/env python3
"""news-image-20261119 -- one image summing up Thursday 19 November 2026.

Draws a newspaper-style front page (1024x1024 PNG) with pure Python
standard library only: no network, no third-party packages, no fonts on
disk. Text is rendered with a small built-in 5x7 bitmap font stored as
bitmask rows, and the PNG is encoded by hand (zlib + struct). Output is
fully deterministic: the same data always produces byte-identical output.

Run:  MAKEFUN_OUTPUT_DIR=out python3 main.py
Writes: $MAKEFUN_OUTPUT_DIR/entry.png

Coverage: full-day edition, reported by 23:59 UTC 19 Nov 2026.
Headlines render at scale 4 across ~850 px, about 34 characters per
line, max 2 lines. Sub-texts render at scale 2, about 69 characters
per line, max 2 lines.
"""

import binascii
import math
import os
import struct
import sys
import zlib

# ---------------------------------------------------------------------------
# The day's stories (full-day edition, reported by 23:59 UTC 19 Nov 2026).
# Sources are listed in BUILD-REPORT.md. Every story below was reported on
# 19 November 2026 (UTC) or first reported that day in some time zone.
# ---------------------------------------------------------------------------

STORIES = [
    {
        "kicker": "THE HAGUE  |  JUSTICE",
        "headline": "ICJ: MYANMAR COMMITTED GENOCIDE",
        "sub": "World court rules 9-6, a first: a state held responsible for "
               "genocide; orders trials, laws and reparations.",
        "color": (166, 30, 30),       # crimson
        "icon": "globe",
    },
    {
        "kicker": "CHINA  |  SUMMIT",
        "headline": "TRUMP, XI AND PUTIN MEET IN SHENZHEN",
        "sub": "First three-way summit ends with a pledge of nuclear-risk "
               "talks; no binding arms cuts agreed.",
        "color": (180, 100, 30),      # brick orange
        "icon": "globe",
    },
    {
        "kicker": "GAZA  |  CONFLICT",
        "headline": "ISRAELI TANKS CROSS GAZA CEASEFIRE LINE",
        "sub": "Raid ends after a day; about 6,000 fled as tanks crossed the "
               "Yellow Line. Hamas calls it a truce breach.",
        "color": (120, 72, 20),       # desert brown
        "icon": "tank",
    },
    {
        "kicker": "UKRAINE  |  WAR",
        "headline": "CRIMEAN BRIDGE ATTACKED AGAIN",
        "sub": "Third strike on the crossing in four days; traffic halted and "
               "Putin vows a harsher response.",
        "color": (20, 90, 160),       # blue
        "icon": "bridge",
    },
    {
        "kicker": "TECH  |  MARKETS",
        "headline": "ANTHROPIC'S $81.3BN IPO DEBUTS",
        "sub": "Shares open at $111.50, close $97.17, up 17%; the largest IPO "
               "by base deal size.",
        "color": (30, 120, 70),       # green
        "icon": "chart",
    },
    {
        "kicker": "GAMING  |  CULTURE",
        "headline": "GTA VI ARRIVES AFTER 13-YEAR WAIT",
        "sub": "Gamers enter Vice City as Rockstar's blockbuster begins its "
               "global rollout after 13 years.",
        "color": (110, 60, 160),      # purple
        "icon": "gamepad",
    },
]

ALSO_TODAY = (
    "ALSO: 300,000 flee Cyclone Akvan; Wall St slides 2%; EU 45bn euro "
    "Ukraine loan; Van Gogh $190.4m record"
)

DATE_LINE = "THURSDAY, 19 NOVEMBER 2026"
TITLE_LINE = "THE WORLD IN ONE PICTURE"
SUB_LINE = "Six stories that defined the day - the full day, 19 November 2026"
FOOT_NOTE = "Full sources in BUILD-REPORT.md"

# ---------------------------------------------------------------------------
# 5x7 bitmap font. Each glyph is 7 rows; each row is a 5-bit integer, bit 4
# (value 16) is the leftmost pixel. Uppercase, lowercase, digits and common
# punctuation. Unknown characters fall back to '?'.
# ---------------------------------------------------------------------------

GLYPHS = {
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0F, 0x10, 0x10, 0x10, 0x10, 0x10, 0x0F),
    "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0F, 0x10, 0x10, 0x17, 0x11, 0x11, 0x0E),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "a": (0x00, 0x00, 0x0F, 0x01, 0x0F, 0x11, 0x0F),
    "b": (0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x1E),
    "c": (0x00, 0x00, 0x0F, 0x10, 0x10, 0x10, 0x0F),
    "d": (0x01, 0x01, 0x0F, 0x11, 0x11, 0x11, 0x0F),
    "e": (0x00, 0x00, 0x0E, 0x11, 0x1F, 0x10, 0x0E),
    "f": (0x06, 0x08, 0x08, 0x1F, 0x08, 0x08, 0x08),
    "g": (0x00, 0x00, 0x0F, 0x11, 0x11, 0x0E, 0x01),
    "h": (0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x11),
    "i": (0x00, 0x04, 0x00, 0x0C, 0x04, 0x04, 0x0E),
    "j": (0x00, 0x02, 0x00, 0x06, 0x02, 0x02, 0x06),
    "k": (0x10, 0x10, 0x12, 0x14, 0x18, 0x14, 0x12),
    "l": (0x0C, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "m": (0x00, 0x00, 0x1A, 0x15, 0x15, 0x15, 0x15),
    "n": (0x00, 0x00, 0x1E, 0x11, 0x11, 0x11, 0x11),
    "o": (0x00, 0x00, 0x0E, 0x11, 0x11, 0x11, 0x0E),
    "p": (0x00, 0x00, 0x1E, 0x11, 0x11, 0x1E, 0x10),
    "q": (0x00, 0x00, 0x0F, 0x11, 0x11, 0x0F, 0x01),
    "r": (0x00, 0x00, 0x16, 0x19, 0x10, 0x10, 0x10),
    "s": (0x00, 0x00, 0x0F, 0x10, 0x0E, 0x01, 0x1E),
    "t": (0x08, 0x08, 0x1F, 0x08, 0x08, 0x08, 0x06),
    "u": (0x00, 0x00, 0x11, 0x11, 0x11, 0x13, 0x0D),
    "v": (0x00, 0x00, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "w": (0x00, 0x00, 0x11, 0x15, 0x15, 0x15, 0x0A),
    "x": (0x00, 0x00, 0x11, 0x0A, 0x04, 0x0A, 0x11),
    "y": (0x00, 0x00, 0x11, 0x11, 0x11, 0x0F, 0x01),
    "z": (0x00, 0x00, 0x1F, 0x02, 0x04, 0x08, 0x1F),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    "3": (0x1E, 0x01, 0x01, 0x0E, 0x01, 0x01, 0x1E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x0E, 0x10, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x02, 0x04, 0x04, 0x04),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x01, 0x0E),
    " ": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00),
    ".": (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x04),
    ",": (0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C, 0x08),
    ":": (0x00, 0x00, 0x04, 0x00, 0x00, 0x04, 0x00),
    ";": (0x00, 0x00, 0x04, 0x00, 0x0C, 0x0C, 0x08),
    "'": (0x08, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00),
    "-": (0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00),
    "(": (0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02),
    ")": (0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08),
    "&": (0x0E, 0x11, 0x0A, 0x04, 0x15, 0x12, 0x0D),
    "/": (0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10),
    "%": (0x11, 0x12, 0x02, 0x04, 0x08, 0x09, 0x11),
    "+": (0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00),
    "!": (0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04),
    "?": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04),
    "$": (0x04, 0x0F, 0x15, 0x0E, 0x0A, 0x1E, 0x04),
    "=": (0x00, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00),
    '"': (0x0A, 0x0A, 0x00, 0x00, 0x00, 0x00, 0x00),
    "*": (0x00, 0x0A, 0x04, 0x1F, 0x04, 0x0A, 0x00),
    "|": (0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "#": (0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A),
}

CELL_W, CELL_H = 5, 7


def text_px(text, scale):
    """Pixel width of text at the given scale (1 px gap between glyphs)."""
    if not text:
        return 0
    return len(text) * (CELL_W * scale + scale) - scale


def fold(text, max_px, scale):
    """Greedy word wrap; returns lines of at most max_px pixels."""
    per_char = CELL_W * scale + scale
    limit = max(1, max_px // per_char)
    out, cur = [], ""
    for word in text.split(" "):
        nxt = word if not cur else cur + " " + word
        if len(nxt) <= limit:
            cur = nxt
        else:
            if cur:
                out.append(cur)
            while len(word) > limit:
                out.append(word[:limit])
                word = word[limit:]
            cur = word
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------------------
# Sheet: an RGB image held as a bytearray, with rect / line / disc / text.
# ---------------------------------------------------------------------------

W, H = 1024, 1024
PAPER = (247, 243, 234)
INK = (24, 28, 38)
GREY = (84, 88, 96)
NAVY = (18, 30, 54)
GOLD = (201, 162, 39)
RED = (178, 34, 34)
WHITE = (255, 255, 255)
CARD = (255, 255, 255)
ROW_ALT = (240, 236, 226)


class Sheet:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.buf = bytearray(w * h * 3)
        self.rect(0, 0, w, h, bg)

    def _put(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i], self.buf[i + 1], self.buf[i + 2] = color

    def rect(self, x, y, w, h, color):
        xa, ya = max(0, x), max(0, y)
        xb, yb = min(self.w, x + w), min(self.h, y + h)
        for yy in range(ya, yb):
            base = (yy * self.w + xa) * 3
            for xx in range(xa, xb):
                i = base + (xx - xa) * 3
                self.buf[i], self.buf[i + 1], self.buf[i + 2] = color

    def seg(self, x0, y0, x1, y1, color):
        """Bresenham line."""
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self._put(x0, y0, color)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def disc(self, cx, cy, r, color):
        for yy in range(cy - r, cy + r + 1):
            span = int((r * r - (yy - cy) ** 2) ** 0.5)
            self.rect(cx - span, yy, 2 * span + 1, 1, color)

    def ring(self, cx, cy, r, color, thick=2):
        for t in range(thick):
            rr = r - t
            for yy in range(cy - rr, cy + rr + 1):
                span = int((rr * rr - (yy - cy) ** 2) ** 0.5)
                self._put(cx - span, yy, color)
                self._put(cx + span, yy, color)

    def glyph(self, x, y, ch, scale, color):
        rows = GLYPHS.get(ch, GLYPHS["?"])
        for r in range(CELL_H):
            bits = rows[r]
            for c in range(CELL_W):
                if bits & (1 << (CELL_W - 1 - c)):
                    self.rect(x + c * scale, y + r * scale,
                              scale, scale, color)

    def text(self, x, y, s, scale, color):
        cx = x
        for ch in s:
            self.glyph(cx, y, ch, scale, color)
            cx += (CELL_W + 1) * scale
        return cx

    def text_mid(self, x, y, w, s, scale, color):
        tw = text_px(s, scale)
        self.text(x + max(0, (w - tw) // 2), y, s, scale, color)


# ---------------------------------------------------------------------------
# Pictograms drawn in white inside each story's colour square (96x96).
# ---------------------------------------------------------------------------

def pictogram(sh, kind, x, y, size, color):
    sh.rect(x, y, size, size, color)
    c = WHITE
    cx, cy = x + size // 2, y + size // 2
    if kind == "globe":
        sh.ring(cx, cy, 34, c, 3)
        sh.seg(cx - 34, cy, cx + 34, cy, c)
        sh.seg(cx, cy - 34, cx, cy + 34, c)
        for dy, half in ((-18, 28), (18, 28)):
            sh.seg(cx - half, cy + dy, cx + half, cy + dy, c)
    elif kind == "tank":
        # Hull, turret, barrel, wheels.
        sh.rect(cx - 36, cy + 2, 72, 18, c)
        sh.rect(cx - 14, cy - 16, 30, 18, c)
        sh.rect(cx + 16, cy - 11, 26, 5, c)
        for wx in range(cx - 28, cx + 29, 14):
            sh.disc(wx, cy + 24, 5, c)
            sh.disc(wx, cy + 24, 2, color)
    elif kind == "bridge":
        # Deck, two towers, arch, cables, water.
        sh.rect(x + 8, cy + 10, size - 16, 4, c)
        sh.rect(cx - 26, cy - 30, 5, 44, c)
        sh.rect(cx + 21, cy - 30, 5, 44, c)
        sh.seg(cx - 24, cy + 10, cx, cy - 34, c)
        sh.seg(cx, cy - 34, cx + 24, cy + 10, c)
        for hx in (-12, 0, 12):
            sh.seg(cx + hx, cy - 22 + abs(hx) // 2, cx + hx, cy + 10, c)
        for wy in (cy + 26, cy + 34):
            for wx in range(x + 8, x + size - 8, 16):
                sh.seg(wx, wy, wx + 8, wy - 4, c)
                sh.seg(wx + 8, wy - 4, wx + 16, wy, c)
    elif kind == "chart":
        # Axes, rising line, arrowhead.
        sh.rect(x + 12, y + 12, 4, size - 24, c)
        sh.rect(x + 12, y + size - 16, size - 24, 4, c)
        pts = [(x + 20, cy + 26), (x + 38, cy + 8),
               (x + 56, cy + 16), (x + 80, cy - 22)]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            sh.seg(ax, ay, bx, by, c)
            sh.seg(ax, ay + 1, bx, by + 1, c)
        sh.seg(x + 80, cy - 22, x + 68, cy - 20, c)
        sh.seg(x + 80, cy - 22, x + 78, cy - 10, c)
    elif kind == "gamepad":
        # Body, grips, d-pad, buttons.
        sh.rect(x + 12, cy - 18, size - 24, 34, c)
        sh.disc(x + 20, cy + 20, 12, c)
        sh.disc(x + size - 20, cy + 20, 12, c)
        sh.rect(cx - 30, cy - 8, 8, 22, color)
        sh.rect(cx - 36, cy - 2, 20, 8, color)
        sh.disc(cx + 22, cy - 6, 5, color)
        sh.disc(cx + 32, cy + 4, 5, color)
    elif kind == "storm":
        # Cyclone spiral with a calm eye.
        t = 0.0
        while t < 4.6 * math.pi:
            r = 3 + t * 2.3
            px = int(cx + r * math.cos(t))
            py = int(cy + r * math.sin(t) * 0.9)
            sh.rect(px - 1, py - 1, 3, 3, c)
            t += 0.12
        sh.disc(cx, cy, 6, color)
        sh.ring(cx, cy, 7, c, 2)


# ---------------------------------------------------------------------------
# Layout and PNG encoding.
# ---------------------------------------------------------------------------

HEADER_H = 140
FOOTER_H = 76
MARGIN = 26
GAP = 10


def render():
    sh = Sheet(W, H, PAPER)

    # ---- Masthead ---------------------------------------------------------
    sh.rect(0, 0, W, HEADER_H, NAVY)
    sh.rect(0, HEADER_H - 6, W, 6, RED)
    sh.text_mid(0, 18, W, TITLE_LINE, 3, GOLD)
    sh.text_mid(0, 52, W, DATE_LINE, 5, WHITE)
    sh.text_mid(0, 104, W, SUB_LINE, 2, (198, 205, 218))

    # ---- Story rows -------------------------------------------------------
    top = HEADER_H + GAP
    rows_h = H - HEADER_H - FOOTER_H - 2 * GAP
    row_h = rows_h // len(STORIES)
    tx = MARGIN + 122
    tw = W - MARGIN - tx

    for i, st in enumerate(STORIES):
        y = top + i * row_h
        rh = row_h - 6
        bg = CARD if i % 2 == 0 else ROW_ALT
        sh.rect(MARGIN, y, W - 2 * MARGIN, rh, bg)
        sh.rect(MARGIN, y, 6, rh, st["color"])
        pictogram(sh, st["icon"], MARGIN + 14, y + (rh - 96) // 2, 96,
                  st["color"])

        sh.text(tx, y + 12, st["kicker"], 2, st["color"])
        heads = fold(st["headline"], tw, 4)
        hy = y + 34
        for line in heads[:2]:
            sh.text(tx, hy, line, 4, INK)
            hy += 30
        if len(heads) == 1:
            hy += 16
        subs = fold(st["sub"], tw, 2)
        sy = hy + 2
        for line in subs[:2]:
            sh.text(tx, sy, line, 2, GREY)
            sy += 17

    # ---- Footer -----------------------------------------------------------
    fy = H - FOOTER_H + 8
    sh.rect(0, H - FOOTER_H, W, 2, RED)
    for line in fold(ALSO_TODAY, W - 2 * MARGIN, 2)[:2]:
        sh.text(MARGIN, fy, line, 2, INK)
        fy += 17
    sh.text(MARGIN, fy + 4, FOOT_NOTE, 2, GREY)

    return png_bytes(sh)


def png_bytes(sh):
    """Encode the sheet as a PNG (colour type 2, 8-bit, filter 0)."""
    raw = bytearray()
    for yy in range(sh.h):
        raw.append(0)  # filter: none
        start = yy * sh.w * 3
        raw += sh.buf[start:start + sh.w * 3]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", sh.w, sh.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    return png


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    os.makedirs(out_dir, exist_ok=True)
    data = render()
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (path, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
