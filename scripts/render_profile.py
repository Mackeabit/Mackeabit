"""Prepare standalone profile graphics; keep all profile copy in README.md."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
TOOLS = ("Java", "Python", "Git", "Codex", "Obsidian")


def element(name, **attributes):
    return ET.Element(
        f"{{{NS}}}{name}",
        {key.replace("_", "-"): str(value) for key, value in attributes.items()},
    )


def write_svg(path, svg):
    for node in svg.iter():
        if node.tag.rsplit("}", 1)[-1] in {"script", "foreignObject"}:
            raise ValueError("Unsupported active SVG content")
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1] == "href" and not value.startswith(("data:", "#")):
                raise ValueError("External image resources are not allowed")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ET.tostring(svg, encoding="unicode") + "\n", encoding="utf-8")


def prepare_icons():
    for label in TOOLS:
        name = label.lower()
        tile = element("svg", width=56, height=56, viewBox="0 0 56 56", role="img")
        title = ET.SubElement(tile, f"{{{NS}}}title")
        title.text = label
        defs = element("defs")
        monochrome = element("filter", id="monochrome", color_interpolation_filters="sRGB")
        monochrome.append(element("feColorMatrix", type="saturate", values=0))
        brightness = element("feComponentTransfer")
        for channel in ("R", "G", "B"):
            brightness.append(element("feFunc" + channel, type="linear", slope=".48"))
        monochrome.append(brightness)
        defs.append(monochrome)
        tile.append(defs)
        tile.append(element("rect", x=".5", y=".5", width=55, height=55, rx=12, fill="#f4f7f5", stroke="#e2e9e5"))
        mark = ET.parse(ROOT / "assets" / "icons" / f"{name}.svg").getroot()
        mark.attrib.pop("style", None)
        for key, value in dict(x="12.5", y="12.5", width="31", height="31", color="#111111", filter="url(#monochrome)").items():
            mark.set(key, value)
        tile.append(mark)
        write_svg(ROOT / "assets" / "tools" / f"{name}.svg", tile)

    accent = element("svg", width=828, height=4, viewBox="0 0 828 4", preserveAspectRatio="none")
    accent.append(element("rect", width=828, height=4, rx=2, fill="#25c6b0"))
    write_svg(ROOT / "assets" / "accent.svg", accent)


def prepare_snakes(ai=False):
    for theme in ("light", "dark"):
        source = ROOT / ".tmp" / f"ai-snake-{theme}.svg" if ai else ROOT / "generated" / f"snake-{theme}.svg"
        svg = ET.parse(source).getroot()
        cells = [node for node in svg.iter() if "c" in node.get("class", "").split()]
        if not 350 <= len(cells) <= 378:
            raise ValueError(f"Unexpected contribution calendar size: {len(cells)}")
        if not any("s" in node.get("class", "").split() for node in svg.iter()):
            raise ValueError("Snake animation is missing")
        # Keep the generated path and original cells. Omit only the consumption bar.
        vx, vy, vw, _ = map(float, svg.get("viewBox").split())
        svg.set("viewBox", f"{vx:g} {vy:g} {vw:g} 160")
        svg.set("height", "160")
        svg.set("id", "contribution-snake")
        svg.set("role", "img")
        for node in list(svg):
            if "u" in node.get("class", "").split():
                svg.remove(node)
        title = element("title")
        title.text = "Mackeabit's AI activity" if ai else "Mackeabit's real public repository activity"
        svg.insert(0, title)
        motion = element("style")
        motion.text = "@media(prefers-reduced-motion:reduce){*{animation:none!important}}"
        svg.append(motion)
        write_svg(ROOT / "generated" / f"{'codex-activity' if ai else 'trail'}-{theme}.svg", svg)


def update_activity():
    calendar = json.loads((ROOT / ".tmp" / "repository-activity.json").read_text(encoding="utf-8"))
    if calendar["account"].lower() != "mackeabit":
        raise ValueError("Unexpected GitHub account")
    days = calendar["days"]
    if not 365 <= len(days) <= 371:
        raise ValueError("Incomplete repository activity calendar")
    if sum(day["count"] for day in days) != calendar["total_contributions"]:
        raise ValueError("Activity totals do not match daily counts")
    if sum(day["count"] > 0 for day in days) != calendar["active_days"]:
        raise ValueError("Active-day total does not match daily counts")
    activity_path = ROOT / "generated" / "activity.json"
    if activity_path.exists():
        previous = json.loads(activity_path.read_text(encoding="utf-8"))
        if previous.get("total_contributions", 0) and calendar["total_contributions"] == 0:
            raise ValueError("GitHub returned empty activity; the published snake will be preserved.")
    for theme in ("light", "dark"):
        svg = ET.parse(ROOT / "generated" / f"snake-{theme}.svg").getroot()
        cells = [node for node in svg.iter() if "c" in node.get("class", "").split()]
        active = sum(len(node.get("class", "").split()) > 1 for node in cells)
        if len(cells) != len(days) or active != calendar["active_days"]:
            raise ValueError("Generated snake does not match the collected activity")
    metadata = {key: value for key, value in calendar.items() if key != "days"}
    metadata["generator"] = "Platane/snk@d8f6715049803e982ee5ff501b6b9b7d5deeb09b with repository activity adapter"
    activity_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (ROOT / "generated" / "activity-calendar.json").write_text(json.dumps(calendar, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-only", action="store_true", help="Prepare assets from existing snake files without changing activity metadata.")
    parser.add_argument("--icons-only", action="store_true", help="Prepare icon tiles and accent without touching retired contribution graphics.")
    parser.add_argument("--ai-snake-only", action="store_true", help="Finish the AI activity animation without labels or statistics.")
    args = parser.parse_args()
    if args.ai_snake_only:
        prepare_snakes(ai=True)
        print("Prepared AI activity snakes without summary text.")
        return
    if not args.assets_only and not args.icons_only:
        update_activity()
    prepare_icons()
    if not args.icons_only:
        prepare_snakes()
    print("Prepared separate icons and contribution animations. README.md is unchanged.")


if __name__ == "__main__":
    main()
