"""验证两种版式的数据一致性与 CLI 更新边界。"""

from datetime import date, timedelta
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from scripts.update_activity import render_svg


ROOT = Path(__file__).resolve().parents[1]
NS = {"svg": "http://www.w3.org/2000/svg"}
DAYS = [(date(2026, 9, 8) + timedelta(days=i)).isoformat() for i in range(31)]
OUTPUTS = [f"activity-{theme}{size}{motion}.svg" for theme in ("light", "dark") for size in ("", "-mobile") for motion in ("", "-static")]


class ActivityTests(unittest.TestCase):
    def test_mobile_keeps_all_days_and_extreme_values(self):
        for dark in (False, True):
            for counts in ([0] * 31, [0] * 15 + [10000] + [0] * 15):
                with self.subTest(dark=dark, peak=max(counts)):
                    desktop = ET.fromstring(render_svg("tester", DAYS, counts, dark))
                    mobile = ET.fromstring(render_svg("tester", DAYS, counts, dark, compact=True))
                    self.assertEqual(mobile.get("viewBox"), "0 0 400 260")
                    expected = [f"{day}: {count} contributions" for day, count in zip(DAYS, counts)]
                    for svg in (desktop, mobile):
                        points = svg.findall(".//svg:rect[@class='day-bar']", NS)
                        self.assertEqual([p.find("svg:title", NS).text for p in points], expected)
                        width, height = map(float, svg.get("viewBox").split()[2:])
                        for point in points:
                            self.assertTrue(0 <= float(point.get("x")) <= width)
                            self.assertTrue(0 <= float(point.get("y")) <= height)
                            self.assertLessEqual(float(point.get('y')) + float(point.get('height')), height)
                        self.assertIn(f"{sum(counts)} contributions", svg.find("svg:desc", NS).text)
                    labels = mobile.findall(".//svg:text", NS)
                    self.assertEqual(len([t for t in labels if t.text and "/" in t.text]), 4)
                    group = mobile.find("svg:g", NS)
                    self.assertGreaterEqual(int(group.get("font-size")), 14)
                    active = mobile.find(".//svg:text[@id='active-days']", NS)
                    self.assertEqual(active.text, "0" if max(counts) == 0 else "1")

    def test_static_card_preserves_data_and_has_no_animation(self):
        for compact in (False, True):
            for dark in (False, True):
                animated = ET.fromstring(render_svg("tester", DAYS, list(range(31)), dark, compact))
                static = ET.fromstring(render_svg("tester", DAYS, list(range(31)), dark, compact, animated=False))
                self.assertIsNotNone(animated.find("svg:style", NS))
                self.assertIsNone(static.find("svg:style", NS))
                self.assertEqual([p.find("svg:title", NS).text for p in animated.findall(".//svg:rect[@class='day-bar']", NS)], [p.find("svg:title", NS).text for p in static.findall(".//svg:rect[@class='day-bar']", NS)])
                self.assertEqual(static.find(".//svg:text[@id='active-days']", NS).text, "30")

    def run_cli(self, directory, missing=False):
        html = []
        for i, day in enumerate(DAYS[:-1] if missing else DAYS):
            html.append(f'<td id="day-{i}" data-date="{day}"></td><tool-tip for="day-{i}">{i} contributions</tool-tip>')
        source = directory / "calendar.html"
        source.write_text("\n".join(html), encoding="utf-8")
        return subprocess.run([sys.executable, str(ROOT / "scripts/update_activity.py"), "--html", str(source), "--end", DAYS[-1], "--output", str(directory / "assets")], capture_output=True)

    def test_cli_updates_all_eight_outputs_from_one_calendar(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            result = self.run_cli(directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(sorted(p.name for p in (directory / "assets").iterdir()), sorted(OUTPUTS))
            for name in OUTPUTS:
                svg = ET.parse(directory / "assets" / name).getroot()
                self.assertIn("465 contributions", svg.find("svg:desc", NS).text)
                self.assertEqual(len(svg.findall(".//svg:rect[@class='day-bar']", NS)), 31)

    def test_missing_day_preserves_all_existing_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            (directory / "assets").mkdir()
            for name in OUTPUTS:
                (directory / "assets" / name).write_bytes(b"previous-valid-image")
            result = self.run_cli(directory, missing=True)
            self.assertNotEqual(result.returncode, 0)
            for name in OUTPUTS:
                self.assertEqual((directory / "assets" / name).read_bytes(), b"previous-valid-image")


if __name__ == "__main__":
    unittest.main()
