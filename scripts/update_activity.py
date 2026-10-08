"""从 GitHub 公开贡献日历生成近 31 天的浅色与深色活动折线图。"""

import argparse
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import math
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


def render_svg(username, days, counts, dark):
    background, foreground, grid, green = (
        ("#0d1117", "#c9d1d9", "#30363d", "#39d353")
        if dark else ("#ffffff", "#57606a", "#d8dee4", "#216e39")
    )
    left, right, top, bottom = 55, 775, 55, 205
    step = max(1, math.ceil(max(counts) / 4))
    ceiling = step * 4
    points = [
        (left + i * (right - left) / 30, bottom - value * (bottom - top) / ceiling)
        for i, value in enumerate(counts)
    ]
    description = f"{username}: {days[0]} to {days[-1]}, {sum(counts)} contributions."
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="260" viewBox="0 0 800 260" role="img" aria-labelledby="title description">',
        '<title id="title">GitHub Activity · Last 31 Days</title>',
        f'<desc id="description">{escape(description)}</desc>',
        f'<rect width="800" height="260" rx="8" fill="{background}"/>',
        f'<g font-family="Arial, sans-serif" font-size="11" fill="{foreground}">',
        '<text x="55" y="25" font-size="15" font-weight="600">GitHub Activity · Last 31 Days</text>',
        f'<text x="775" y="25" text-anchor="end">{sum(counts)} contributions</text>',
    ]
    for i in range(5):
        y = bottom - i * (bottom - top) / 4
        svg.append(f'<path d="M {left} {y} H {right}" stroke="{grid}" stroke-dasharray="3 4"/>')
        svg.append(f'<text x="43" y="{y + 4}" text-anchor="end">{step * i}</text>')
    for i in range(0, 31, 5):
        svg.append(f'<text x="{points[i][0]:.1f}" y="226" text-anchor="middle">{days[i][5:].replace("-", "/")}</text>')
    svg.append(f'<text x="55" y="247">Daily contributions · Updated {days[-1]} UTC</text>')
    svg.append('</g>')
    coordinates = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    svg.append(f'<polygon points="{left},{bottom} {coordinates} {right},{bottom}" fill="{green}" opacity="0.12"/>')
    svg.append(f'<polyline points="{coordinates}" fill="none" stroke="{green}" stroke-width="2" stroke-linejoin="round"/>')
    for day, count, (x, y) in zip(days, counts, points):
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.5" fill="{green}"><title>{day}: {count} contributions</title></circle>')
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
    images = {theme: render_svg(args.username, days, counts, theme == "dark") for theme in ("light", "dark")}
    args.output.mkdir(parents=True, exist_ok=True)
    for theme, image in images.items():
        (args.output / f"activity-{theme}.svg").write_text(image, encoding="utf-8")
    print(f"Generated activity graphs: {days[0]} to {days[-1]}, {sum(counts)} contributions")


if __name__ == "__main__":
    main()
