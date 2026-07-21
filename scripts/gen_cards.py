#!/usr/bin/env python3
"""生成个人主页统计卡片 SVG（tokyonight 配色，与 streak 卡片风格一致）。

用法: python3 scripts/gen_cards.py [输出目录]
需要环境变量 GITHUB_TOKEN（可选，无则走匿名 API）。
"""
import json
import os
import sys
import urllib.request

USER = "cool2528"

BG = "#1a1b27"
TITLE = "#70a5fd"
TEXT = "#a9b1d6"
VALUE = "#38bdae"
ACCENT = "#bf91f3"

LANG_COLORS = {
    "C++": "#f34b7d",
    "C": "#555555",
    "Python": "#3572A5",
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "Go": "#00ADD8",
    "CSS": "#663399",
    "HTML": "#e34c26",
    "Stylus": "#ff6347",
    "CMake": "#DA3434",
    "Shell": "#89e051",
    "Makefile": "#427819",
    "Objective-C": "#438eff",
    "CoffeeScript": "#244776",
}
FALLBACK_COLOR = "#8b949e"

FONT = "font-family=\"'Segoe UI', 'PingFang SC', 'Microsoft YaHei', Ubuntu, sans-serif\""


def api(url):
    req = urllib.request.Request(url)
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch():
    user = api(f"https://api.github.com/users/{USER}")
    repos = []
    page = 1
    while True:
        batch = api(f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}")
        repos += batch
        if len(batch) < 100:
            break
        page += 1
    own = [r for r in repos if not r["fork"]]
    langs = {}
    for r in own:
        try:
            for lang, size in api(r["languages_url"]).items():
                langs[lang] = langs.get(lang, 0) + size
        except Exception as e:
            print(f"跳过 {r['name']} 语言统计: {e}", file=sys.stderr)
    return user, own, langs


def stats_card(user, own):
    stars = sum(r["stargazers_count"] for r in own)
    forks = sum(r["forks_count"] for r in own)
    rows = [
        ("获得 Star 总数", f"{stars:,}"),
        ("被 Fork 总数", f"{forks:,}"),
        ("关注者", f"{user['followers']:,}"),
        ("原创仓库", f"{len(own):,}"),
    ]
    items = []
    for i, (label, value) in enumerate(rows):
        y = 78 + i * 28
        items.append(
            f'<g class="row" style="animation-delay:{300 + i * 150}ms">'
            f'<text x="25" y="{y}" fill="{ACCENT}" font-size="14">✦</text>'
            f'<text x="45" y="{y}" fill="{TEXT}" font-size="14">{label}</text>'
            f'<text x="442" y="{y}" fill="{VALUE}" font-size="14" font-weight="600" text-anchor="end">{value}</text>'
            f"</g>"
        )
    rows_svg = "".join(items)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="467" height="195" viewBox="0 0 467 195" {FONT}>
<style>
.row {{ opacity: 0; animation: fadein 0.5s ease forwards; }}
@keyframes fadein {{ to {{ opacity: 1; }} }}
</style>
<rect width="467" height="195" rx="10" fill="{BG}"/>
<text x="25" y="40" fill="{TITLE}" font-size="18" font-weight="600">cool2528 的 GitHub 数据</text>
{rows_svg}
</svg>
"""


def langs_card(langs):
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:8]
    bar_x, bar_w = 25, 300
    segments, legend = [], []
    x = float(bar_x)
    for i, (lang, size) in enumerate(top):
        pct = size / total
        color = LANG_COLORS.get(lang, FALLBACK_COLOR)
        w = pct * bar_w
        segments.append(f'<rect x="{x:.1f}" y="55" width="{w:.1f}" height="10" fill="{color}"/>')
        col, row = divmod(i, 4)
        lx = 25 + col * 165
        ly = 95 + row * 24
        legend.append(
            f'<g class="row" style="animation-delay:{300 + i * 100}ms">'
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>'
            f'<text x="{lx + 18}" y="{ly}" fill="{TEXT}" font-size="12">{lang} '
            f'<tspan fill="{VALUE}" font-weight="600">{pct * 100:.1f}%</tspan></text>'
            f"</g>"
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="350" height="195" viewBox="0 0 350 195" {FONT}>
<style>
.row {{ opacity: 0; animation: fadein 0.5s ease forwards; }}
@keyframes fadein {{ to {{ opacity: 1; }} }}
</style>
<rect width="350" height="195" rx="10" fill="{BG}"/>
<text x="25" y="40" fill="{TITLE}" font-size="18" font-weight="600">常用语言</text>
<clipPath id="bar"><rect x="{bar_x}" y="55" width="{bar_w}" height="10" rx="5"/></clipPath>
<g clip-path="url(#bar)">{"".join(segments)}</g>
{"".join(legend)}
</svg>
"""


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "dist"
    os.makedirs(outdir, exist_ok=True)
    user, own, langs = fetch()
    with open(os.path.join(outdir, "stats-card.svg"), "w", encoding="utf-8") as f:
        f.write(stats_card(user, own))
    with open(os.path.join(outdir, "top-langs.svg"), "w", encoding="utf-8") as f:
        f.write(langs_card(langs))
    print(f"已生成 {outdir}/stats-card.svg 和 {outdir}/top-langs.svg")


if __name__ == "__main__":
    main()
