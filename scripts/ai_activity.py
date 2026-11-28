"""Sum Codex and per-host Claude Code daily tokens into the single series the snake draws.

Reads generated/codex-activity.json and generated/claude-activity/*.json, writes
.tmp/ai-activity.json. Both the renderer and the verifier use that one file.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOST_FILE = re.compile(r'^([0-9a-f]{8})\.json$')


def daily(items, key, today, label):
    days = {}
    for item in items:
        stamp, tokens = item.get('date'), item.get(key)
        if not isinstance(stamp, str) or date.fromisoformat(stamp).isoformat() != stamp or date.fromisoformat(stamp) > today:
            raise ValueError(f'{label}: invalid or future date')
        if stamp in days or type(tokens) is not int or tokens < 0:
            raise ValueError(f'{label}: invalid or duplicate token count')
        days[stamp] = tokens
    return days


def combine(codex, claude_files, today=None):
    """codex: parsed codex-activity.json or None; claude_files: {filename: parsed host file}."""
    today = today or datetime.now(timezone.utc).date()
    sources = []
    if codex is not None:
        if codex.get('schema') != 1: raise ValueError('Unexpected Codex activity file')
        sources.append(daily(codex['days'], 'tokens', today, 'Codex'))
    for name, data in sorted(claude_files.items()):
        match = HOST_FILE.match(name)
        if not match or data.get('schema') != 1 or data.get('host') != match.group(1):
            raise ValueError(f'Unexpected Claude activity file {name}')
        sources.append(daily(data['days'], 'tokens', today, name))
    total = {}
    for source in sources:
        for day, tokens in source.items(): total[day] = total.get(day, 0) + tokens
    if not any(total.values()): raise ValueError('No AI activity to draw')
    return {'dataThrough': max(total), 'sources': len(sources),
            'days': [{'date': d, 'tokens': total[d]} for d in sorted(total)]}


def main():
    codex_path = ROOT / 'generated' / 'codex-activity.json'
    codex = json.loads(codex_path.read_text(encoding='utf-8')) if codex_path.exists() else None
    folder = ROOT / 'generated' / 'claude-activity'
    claude = {p.name: json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*.json'))} if folder.is_dir() else {}
    result = combine(codex, claude)
    out = ROOT / '.tmp' / 'ai-activity.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"Combined Codex{' ' if codex else ' (missing) '}and {len(claude)} Claude host(s) through {result['dataThrough']}.")


if __name__ == '__main__':
    main()
