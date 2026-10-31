"""Render the approved profile using real contribution SVGs (standard library only)."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
TOOLS = ("Java", "Python", "Git", "Codex", "Obsidian")
INTERESTS = (
    ("sparkles", "AI & Automation", "Smarter everyday workflows."),
    ("shield-check", "Systems & Security", "Understanding what runs beneath."),
    ("wrench", "Everyday Tools", "Small ideas. Useful changes."),
)
PALETTES = {
    "light": dict(paper="#ffffff", ink="#171d1b", muted="#64716c", line="#e0e7e3", accent="#087a69"),
    "dark": dict(paper="#101413", ink="#f3f6f5", muted="#a1b0aa", line="#28322e", accent="#66e0cd"),
}


def element(name, **attributes):
    return ET.Element(f"{{{NS}}}{name}", {key.replace("_", "-"): str(value) for key, value in attributes.items()})


def icon(name, x, y, size, color="#111111", grayscale=False):
    svg = ET.parse(ROOT / "assets" / "icons" / f"{name}.svg").getroot()
    for key, value in dict(x=x, y=y, width=size, height=size, color=color).items():
        svg.set(key, str(value))
    svg.attrib.pop("style", None)
    svg.attrib.pop("class", None)
    if grayscale:
        svg.set("filter", "url(#monochrome)")
    return ET.tostring(svg, encoding="unicode")


def snake(theme, x, y, width):
    svg = ET.parse(ROOT / "generated" / f"snake-{theme}.svg").getroot()
    cells = [node for node in svg.iter() if "c" in node.get("class", "").split()]
    if not 350 <= len(cells) <= 378:
        raise ValueError(f"Unexpected contribution calendar size: {len(cells)}")
    if not any("s" in node.get("class", "").split() for node in svg.iter()):
        raise ValueError("Snake animation is missing")
    # Preserve the complete generated path, including the space above the grid.
    # The generated consumption bar is omitted to match the approved design.
    vx, vy, vw, _ = map(float, svg.get("viewBox").split())
    view_height = 160
    svg.set("viewBox", f"{vx:g} {vy:g} {vw:g} {view_height}")
    height = width / vw * view_height
    for key, value in dict(id="contribution-snake", x=x, y=y, width=width, height=height).items():
        svg.set(key, str(value))
    for node in list(svg):
        if "u" in node.get("class", "").split():
            svg.remove(node)
    description = element("desc")
    description.text = "Animated snake generated from Mackeabit's real GitHub contribution calendar."
    svg.insert(0, description)
    return ET.tostring(svg, encoding="unicode"), height


def render(theme, mobile):
    p = PALETTES[theme]
    width, pad = (360, 24) if mobile else (828, 36)
    inner = width - pad * 2
    hero_height = 284 if mobile else 230
    header_y = hero_height + 40
    interest_line = header_y + (226 if mobile else 119)
    tools_header = interest_line + 35
    tools_top = tools_header + 25
    tools_line = tools_top + (186 if mobile else 110)
    trail_header = tools_line + 35
    subtitle_y = trail_header + 39
    snake_y = subtitle_y + 4
    snake_markup, snake_height = snake(theme, pad, snake_y, inner)
    footer_y = snake_y + snake_height + 20
    height = footer_y + (48 if mobile else 30)
    logo = base64.b64encode((ROOT / "assets" / "logo.png").read_bytes()).decode("ascii")
    output = [
        f'<svg xmlns="{NS}" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height:.2f}" viewBox="0 0 {width} {height:.2f}" role="img" aria-labelledby="profile-title profile-description">',
        '<title id="profile-title">Mackeabit — curious by default</title>',
        '<desc id="profile-description">Learning by doing. Making everyday things simpler. Exploring AI and automation, systems and security, and everyday tools. Java, Python, Git, Codex and Obsidian. A teal snake follows real GitHub contributions.</desc>',
        '<defs>',
        '<radialGradient id="hero-gradient" cx="96%" cy="4%" r="100%"><stop offset="0" stop-color="#163d35"/><stop offset=".31" stop-color="#101817"/><stop offset=".68" stop-color="#0c100f"/></radialGradient>',
        f'<clipPath id="profile-clip"><rect x=".5" y=".5" width="{width-1}" height="{height-1:.2f}" rx="12"/></clipPath>',
        '<filter id="monochrome" color-interpolation-filters="sRGB"><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncR type="linear" slope=".48"/><feFuncG type="linear" slope=".48"/><feFuncB type="linear" slope=".48"/></feComponentTransfer></filter>',
        '</defs>',
        '<style>',
        'text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}',
        '.section-label,.profile-kicker,.profile-footer{font-family:ui-monospace,Consolas,"Liberation Mono",monospace}',
        f'.section-label{{font-size:11px;letter-spacing:1.6px;fill:{p["muted"]}}}',
        f'.profile-note{{font-size:11px;fill:{p["muted"]}}}',
        '@media(prefers-reduced-motion:reduce){#contribution-snake *{animation:none!important}}',
        '</style>',
        '<g clip-path="url(#profile-clip)">',
        f'<rect width="{width}" height="{height:.2f}" fill="{p["paper"]}"/>',
        f'<rect width="{width}" height="{hero_height}" fill="url(#hero-gradient)"/>',
        f'<rect width="{width}" height="3" fill="#25c6b0"/>',
    ]

    def text(x, y, value, **attrs):
        attributes = " ".join(f'{key.rstrip("_").replace("_","-")}="{escape(str(val), quote=True)}"' for key, val in attrs.items())
        output.append(f'<text x="{x}" y="{y}" {attributes}>{escape(value)}</text>')

    def line(y):
        output.append(f'<path d="M{pad} {y}H{width-pad}" stroke="{p["line"]}"/>')

    if mobile:
        lx, ly, ls, kicker_y, name_y, intro_y = pad, 28, 64, 128, 179, 218
    else:
        lx, ly, ls, kicker_y, name_y, intro_y = width-pad-116, 60, 116, 54, 120, 161
    output.append(f'<clipPath id="logo-clip"><rect x="{lx}" y="{ly}" width="{ls}" height="{ls}" rx="{9 if mobile else 12}"/></clipPath>')
    output.append(f'<rect x="{lx}" y="{ly}" width="{ls}" height="{ls}" rx="{9 if mobile else 12}" fill="#ffffff"/>')
    output.append(f'<image x="{lx}" y="{ly}" width="{ls}" height="{ls}" clip-path="url(#logo-clip)" xlink:href="data:image/png;base64,{logo}"/>')
    output.append(f'<rect x="{pad}" y="{kicker_y-6}" width="5" height="5" fill="#25c6b0"/>')
    text(pad+14, kicker_y, "CURIOUS BY DEFAULT", class_="profile-kicker", fill="#91d7c8", font_size=10 if mobile else 11, letter_spacing=1.9)
    text(pad, name_y, "Mackeabit", fill="#f5f8f6", font_size=36 if mobile else 48, font_weight=650, letter_spacing=-1.3 if mobile else -1.9)
    text(pad, intro_y, "Learning by doing.", fill="#c2d1ca", font_size=15)
    text(pad, intro_y+26, "Making everyday things simpler.", fill="#c2d1ca", font_size=15)

    text(pad, header_y, "CURRENTLY EXPLORING", class_="section-label")
    for i, (symbol, heading, description) in enumerate(INTERESTS):
        x = pad if mobile else pad + i * (inner + 18) / 3
        y = header_y + 24 + i * 62 if mobile else header_y + 24
        output.append(icon(symbol, x, y, 18, p["accent"]))
        tx, ty = (x+32, y+14) if mobile else (x, y+37)
        text(tx, ty, heading, fill=p["ink"], font_size=14, font_weight=600)
        text(tx, ty+22, description, fill=p["muted"], font_size=12)
    line(interest_line)
    text(pad, tools_header, "TECH & TOOLS", class_="section-label")
    text(width-pad, tools_header, "Always learning.", class_="profile-note", text_anchor="end")
    for i, label in enumerate(TOOLS):
        columns = 3 if mobile else 5
        cell_width = inner / columns
        cx = pad + (i % columns + .5) * cell_width
        y = tools_top + (i // columns) * 90
        tile, size = (50, 28) if mobile else (56, 31)
        output.append(f'<rect x="{cx-tile/2:g}" y="{y}" width="{tile}" height="{tile}" rx="12" fill="#f4f7f5" stroke="#e2e9e5"/>')
        output.append(icon(label.lower(), cx-size/2, y+(tile-size)/2, size, grayscale=True))
        text(cx, y+tile+22, label, fill=p["muted"], font_size=12, text_anchor="middle")
    line(tools_line)
    text(pad, trail_header, "CONTRIBUTION TRAIL", class_="section-label")
    if not mobile:
        text(width-pad, trail_header, "GitHub activity", class_="profile-note", text_anchor="end")
    text(pad, subtitle_y, "One small step at a time.", fill=p["ink"], font_size=17, font_weight=500, letter_spacing=-.2)
    output.append(snake_markup)
    text(pad, footer_y, "Keep learning. Keep moving.", class_="profile-footer", fill=p["accent"], font_size=11)
    text(pad if mobile else width-pad, footer_y+22 if mobile else footer_y, "Updated daily", class_="profile-footer", fill=p["muted"], font_size=11, text_anchor="start" if mobile else "end")
    output.extend([
        '</g>',
        f'<rect x=".5" y=".5" width="{width-1}" height="{height-1:.2f}" rx="12" fill="none" stroke="{p["line"]}"/>',
        '</svg>',
    ])
    document = "\n".join(output)
    parsed = ET.fromstring(document)
    for node in parsed.iter():
        if node.tag.rsplit("}", 1)[-1] in {"script", "foreignObject"}:
            raise ValueError("Unsupported active SVG content")
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1] == "href" and not value.startswith(("data:", "#")):
                raise ValueError("External resources are not allowed in the profile SVG")
    return document + "\n"


def main():
    response = json.loads((ROOT / ".tmp" / "calendar.json").read_text(encoding="utf-8"))
    if response.get("errors"):
        raise ValueError(f"GitHub calendar request failed: {response['errors']}")
    user = response["data"]["user"]
    if user["login"].lower() != "mackeabit":
        raise ValueError("Refusing to generate a profile for an unexpected account")
    calendar = user["contributionsCollection"]["contributionCalendar"]
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
    if not 350 <= len(days) <= 378:
        raise ValueError("Incomplete contribution calendar")
    metadata = dict(
        account=user["login"],
        start=days[0]["date"],
        end=days[-1]["date"],
        total_contributions=calendar["totalContributions"],
        active_days=sum(day["contributionCount"] > 0 for day in days),
        calendar_days=len(days),
        updated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        source="GitHub GraphQL contributionCalendar",
        generator="Platane/snk@d8f6715049803e982ee5ff501b6b9b7d5deeb09b",
    )
    (ROOT / "generated" / "activity.json").write_text(json.dumps(metadata, indent=2)+"\n", encoding="utf-8")
    for theme in PALETTES:
        for mobile in (False, True):
            name = f"profile-{theme}{'-mobile' if mobile else ''}.svg"
            (ROOT / "assets" / name).write_text(render(theme, mobile), encoding="utf-8")
    readme = """<picture>
  <source media="(prefers-color-scheme: dark) and (max-width: 600px)" srcset="./assets/profile-dark-mobile.svg">
  <source media="(max-width: 600px)" srcset="./assets/profile-light-mobile.svg">
  <source media="(prefers-color-scheme: dark)" srcset="./assets/profile-dark.svg">
  <img src="./assets/profile-light.svg" width="100%" alt="Mackeabit — Learning by doing. Making everyday things simpler. Exploring AI &amp; Automation, Systems &amp; Security, and Everyday Tools. Java · Python · Git · Codex · Obsidian. A teal snake follows my real GitHub contributions.">
</picture>
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    print("Rendered four self-contained SVG profiles and README.md.")


if __name__ == "__main__":
    main()
