"""从 GitHub 公开贡献日历生成近 31 天的浅色与深色贡献节奏卡。"""

import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.request import Request, urlopen


class ContributionCalendar(HTMLParser):
    """通过日历单元格与 tooltip 的对应关系读取真实每日贡献次数。"""

    def __init__(self):
        super().__init__()
        self.dates = {}
        self.counts = {}
        self.tooltip = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "data-date" in attrs and "id" in attrs:
            self.dates[attrs["id"]] = attrs["data-date"]
        elif tag == "tool-tip":
            self.tooltip = attrs.get("for")
            self.text = []

    def handle_data(self, data):
        if self.tooltip:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag != "tool-tip" or not self.tooltip:
            return
        day = self.dates.get(self.tooltip)
        match = re.search(r"(No|[\d,]+)\s+contributions?\b", "".join(self.text))
        if day and match:
            self.counts[day] = 0 if match[1] == "No" else int(match[1].replace(",", ""))
        self.tooltip = None


def render_svg(username, days, counts, dark, compact=False, animated=True):
    background, foreground, muted, accent = (
        ("#0d1117", "#e6edf3", "#30363d", "#2dd4bf")
        if dark else ("#ffffff", "#24292f", "#d8dee4", "#0d9488")
    )
    width = 400 if compact else 800
    margin = 24 if compact else 36
    bottom, top = 202, 116
    slot = (width - 2 * margin) / 31
    active = sum(value > 0 for value in counts)
    description = f"{username}: {days[0]} to {days[-1]}, {sum(counts)} contributions. {active} active days."
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="260" viewBox="0 0 {width} 260" role="img" aria-labelledby="title description">',
        '<title id="title">GitHub 贡献节奏 · 近 31 天</title>',
        f'<desc id="description">{escape(description)}</desc>',
        f'<rect width="{width}" height="260" rx="12" fill="{background}"/>',
    ]
    if animated:
        svg.append('<style>@keyframes light-up { 0% { opacity: .18; } 6%, 100% { opacity: 1; } } .day-bar { animation: light-up 10s ease-out infinite both; } @media (prefers-reduced-motion: reduce) { .day-bar { animation: none; } }</style>')
    svg.extend([
        f'<g font-family="Arial, Microsoft YaHei, sans-serif" font-size="14" fill="{foreground}">',
        f'<text x="{margin}" y="29" font-size="18" font-weight="600">GitHub 贡献节奏 · 近 31 天</text>',
        f'<text id="total-contributions" x="{margin}" y="73" font-size="32" font-weight="600">{sum(counts)}</text>',
        f'<text x="{margin}" y="96">总贡献</text>',
        f'<text id="active-days" x="{width // 2}" y="73" font-size="32" font-weight="600">{active}</text>',
        f'<text x="{width // 2}" y="96">活跃天数</text>',
    ])
    for i in range(0, 31, 10 if compact else 5):
        x = margin + (i + .5) * slot
        svg.append(f'<text x="{x:.2f}" y="225" text-anchor="middle">{days[i][5:].replace("-", "/")}</text>')
    svg.append(f'<text x="{margin}" y="250">更新 {days[-1]} UTC</text>')
    svg.append('</g>')
    peak = max(1, max(counts))
    for i, (day, count) in enumerate(zip(days, counts)):
        height = max(2, count / peak * (bottom - top))
        x = margin + i * slot + slot * .15
        delay = f' style="animation-delay: {i * .035:.3f}s"' if animated else ''
        fill = accent if count else muted
        svg.append(f'<rect class="day-bar" x="{x:.2f}" y="{bottom - height:.2f}" width="{slot * .7:.2f}" height="{height:.2f}" rx="2" fill="{fill}"{delay}><title>{day}: {count} contributions</title></rect>')
    svg.append('</svg>')
    return "\n".join(svg) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="MashedPotato817")
    parser.add_argument("--end", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--html", type=Path, help="使用已下载的贡献日历，支持离线重现")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "assets")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]+", args.username):
        parser.error("GitHub 用户名格式无效")
    start = args.end - timedelta(days=30)
    if args.html:
        content = args.html.read_text(encoding="utf-8")
    else:
        url = f"https://github.com/users/{args.username}/contributions?from={start}&to={args.end}"
        request = Request(url, headers={"User-Agent": "GitHub-Profile-Activity", "Accept": "text/html"})
        with urlopen(request, timeout=30) as response:
            content = response.read().decode("utf-8")
    calendar = ContributionCalendar()
    calendar.feed(content)
    days = [(start + timedelta(days=i)).isoformat() for i in range(31)]
    missing = [day for day in days if day not in calendar.counts]
    if missing:
        raise ValueError(f"贡献日历缺少 {len(missing)} 天的数据，保留已有图表")
    counts = [calendar.counts[day] for day in days]
    images = {
        f"{theme}{'-mobile' if compact else ''}{'-static' if not animated else ''}": render_svg(args.username, days, counts, theme == "dark", compact, animated)
        for theme in ("light", "dark") for compact in (False, True) for animated in (True, False)
    }
    args.output.mkdir(parents=True, exist_ok=True)
    for theme, image in images.items():
        (args.output / f"activity-{theme}.svg").write_text(image, encoding="utf-8")
    print(f"Generated activity graphs: {days[0]} to {days[-1]}, {sum(counts)} contributions")


if __name__ == "__main__":
    main()
