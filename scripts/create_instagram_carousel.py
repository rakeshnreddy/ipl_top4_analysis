#!/usr/bin/env python3
"""Create IPL Top 4 Instagram carousel slides from the canonical payload."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "frontend/ipl-analyzer-frontend/public/data/ipl-2026.json"
OUTPUT_ROOT = ROOT / "frontend/ipl-analyzer-frontend/public/social/instagram-carousel"
WIDTH = 1080
HEIGHT = 1920
SAFE_X = 70
SAFE_BOTTOM = 1800
DISCLAIMER = "Probabilities exclude NRR calculation. Final qualification outcomes may still change due to NRR."

TEAM_STYLES = {
    "Mumbai": {"bg": "#004B8D", "text": "#FFFFFF"},
    "Chennai": {"bg": "#F9CD05", "text": "#000000"},
    "Bangalore": {"bg": "#EC1C24", "text": "#FFFFFF"},
    "Kolkata": {"bg": "#3A225D", "text": "#FFFFFF"},
    "Hyderabad": {"bg": "#FEDC32", "text": "#000000"},
    "Delhi": {"bg": "#2561AE", "text": "#FFFFFF"},
    "Punjab": {"bg": "#ED1D24", "text": "#FFFFFF"},
    "Rajasthan": {"bg": "#254AA5", "text": "#FFFFFF"},
    "Gujarat": {"bg": "#0A1C34", "text": "#FFFFFF"},
    "Lucknow": {"bg": "#0057E2", "text": "#FFFFFF"},
}


FONT_CANDIDATES = {
    "regular": [
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ],
    "bold": [
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ],
    "black": [
        Path("/System/Library/Fonts/Supplemental/Arial Black.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ],
}


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES.get(weight, FONT_CANDIDATES["regular"]):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(a[index] * (1 - t) + b[index] * t) for index in range(3))


def rgba(hex_color: str, alpha: int) -> tuple[int, int, int, int]:
    return (*hex_to_rgb(hex_color), alpha)


def pct(value: float) -> str:
    rounded = round(value, 1)
    if math.isclose(rounded, round(rounded)):
        return f"{int(round(rounded))}%"
    return f"{rounded:.1f}%"


def nrr(value: float) -> str:
    return f"{value:+.3f}"


def status_for(chance: float) -> tuple[str, str]:
    if chance >= 90:
        return "Almost Safe", "#38D996"
    if chance >= 75:
        return "Strong Position", "#57B8FF"
    if chance >= 55:
        return "Good Chance", "#A7F3D0"
    if chance >= 40:
        return "50-50 Zone", "#FBBF24"
    if chance >= 20:
        return "Needs Help", "#FB923C"
    if chance >= 1:
        return "Must Win", "#FB7185"
    return "Almost Out", "#94A3B8"


def generated_date(payload: dict[str, Any]) -> str:
    value = payload["metadata"]["generated_at"]
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.strftime("%b %-d, %Y")


def generated_date_slug(payload: dict[str, Any]) -> str:
    value = payload["metadata"]["generated_at"]
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d")


def draw_gradient(draw: ImageDraw.ImageDraw, start: str, end: str) -> None:
    start_rgb = hex_to_rgb(start)
    end_rgb = hex_to_rgb(end)
    for y in range(HEIGHT):
        t = y / (HEIGHT - 1)
        color = mix(start_rgb, end_rgb, t)
        draw.line([(0, y), (WIDTH, y)], fill=color)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: Any, outline: Any = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text_width(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont) -> int:
    return round(draw.textbbox((0, 0), text, font=text_font)[2])


def fit_text(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont, max_width: int) -> str:
    if text_width(draw, text, text_font) <= max_width:
        return text
    output = text
    while output and text_width(draw, f"{output}...", text_font) > max_width:
        output = output[:-1]
    return f"{output.rstrip()}..."


def wrapped_lines(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont, max_width: int, max_lines: int = 3) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if text_width(draw, candidate, text_font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return lines


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int, fill: Any, weight: str = "regular") -> None:
    draw.text(xy, text, font=font(size, weight), fill=fill)


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    size: int,
    fill: Any,
    weight: str = "regular",
    max_width: int = 900,
    line_gap: int = 8,
    max_lines: int = 3,
) -> int:
    text_font = font(size, weight)
    y = xy[1]
    for line in wrapped_lines(draw, text, text_font, max_width, max_lines):
        draw.text((xy[0], y), line, font=text_font, fill=fill)
        y += size + line_gap
    return y


def draw_chip(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, fill: str, text_fill: str = "#08111F") -> None:
    chip_font = font(30, "bold")
    padding_x = 22
    width = text_width(draw, label, chip_font) + padding_x * 2
    rounded(draw, (x, y, x + width, y + 50), 25, rgba(fill, 235))
    draw.text((x + padding_x, y + 9), label, font=chip_font, fill=text_fill)


def draw_footer(draw: ImageDraw.ImageDraw) -> None:
    footer_font = font(18, "regular")
    lines = wrapped_lines(draw, DISCLAIMER, footer_font, 920, 2)
    y = SAFE_BOTTOM + 18
    for line in lines:
        draw.text((SAFE_X, y), line, font=footer_font, fill=(190, 203, 222))
        y += 24


def slide_base(accent: str = "#2563EB") -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#07111F")
    draw = ImageDraw.Draw(image, "RGBA")
    draw_gradient(draw, "#07111F", "#16111C")
    accent_rgb = hex_to_rgb(accent)
    draw.ellipse((-300, -260, 560, 600), fill=(*accent_rgb, 72))
    draw.ellipse((570, 1110, 1340, 1960), fill=(*accent_rgb, 48))
    rounded(draw, (48, 48, 1032, 1872), 34, (255, 255, 255, 22), (255, 255, 255, 42), 2)
    return image, draw


def probability_order(payload: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    probs = payload["analysis"]["overallProbabilities"]
    standings = payload["standings"]
    ordered = sorted(standings, key=lambda team: probs[team["teamKey"]]["top4"], reverse=True)
    return ordered[:limit] if limit else ordered


def path_for(payload: dict[str, Any], team_key: str) -> dict[str, Any]:
    return payload["analysis"]["qualificationPath"]["4"][team_key]


def top2_path_for(payload: dict[str, Any], team_key: str) -> dict[str, Any]:
    return payload["analysis"]["qualificationPath"]["2"][team_key]


def key_result(payload: dict[str, Any], team: dict[str, Any]) -> tuple[str, str]:
    path = path_for(payload, team["teamKey"])
    impacts = path.get("nextFixtureImpacts") or path.get("fixtureImpacts") or []
    if impacts:
        impact = impacts[0]
        return "TODAY'S KEY RESULT", f"{impact['preferredLabel']} ({impact['label']})"

    for fixture in payload["fixtures"]:
        if team["teamKey"] in (fixture["teamA"], fixture["teamB"]):
            other = fixture["teamB"] if fixture["teamA"] == team["teamKey"] else fixture["teamA"]
            other_short = next((row["shortName"] for row in payload["standings"] if row["teamKey"] == other), other)
            return "NEXT KEY MATCH", f"{team['shortName']} vs {other_short}"
    return "NEXT KEY MATCH", "No listed fixture"


def need_lines(payload: dict[str, Any], team: dict[str, Any]) -> list[str]:
    path = path_for(payload, team["teamKey"])
    top2_path = top2_path_for(payload, team["teamKey"])
    lines: list[str] = []

    possible = path.get("possible")
    likely = path.get("likely")
    guaranteed = path.get("guaranteed")
    top2_likely = top2_path.get("likely")

    if isinstance(possible, int):
        lines.append(f"{possible}+ wins keeps Top 4 possible.")
    if isinstance(likely, int):
        lines.append(f"{likely}+ wins gets them past 50%.")
    else:
        lines.append("No 50% path by own wins alone.")
    if isinstance(guaranteed, int):
        lines.append(f"{guaranteed}+ wins locks Top 4 in the model.")
    else:
        lines.append("No Top 4 lock without other results.")
    if isinstance(top2_likely, int):
        lines.append(f"{top2_likely}+ wins needed for a 50% Top 2 path.")

    return lines[:4]


def takeaway(payload: dict[str, Any], team: dict[str, Any]) -> str:
    chance = payload["analysis"]["overallProbabilities"][team["teamKey"]]["top4"]
    path = path_for(payload, team["teamKey"])
    likely = path.get("likely")
    guaranteed = path.get("guaranteed")
    if chance >= 90:
        return f"{team['shortName']} can focus on locking a top-two finish."
    if chance >= 75:
        return f"{team['shortName']} are in control if they avoid a late slide."
    if chance >= 55:
        return f"{team['shortName']} have room, but two wins still matter."
    if chance >= 40:
        return f"{team['shortName']} need a clean run and rival slips."
    if isinstance(likely, int):
        return f"{team['shortName']} need at least {likely} wins to become serious."
    if isinstance(guaranteed, int):
        return f"{team['shortName']} still have a route, but it is narrow."
    return f"{team['shortName']} need wins and outside help immediately."


def draw_overview(payload: dict[str, Any], teams: list[dict[str, Any]], output_dir: Path) -> Path:
    image, draw = slide_base("#F59E0B")
    draw_text(draw, (78, 94), "IPL ROAD TO TOP 4", 68, "#FFFFFF", "black")
    draw_text(draw, (82, 178), "Daily qualification probability update", 34, "#CBD5E1", "bold")
    draw_text(draw, (82, 240), generated_date(payload), 30, "#FDE68A", "bold")

    table_x = 70
    table_y = 340
    table_w = 940
    header_h = 66
    row_h = 106
    table_h = header_h + row_h * len(teams) + 28
    rounded(draw, (table_x, table_y, table_x + table_w, table_y + table_h), 32, (255, 255, 255, 28), (255, 255, 255, 48), 2)

    headers = [("Rank", 92), ("Team", 245), ("Top 4 %", 450), ("Top 2 %", 610), ("Status", 760)]
    for label, x in headers:
        draw_text(draw, (table_x + x, table_y + 26), label.upper(), 22, "#9FB2CC", "bold")

    probs = payload["analysis"]["overallProbabilities"]
    y = table_y + header_h
    for index, team in enumerate(teams, start=1):
        top4 = probs[team["teamKey"]]["top4"]
        top2 = probs[team["teamKey"]]["top2"]
        status, status_color = status_for(top4)
        accent = TEAM_STYLES[team["teamKey"]]["bg"]
        row_fill = (*hex_to_rgb(accent), 45) if index <= 4 else (255, 255, 255, 18)
        rounded(draw, (table_x + 20, y + 9, table_x + table_w - 20, y + row_h - 9), 22, row_fill, (255, 255, 255, 35), 1)
        draw.ellipse((table_x + 38, y + 31, table_x + 94, y + 87), fill=(8, 17, 31, 245))
        draw_text(draw, (table_x + 57, y + 45), str(index), 28, "#FFFFFF", "bold")
        draw.rectangle((table_x + 112, y + 24, table_x + 124, y + 88), fill=rgba(accent, 255))
        draw_text(draw, (table_x + 144, y + 24), team["shortName"], 34, "#FFFFFF", "black")
        draw_text(draw, (table_x + 144, y + 62), fit_text(draw, team["fullName"], font(21, "regular"), 290), 21, "#BFD0E6")
        draw_text(draw, (table_x + 450, y + 42), pct(top4), 34, "#FFFFFF", "black")
        draw_text(draw, (table_x + 620, y + 43), pct(top2), 32, "#E5E7EB", "bold")
        rounded(draw, (table_x + 760, y + 34, table_x + 910, y + 76), 21, rgba(status_color, 225))
        status_font = font(18, "bold")
        draw.text((table_x + 835 - text_width(draw, status, status_font) // 2, y + 46), status, font=status_font, fill="#08111F")
        y += row_h

    note_y = table_y + table_h + 46
    rounded(draw, (70, note_y, 1010, note_y + 154), 28, (255, 255, 255, 22), (255, 255, 255, 40), 1)
    draw_text(draw, (100, note_y + 28), "READ THIS TABLE", 25, "#FDE68A", "black")
    draw_wrapped_text(
        draw,
        (100, note_y + 66),
        "Top 4 and Top 2 percentages are based on all remaining result combinations, excluding NRR movement.",
        28,
        "#E2E8F0",
        "bold",
        850,
        8,
        2,
    )
    draw_footer(draw)
    output = output_dir / "slide-01-overview.png"
    image.save(output)
    return output


def draw_team_slide(payload: dict[str, Any], team: dict[str, Any], slide_number: int, output_dir: Path) -> Path:
    style = TEAM_STYLES[team["teamKey"]]
    accent = style["bg"]
    image, draw = slide_base(accent)
    probs = payload["analysis"]["overallProbabilities"][team["teamKey"]]
    top4 = probs["top4"]
    top2 = probs["top2"]
    status, status_color = status_for(top4)
    path = path_for(payload, team["teamKey"])

    draw_text(draw, (78, 86), team["shortName"], 108, "#FFFFFF", "black")
    draw_text(draw, (82, 202), team["fullName"], 34, "#CBD5E1", "bold")
    draw_chip(draw, 722, 112, status, status_color)

    rounded(draw, (70, 290, 1010, 632), 36, (255, 255, 255, 32), (255, 255, 255, 50), 2)
    draw_text(draw, (110, 328), "TOP 4 CHANCE", 31, "#FDE68A", "bold")
    draw_text(draw, (106, 366), pct(top4), 146, "#FFFFFF", "black")
    rounded(draw, (702, 366, 950, 542), 30, rgba(accent, 155), (255, 255, 255, 45), 2)
    draw_text(draw, (738, 397), "TOP 2", 31, "#E2E8F0", "bold")
    draw_text(draw, (738, 442), pct(top2), 62, "#FFFFFF", "black")

    stat_y = 680
    stat_boxes = [
        ("POSITION", f"#{team['rank']}"),
        ("POINTS", f"{team['points']}"),
        ("NRR", nrr(team["nrr"])),
    ]
    for idx, (label, value) in enumerate(stat_boxes):
        x = 70 + idx * 315
        rounded(draw, (x, stat_y, x + 285, stat_y + 124), 24, (255, 255, 255, 25), (255, 255, 255, 40), 1)
        draw_text(draw, (x + 24, stat_y + 24), label, 24, "#9FB2CC", "bold")
        draw_text(draw, (x + 24, stat_y + 58), value, 42, "#FFFFFF", "black")

    need_y = 842
    rounded(draw, (70, need_y, 1010, need_y + 320), 30, (255, 255, 255, 25), (255, 255, 255, 40), 1)
    draw_text(draw, (100, need_y + 30), "WHAT THEY NEED", 31, "#FDE68A", "black")
    y = need_y + 86
    for line in need_lines(payload, team):
        draw.ellipse((104, y + 13, 118, y + 27), fill=rgba(accent, 255))
        y = draw_wrapped_text(draw, (134, y), line, 29, "#FFFFFF", "bold", 810, 6, 2) + 4

    key_label, key_text = key_result(payload, team)
    key_y = 1204
    rounded(draw, (70, key_y, 1010, key_y + 154), 30, rgba(accent, 78), (255, 255, 255, 45), 2)
    draw_text(draw, (100, key_y + 28), key_label, 25, "#C7D2FE", "bold")
    draw_wrapped_text(draw, (100, key_y + 64), key_text, 36, "#FFFFFF", "black", 835, 8, 2)

    bucket_y = 1400
    draw_text(draw, (78, bucket_y), "WIN BUCKETS", 28, "#9FB2CC", "black")
    buckets = path.get("ownWinBuckets", [])
    columns = 4
    cell_gap = 14
    cell_w = math.floor((940 - cell_gap * (columns - 1)) / columns)
    cell_h = 112
    for idx, bucket in enumerate(buckets):
        x = 70 + (idx % columns) * (cell_w + cell_gap)
        y = bucket_y + 50 + (idx // columns) * (cell_h + cell_gap)
        rounded(draw, (x, y, x + cell_w, y + cell_h), 20, (255, 255, 255, 27), (255, 255, 255, 40), 1)
        label = f"{bucket['wins']}W"
        value = pct(bucket["probability"])
        draw.text((x + 18, y + 20), label, font=font(24, "bold"), fill="#BFD0E6")
        draw.text((x + 18, y + 56), value, font=font(32, "black"), fill="#FFFFFF")

    takeaway_text = takeaway(payload, team)
    draw_wrapped_text(draw, (76, 1716), takeaway_text, 30, "#FFFFFF", "bold", 930, 8, 2)
    draw_footer(draw)

    safe_name = team["shortName"].lower()
    output = output_dir / f"slide-{slide_number:02d}-{safe_name}.png"
    image.save(output)
    return output


def draw_contact_sheet(paths: list[Path], output_dir: Path) -> Path:
    sheet, draw = slide_base("#F59E0B")
    draw_text(draw, (78, 94), "REELS EXPORT SET", 64, "#FFFFFF", "black")
    draw_text(draw, (82, 170), "One overview plus every team slide", 32, "#CBD5E1", "bold")

    thumb_w = 220
    thumb_h = 391
    columns = 4
    gap_x = 20
    gap_y = 28
    grid_x = 70
    grid_y = 270
    for index, path in enumerate(paths):
        image = Image.open(path).resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        x = grid_x + (index % columns) * (thumb_w + gap_x)
        y = grid_y + (index // columns) * (thumb_h + gap_y)
        rounded(draw, (x - 3, y - 3, x + thumb_w + 3, y + thumb_h + 3), 14, (255, 255, 255, 26), (255, 255, 255, 42), 1)
        sheet.paste(image, (x, y))
        draw_text(draw, (x + 10, y + thumb_h - 38), f"{index + 1:02d}", 22, "#FFFFFF", "black")

    draw_footer(draw)
    output = output_dir / "contact-sheet.png"
    sheet.save(output)
    return output


def main() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    teams = probability_order(payload)
    output_dir = OUTPUT_ROOT / generated_date_slug(payload)
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.glob("*.png"):
        old_file.unlink()

    outputs = [draw_overview(payload, teams, output_dir)]
    for index, team in enumerate(teams, start=2):
        outputs.append(draw_team_slide(payload, team, index, output_dir))
    outputs.append(draw_contact_sheet(outputs, output_dir))

    print("\n".join(str(path) for path in outputs))


if __name__ == "__main__":
    main()
