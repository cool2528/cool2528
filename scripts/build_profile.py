#!/usr/bin/env python3
"""生成个人主页 README 用到的全部 SVG 面板（深色、浅色各一份）。

  build_profile.py static [目录=assets]   头图 + 技术栈，不联网，结果提交进 main
  build_profile.py live   [目录=dist]     项目卡片 + 统计，读 GitHub API，由 Actions 推到 output 分支

文字先用 HarfBuzz 排版，再转成路径写进 SVG：README 里的图片加载不了外部字体，
转成路径后各平台看到的字形和排版完全一致，胶囊、对齐也能按真实字宽计算。

依赖：pip install -r scripts/requirements.txt
环境变量 GITHUB_TOKEN 可选；没有时走匿名 API，并且不显示贡献数。
"""
import json
import os
import random
import sys
import urllib.request
from functools import lru_cache
from pathlib import Path

import uharfbuzz as hb

USER = "cool2528"
HERE = Path(__file__).resolve().parent
W = 840          # 整宽面板的宽度，约等于 GitHub 个人主页 README 的内容宽度
CARD_W = 416     # 半宽卡片
GUTTER = 8       # 并排两张卡片之间的间隙：左右卡片各带 4px 透明边，README 里两张图各占 50% 且紧挨着
FEATURE_H = 229  # 主推卡片的高度，与右侧截图（assets/gdownload-app-*.png，416 × 229）等高

# ───────────────────────── 配色 ─────────────────────────
# 强调色取自 GDownload 的 Aurora 标志（青 → 蓝 → 紫）。
# fill 用于图形，ink 用于小字（浅色主题下需要更深才够对比度）。
THEMES = {
    "dark": dict(
        bg="#0A0F1A", recess="#060A12", line="#1E2636", cell="#FFFFFF", cell_op=0.05,
        hi="#EDF2FA", text="#A7B2C6", dim="#77839B",
        fill=("#35D8EE", "#5AA9FF", "#A78BFA"),
        ink=("#4FDCF0", "#6FB3FF", "#B49CFB"),
        chip="#111827", glow=0.20, shadow=0.55,
        neutral=("#66718B", "#4A546C", "#353E53", "#262D3D"),
    ),
    "light": dict(
        bg="#F5F7FB", recess="#EBEFF6", line="#DAE0EB", cell="#0E1524", cell_op=0.055,
        hi="#0E1524", text="#414C60", dim="#667189",
        fill=("#0AA3C2", "#2F7DF0", "#7B50E6"),
        ink=("#0A7A92", "#1F63D6", "#6A3FD8"),
        chip="#FFFFFF", glow=0.16, shadow=0.16,
        neutral=("#8490A6", "#A5AEC0", "#C3CAD8", "#DBE0EA"),
    ),
}


def _hex(c):
    return [int(c[i:i + 2], 16) for i in (1, 3, 5)]


def ramp(stops, t):
    """沿 青→蓝→紫 取色，t ∈ [0, 1]。"""
    t = min(max(t, 0.0), 1.0) * (len(stops) - 1)
    i = min(int(t), len(stops) - 2)
    a, b, f = _hex(stops[i]), _hex(stops[i + 1]), t - i
    return "#%02X%02X%02X" % tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))


def n(v):
    """把数字写成最短的 SVG 数值。"""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


# ───────────────────────── 排版 ─────────────────────────
MONO_FILES = {400: "IBMPlexMono-Regular.ttf", 500: "IBMPlexMono-Medium.ttf", 600: "IBMPlexMono-SemiBold.ttf"}


@lru_cache(maxsize=None)
def _font(family, weight):
    name = "IBMPlexSans.ttf" if family == "sans" else MONO_FILES[weight]
    face = hb.Face(hb.Blob.from_file_path(str(HERE / "fonts" / name)))
    assert face.upem == 1000
    font = hb.Font(face)
    if family == "sans":
        font.set_variations({"wght": weight})
    return font


@lru_cache(maxsize=None)
def shape(s, family, weight):
    buf = hb.Buffer()
    buf.add_str(s)
    buf.guess_segment_properties()
    hb.shape(_font(family, weight), buf)
    out = []
    for ch, info, pos in zip(s, buf.glyph_infos, buf.glyph_positions):
        if info.codepoint == 0:
            raise ValueError(f"字体里没有这个字符：{ch!r}（出自 {s!r}）")
        out.append((info.codepoint, pos.x_advance, pos.x_offset, pos.y_offset))
    return tuple(out)


def measure(s, size, family="sans", weight=400, track=0.0):
    g = shape(s, family, weight)
    return sum(a for _, a, _, _ in g) * size / 1000 + track * max(len(g) - 1, 0)


def wrap(s, max_w, size, family="sans", weight=400):
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if cur and measure(trial, size, family, weight) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


class _Pen:
    def __init__(self):
        self.d = []

    def moveTo(self, p):
        self.d.append("M%d %d" % (round(p[0]), round(p[1])))

    def lineTo(self, p):
        self.d.append("L%d %d" % (round(p[0]), round(p[1])))

    def qCurveTo(self, c, p):
        self.d.append("Q%d %d %d %d" % (round(c[0]), round(c[1]), round(p[0]), round(p[1])))

    def curveTo(self, a, b, p):
        self.d.append("C%d %d %d %d %d %d" % tuple(round(v) for v in (*a, *b, *p)))

    def closePath(self):
        self.d.append("Z")

    def endPath(self):
        pass


# 24×24 vector outlines from Simple Icons 14.15.0 (CC0-1.0).
# https://github.com/simple-icons/simple-icons/tree/14.15.0/icons
# Use a lighter or darker tint of each brand color on its chip surface.
SKILL_ICONS = {
    "C++17 / 20": ("cplusplus", "#77BCF7", "#00599C"),
    "Qt 6": ("qt", "#61CD80", "#187B3B"),
    "FFmpeg": ("ffmpeg", "#75CD74", "#227832"),
    "CMake": ("cmake", "#71BCF3", "#13649B"),
    "GitHub Actions": ("githubactions", "#69B3FF", "#1267C7"),
    "Python": ("python", "#FFDB68", "#3670A0"),
    "TypeScript": ("typescript", "#7BB8F2", "#3178C6"),
    "Lua": ("lua", "#ACAEFF", "#42448A"),
}
ICON_PATHS = json.loads((HERE / "skill-icons.json").read_text(encoding="utf-8"))


class Canvas:
    def __init__(self, w, h, theme, side=None):
        """side：半宽卡片在一行里的位置（"L" / "R"），决定透明边留在哪一侧。"""
        self.w, self.h, self.t, self.side = w, h, THEMES[theme], side
        self.theme = theme
        self.glyphs, self.defs, self.body, self.css = {}, [], [], []

    def add(self, s):
        self.body.append(s)

    def _glyph(self, family, weight, gid):
        key = f"{family[0]}{weight // 100}g{gid}"
        if key not in self.glyphs:
            pen = _Pen()
            _font(family, weight).draw_glyph_with_pen(gid, pen)
            self.glyphs[key] = "".join(pen.d)
        return key if self.glyphs[key] else None

    def text(self, x, y, s, size, fill, *, font="sans", weight=400, anchor="start", track=0.0, opacity=None):
        """画一行字（转成路径），返回这行字的宽度。"""
        width = measure(s, size, font, weight, track)
        if anchor == "end":
            x -= width
        elif anchor == "middle":
            x -= width / 2
        k = size / 1000
        uses, pen = [], 0.0
        for gid, adv, xo, yo in shape(s, font, weight):
            ref = self._glyph(font, weight, gid)
            if ref:
                uses.append(f'<use href="#{ref}" x="{round(pen + xo)}"' + (f' y="{yo}"' if yo else "") + "/>")
            pen += adv + track / k
        op = f' opacity="{n(opacity)}"' if opacity is not None else ""
        self.add(f'<g transform="translate({n(x)} {n(y)}) scale({k:.4f} -{k:.4f})" fill="{fill}"{op}>{"".join(uses)}</g>')
        return width

    def rect(self, x, y, w, h, rx=0, fill="none", stroke=None, extra=""):
        s = f' stroke="{stroke}"' if stroke else ""
        self.add(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(rx)}" fill="{fill}"{s}{extra}/>')

    def panel(self, rx=14):
        """面板底：圆角、细描边。"""
        self.rect(0.5, 0.5, self.w - 1, self.h - 1, rx, self.t["bg"], self.t["line"])

    def piece(self, x, y, size, fill, extra=""):
        """一个“分片”小方块 —— 整套设计反复出现的母题。"""
        self.rect(x, y, size, size, size * 0.23, fill, extra=extra)

    def chip(self, x, y, label, h=26, size=11.5):
        icon = SKILL_ICONS.get(label)
        icon_size, icon_gap = 15, 5
        inset = icon_size + icon_gap if icon else 0
        w = measure(label, size, "mono", 400) + 22 + inset
        self.rect(x + 0.5, y + 0.5, w - 1, h - 1, 7, self.t["chip"], self.t["line"])
        if icon:
            slug, dark, light = icon
            color = dark if self.theme == "dark" else light
            self.add(f'<path id="logo-{slug}" fill="{color}" d="{ICON_PATHS[slug]}" '
                     f'transform="translate({n(x + 11)} {n(y + (h - icon_size) / 2)}) scale({icon_size / 24})"/>')
        self.text(x + 11 + inset, y + h / 2 + size * 0.34, label, size, self.t["text"], font="mono")
        return w

    def star(self, cx, cy, r, fill):
        import math
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.42
            pts.append(f"{n(cx + rr * math.cos(a))},{n(cy + rr * math.sin(a))}")
        self.add(f'<polygon points="{" ".join(pts)}" fill="{fill}"/>')

    def render(self, title, desc):
        glyphs = "".join(f'<path id="{k}" d="{d}"/>' for k, d in self.glyphs.items() if d)
        css = f"<style>{''.join(self.css)}</style>" if self.css else ""
        outer = self.w + (GUTTER // 2 if self.side else 0)
        body = "".join(self.body)
        if self.side == "R":
            body = f'<g transform="translate({GUTTER // 2} 0)">{body}</g>'
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{outer}" height="{self.h}" '
            f'viewBox="0 0 {outer} {self.h}" role="img" aria-labelledby="t d">'
            f'<title id="t">{esc(title)}</title><desc id="d">{esc(desc)}</desc>{css}'
            f'<defs>{glyphs}{"".join(self.defs)}</defs>{body}</svg>\n'
        )


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ───────────────────────── 头图 ─────────────────────────
# 名字用“下载分片图”拼出来：每个小方块是一个分片，按到达顺序依次点亮。
LETTERS = {
    "c": [".######", "#######", "##.....", "##.....", "##.....", "#######", ".######"],
    "o": [".#####.", "#######", "##...##", "##...##", "##...##", "#######", ".#####."],
    "l": ["##"] * 10,
}
ROWS = 10


def wordmark_cells(word="cool"):
    cells, col = [], 0
    for ch in word:
        rows = LETTERS[ch]
        top = ROWS - len(rows)
        for r, line in enumerate(rows):
            cells += [(col + c, top + r) for c, v in enumerate(line) if v == "#"]
        col += len(rows[0]) + 1
    return cells, col - 1


def hero(theme):
    t = THEMES[theme]
    cv = Canvas(W, 318, theme)
    m, cols, gap = 44, 47, 3.0
    pitch = (W - 2 * m + gap) / cols
    cell = pitch - gap
    y0 = 40
    cells, word_cols = wordmark_cells()
    rng = random.Random(2528)

    # 底：面板 + 两团极淡的“极光”
    cv.defs.append(
        f'<radialGradient id="ga" cx="0.86" cy="0.02" r="0.6"><stop offset="0" stop-color="{t["fill"][2]}" stop-opacity="{t["glow"]}"/>'
        f'<stop offset="1" stop-color="{t["fill"][2]}" stop-opacity="0"/></radialGradient>'
        f'<radialGradient id="gb" cx="0.1" cy="1.05" r="0.55"><stop offset="0" stop-color="{t["fill"][0]}" stop-opacity="{t["glow"] * 0.7}"/>'
        f'<stop offset="1" stop-color="{t["fill"][0]}" stop-opacity="0"/></radialGradient>'
        f'<pattern id="field" x="{n(m)}" y="{n(y0)}" width="{n(pitch)}" height="{n(pitch)}" patternUnits="userSpaceOnUse">'
        f'<rect width="{n(cell)}" height="{n(cell)}" rx="{n(cell * 0.23)}" fill="{t["cell"]}" fill-opacity="{t["cell_op"]}"/></pattern>'
    )
    cv.panel()
    for g in ("ga", "gb"):
        cv.rect(1, 1, W - 2, cv.h - 2, 13, f"url(#{g})")

    # 分片图：整行都是“待下载”的空位
    cv.rect(m, y0, W - 2 * m, ROWS * pitch - gap, 0, "url(#field)")

    cv.css.append(
        ".p{animation:p .36s cubic-bezier(.2,.8,.3,1.25) both;transform-box:fill-box;transform-origin:center}"
        "@keyframes p{from{opacity:.14;transform:scale(.72)}to{opacity:1;transform:none}}"
        ".s{animation:s 7s ease-in-out infinite both}"
        "@keyframes s{0%,100%{opacity:.1}50%{opacity:.7}}"
        "@media (prefers-reduced-motion:reduce){.p,.s{animation:none}}"
    )

    # 名字：大体从左到右到达，夹杂一些乱序。起始帧是暗的“待下载”分片而不是全透明，
    # 这样只截取第一帧的渲染器里名字也认得出来
    for c, r in sorted(cells):
        delay = 250 + 1500 * c / word_cols + rng.uniform(0, 650)
        color = ramp(t["fill"], c / word_cols)
        cv.piece(m + c * pitch, y0 + r * pitch, cell, color, f' class="p" style="animation-delay:{delay:.0f}ms"')

    # 右侧零星的分片：越往右越稀，缓慢明灭，像仍在到达
    taken = set(cells)
    for c in range(word_cols + 3, cols):
        for r in range(ROWS):
            f = (c - word_cols - 3) / (cols - word_cols - 3)
            if (c, r) in taken or rng.random() > 0.26 * (1 - f) ** 1.4 + 0.02:
                continue
            color = ramp(t["fill"], rng.random())
            cv.piece(m + c * pitch, y0 + r * pitch, cell, color,
                     f' class="s" style="animation-delay:-{rng.uniform(0, 7):.1f}s;animation-duration:{rng.uniform(5, 9):.1f}s"')

    # 分片图下方的状态行
    base = y0 + ROWS * pitch - gap + 22
    cv.text(m, base, f"github.com/{USER}", 10.5, t["dim"], font="mono", track=0.3)
    cv.text(W - m, base, f"{len(cells)} / {len(cells)} pieces  ·  verified", 10.5, t["dim"], font="mono", anchor="end", track=0.3)

    cv.text(m, base + 46, "C++ desktop & systems developer", 28, t["hi"], weight=600, track=-0.3)
    cv.text(m, base + 74, "Download engines, wire protocols and cross-platform Qt apps. And Windows binaries, taken apart.",
            15, t["text"])
    return cv.render(
        "cool — C++ desktop & systems developer",
        "The name cool spelled out of download pieces that arrive one by one, in cyan, blue and violet.",
    )


# ───────────────────────── 技术栈 ─────────────────────────
# 从像素到字节：一个桌面应用自上而下的每一层，以及体现这一层的开源项目。
STACK = [
    ("Interface", ["Qt 6", "QML", "Qt Widgets", "Win32 / GDI", "CEF", "Duilib"], "GDownload"),
    ("Media & vision", ["FFmpeg", "NVENC · AMF · QSV", "OpenGL", "libVLC", "ncnn", "YOLO", "OCR"], "VideoHardwareEncoding"),
    ("Concurrency", ["C++17 / 20", "coroutines", "Boost.Asio", "thread pools", "async I/O"], "ed2k-engine-cpp  ·  ThreadPool"),
    ("Protocols", ["HTTP", "BitTorrent", "eD2k / Kad", "aria2", "Tars / JCE"], "ed2k-engine-cpp  ·  tarswire"),
    ("Binaries", ["x86 / x64 asm", "PE internals", "static analysis", "debugging", "DLL proxying"], "010Forge  ·  uninstalltool-keygen-cpp"),
]
TOOLCHAIN = ["CMake", "vcpkg", "GitHub Actions", "Python", "TypeScript", "Lua"]


def chip_row(cv, x, y, labels, limit=W - 44):
    """一行胶囊；超出右边界直接报错，而不是悄悄画出面板。"""
    for label in labels:
        x += cv.chip(x, y, label) + 7
    assert x - 7 <= limit, f"这一行胶囊超出了右边界：{labels}"


def stack(theme):
    t = THEMES[theme]
    row_h, top = 70, 40
    cv = Canvas(W, top + row_h * len(STACK) + 78, theme)
    cv.panel()
    rail_x, name_x, chip_x = 50, 78, 232
    last = len(STACK) - 1
    node = lambda i: top + i * row_h + 26

    cv.defs.append(
        f'<linearGradient id="rail" x1="0" y1="0" x2="0" y2="1">'
        + "".join(f'<stop offset="{i / 2}" stop-color="{c}"/>' for i, c in enumerate(t["fill"]))
        + "</linearGradient>"
    )
    cv.rect(rail_x - 1, node(0), 2, node(last) - node(0), 0, "url(#rail)", extra=' opacity=".55"')
    cv.text(rail_x, node(0) - 17, "PIXELS", 8.5, t["dim"], font="mono", weight=500, anchor="middle", track=1.1)
    cv.text(rail_x, node(last) + 25, "BYTES", 8.5, t["dim"], font="mono", weight=500, anchor="middle", track=1.1)

    for i, (name, chips, proof) in enumerate(STACK):
        y = top + i * row_h
        if i:
            cv.rect(name_x, y - 0.5, W - name_x - 44, 1, 0, t["line"])
        cv.rect(rail_x - 9, node(i) - 9, 18, 18, 0, t["bg"])
        cv.piece(rail_x - 5.5, node(i) - 5.5, 11, ramp(t["fill"], i / last))
        cv.text(name_x, y + 31.5, name, 16.5, t["hi"], weight=600)
        chip_row(cv, chip_x, y + 13, chips)
        w = cv.text(chip_x + 1, y + 56, "in", 10.5, t["dim"], font="mono")
        cv.text(chip_x + 1 + w + 8, y + 56, proof, 10.5, t["text"], font="mono")

    y = top + row_h * len(STACK) + 8
    cv.rect(44, y - 0.5, W - 88, 1, 0, t["line"])
    cv.text(name_x, y + 39, "Toolchain", 16.5, t["hi"], weight=600)
    chip_row(cv, chip_x, y + 21, TOOLCHAIN)
    return cv.render(
        "Stack: from pixels to bytes",
        "Five layers, top to bottom. "
        + " ".join(f"{name}: {', '.join(chips)} (seen in {proof.replace('  ·  ', ' and ')})." for name, chips, proof in STACK)
        + f" Toolchain: {', '.join(TOOLCHAIN)}.",
    )


# ───────────────────────── 项目卡片 ─────────────────────────
# layer：0 → 1 对应技术栈里从“像素”到“字节”的位置，决定卡片的强调色。
# strip：卡片底部那行“证据”——分段写，a = 强调，d = 次要，其余为正文色。
CARDS = [
    dict(repo="ed2k-engine-cpp", side="L", kind="PROTOCOL ENGINE", meta="C++20 · MIT", layer=0.75,
         desc="From-scratch eD2k / eMule engine on Boost.Asio coroutines. Wire formats verified byte for byte against aMule.",
         strip=[("E3", "a"), (" │ ", "d"), ("size:u32", ""), (" │ ", "d"), ("opcode", ""), (" │ ", "d"), ("payload …", "")],
         note="eD2k frame"),
    dict(repo="tarswire", side="R", kind="WIRE CODEC", meta="C++ · MIT", layer=0.75,
         desc="Tars / JCE codec, query and builder library, with a CLI that turns raw hex dumps into JSON.",
         strip=[("0x32", "a"), ("  →  ", "d"), ("tag 3", ""), (" │ ", "d"), ("type Int", "")],
         note="field head"),
    dict(repo="VideoHardwareEncoding", side="L", kind="MEDIA", meta="C++ · MIT", layer=0.25,
         desc="Screen recording through FFmpeg, hardware-encoded on whichever GPU the machine has.",
         strip=[("NVENC", "a"), (" │ ", "d"), ("AMF", "a"), (" │ ", "d"), ("QSV", "a")],
         note="NVIDIA · AMD · Intel"),
    dict(repo="linguist-ai", side="R", kind="TOOLING", meta="Python", layer=0.5,
         desc="Batch-translates Qt .ts files with LLM and MT engines, keeping placeholders and markup intact.",
         strip=[("\"Open ", ""), ("%1", "a"), ("\"", ""), ("  →  ", "d"), ("\"", ""), ("%1", "a"), (" öffnen\"", "")],
         note="placeholders kept"),
    dict(repo="010Forge", side="L", kind="WINDOWS INTERNALS", meta="C++ · Win32", layer=1.0,
         desc="I traced how 010 Editor loads interface text to localize its menus and dialogs. Content hashes guard file replacement.",
         strip=[("PE resources", "a"), ("  ·  ", "d"), ("localization", ""), ("  ·  ", "d"), ("rollback", "")],
         note=""),
    dict(repo="uninstalltool-keygen-cpp", side="R", kind="ALGORITHM RECOVERY", meta="C++20 · Win32", layer=1.0,
         desc="I modeled a Windows binary's arithmetic in C++20 and checked the recovered model against regression fixtures.",
         strip=[("Finite fields", "a"), ("  ·  ", "d"), ("round-trip tests", "")],
         note="offline"),
]


def compact(v):
    return f"{v / 1000:.1f}k".replace(".0k", "k") if v >= 1000 else str(v)


def stars_badge(cv, x_right, y, stars, size=12):
    """右对齐的 ★ 数字，没有星标时不画。"""
    if not stars:
        return
    t = cv.t
    w = cv.text(x_right, y, compact(stars), size, t["text"], font="mono", weight=500, anchor="end")
    cv.star(x_right - w - size * 0.75, y - size * 0.36, size * 0.5, t["text"])


def strip_line(cv, x, y, w, segs, note, layer, h=34):
    t = cv.t
    cv.rect(x, y, w, h, 8, t["recess"])
    cx, base = x + 13, y + h / 2 + 4
    for s, role in segs:
        fill = {"a": ramp(t["ink"], layer), "d": t["dim"]}.get(role, t["text"])
        cx += cv.text(cx, base, s, 11.5, fill, font="mono", weight=500 if role == "a" else 400)
    if note and cx + measure(note, 10, "mono") + 26 < x + w:
        cv.text(x + w - 13, base - 0.5, note, 10, t["dim"], font="mono", anchor="end")


def card(theme, spec, stars):
    t = THEMES[theme]
    cv = Canvas(CARD_W, 190, theme, spec["side"])
    cv.panel(12)
    pad = 22
    cv.piece(pad, 25, 9, ramp(t["fill"], spec["layer"]))
    cv.text(pad + 17, 33.5, spec["kind"], 10, t["dim"], font="mono", weight=500, track=1.0)
    cv.text(CARD_W - pad, 33.5, spec["meta"], 10, t["dim"], font="mono", anchor="end")
    cv.text(pad, 66, spec["repo"], 20, t["hi"], weight=600, track=-0.1)
    stars_badge(cv, CARD_W - pad, 65, stars)
    lines = wrap(spec["desc"], CARD_W - 2 * pad, 13.5)
    assert len(lines) <= 2, f"{spec['repo']} 的简介超过两行"
    for i, line in enumerate(lines):
        cv.text(pad, 91 + i * 19.5, line, 13.5, t["text"])
    strip_line(cv, pad, 134, CARD_W - 2 * pad, spec["strip"], spec["note"], spec["layer"])
    return cv.render(spec["repo"], spec["desc"])


def feature(theme, stars, release):
    """主推项目 GDownload 的文字卡片；README 里它右边并排放一张真实界面截图。"""
    t = THEMES[theme]
    cv = Canvas(CARD_W, FEATURE_H, theme, "L")
    cv.panel(12)
    pad = 22
    cv.piece(pad, 25, 9, ramp(t["fill"], 0))
    cv.text(pad + 17, 33.5, "FLAGSHIP · DOWNLOAD MANAGER", 10, t["dim"], font="mono", weight=500, track=1.0)
    cv.text(CARD_W - pad, 33.5, "C++20 · Qt 6", 10, t["dim"], font="mono", anchor="end")
    cv.text(pad, 72, "GDownload", 27, t["hi"], weight=600, track=-0.3)
    x = CARD_W - pad
    if release:
        x -= cv.text(x, 70, release, 12, t["dim"], font="mono", anchor="end") + 14
    stars_badge(cv, x, 70, stars)
    desc = ("Cross-platform download manager. HTTP, BitTorrent and eD2k in one client, built on aria2 and "
            "my own eD2k engine, with cloud-drive plugins and a browser extension.")
    lines = wrap(desc, CARD_W - 2 * pad, 13.5)
    assert len(lines) <= 3, "GDownload 的简介超过三行"
    for i, line in enumerate(lines):
        cv.text(pad, 99 + i * 19.5, line, 13.5, t["text"])
    strip_line(cv, pad, 173, CARD_W - 2 * pad,
               [("Windows", "a"), (" │ ", "d"), ("macOS", "a"), (" │ ", "d"), ("Linux", "a")], "AGPL-3.0", 0)
    return cv.render("GDownload", desc + " Runs on Windows, macOS and Linux. AGPL-3.0.")


# ───────────────────────── 统计 ─────────────────────────
def stats(theme, data):
    t = THEMES[theme]
    cv = Canvas(W, 178, theme)
    cv.panel()
    pad = 32
    tiles = [(k, v) for k, v in (
        ("Stars earned", data["stars"]), ("Forks", data["forks"]),
        ("Followers", data["followers"]), ("Contributions, past year", data["contributions"]),
    ) if v is not None]
    col = (W - 2 * pad) / len(tiles)
    for i, (label, value) in enumerate(tiles):
        x = pad + i * col
        if i:
            cv.rect(x - 22, 30, 1, 46, 0, t["line"])
        cv.text(x, 58, f"{value:,}", 30, t["hi"], weight=600, track=-0.4)
        cv.text(x, 80, label, 12, t["dim"])

    # 语言占比：一条细分段条。C++ 用强调色，其余用递减的中性灰；名称和占比写在下方。
    langs = data["langs"]
    bar_y, bar_h, gap = 108, 8, 2
    total_w = W - 2 * pad - gap * (len(langs) - 1)
    colors = [ramp(t["fill"], 0.5)] + [t["neutral"][min(i, 3)] for i in range(len(langs) - 1)]
    cv.defs.append(f'<clipPath id="bar"><rect x="{pad}" y="{bar_y}" width="{W - 2 * pad}" height="{bar_h}" rx="{bar_h / 2}"/></clipPath>')
    x = pad
    segs = []
    for (name, share), color in zip(langs, colors):
        w = max(share * total_w, 1.5)
        segs.append(f'<rect x="{n(x)}" y="{bar_y}" width="{n(w)}" height="{bar_h}" fill="{color}"/>')
        x += w + gap
    cv.add(f'<g clip-path="url(#bar)">{"".join(segs)}</g>')
    x = pad
    for (name, share), color in zip(langs, colors):
        cv.piece(x, 136.5, 9, color)
        x += 16
        x += cv.text(x, 145, name, 12, t["text"]) + 6
        pct = f"{share * 100:.0f}%" if share >= 0.01 else "<1%"
        x += cv.text(x, 145, pct, 12, t["hi"], weight=600) + 22
    cv.text(W - pad, 145, "by bytes, public non-fork repos", 10.5, t["dim"], font="mono", anchor="end")
    return cv.render(
        "GitHub at a glance",
        "; ".join(f"{label}: {value:,}" for label, value in tiles) + ". Languages by bytes: "
        + ", ".join(f"{name} {share * 100:.0f}%" for name, share in langs) + ".",
    )


# ───────────────────────── 数据 ─────────────────────────
def api(url, payload=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload else None)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch():
    user = api(f"https://api.github.com/users/{USER}")
    repos, page = [], 1
    while True:
        batch = api(f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"] and not r["private"]]
    sizes = {}
    for r in own:
        for lang, size in api(r["languages_url"]).items():
            sizes[lang] = sizes.get(lang, 0) + size
    total = sum(sizes.values()) or 1
    ranked = sorted(sizes.items(), key=lambda kv: -kv[1])
    langs = [(k, v / total) for k, v in ranked[:4]]
    rest = sum(v for _, v in ranked[4:]) / total
    if rest > 0:
        langs.append(("Other", rest))

    contributions = None
    if os.environ.get("GITHUB_TOKEN"):
        q = 'query{user(login:"%s"){contributionsCollection{contributionCalendar{totalContributions}}}}' % USER
        try:
            res = api("https://api.github.com/graphql", {"query": q})
            contributions = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        except Exception as e:  # 贡献数拿不到就不显示这一格，其余照常生成
            print(f"跳过贡献数：{e}", file=sys.stderr)
    try:
        release = api(f"https://api.github.com/repos/{USER}/GDownload/releases/latest")["tag_name"]
    except Exception as e:
        print(f"跳过 GDownload 版本号：{e}", file=sys.stderr)
        release = None
    return dict(
        stars=sum(r["stargazers_count"] for r in own), forks=sum(r["forks_count"] for r in own),
        followers=user["followers"], contributions=contributions, langs=langs, release=release,
        repo_stars={r["name"]: r["stargazers_count"] for r in own},
    )


# ───────────────────────── 入口 ─────────────────────────
def write(outdir, name, theme, svg):
    path = Path(outdir) / f"{name}-{theme}.svg"
    path.write_text(svg, encoding="utf-8")
    print(f"{path}  {len(svg) / 1024:.1f} KB")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("static", "live"):
        sys.exit(__doc__)
    outdir = sys.argv[2] if len(sys.argv) > 2 else {"static": "assets", "live": "dist"}[mode]
    os.makedirs(outdir, exist_ok=True)
    if mode == "static":
        for theme in THEMES:
            write(outdir, "hero", theme, hero(theme))
            write(outdir, "stack", theme, stack(theme))
        return
    data = fetch()
    for theme in THEMES:
        write(outdir, "gdownload", theme, feature(theme, data["repo_stars"].get("GDownload"), data["release"]))
        for spec in CARDS:
            write(outdir, spec["repo"], theme, card(theme, spec, data["repo_stars"].get(spec["repo"])))
        write(outdir, "stats", theme, stats(theme, data))


if __name__ == "__main__":
    main()
