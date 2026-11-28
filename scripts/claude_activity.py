"""Collect this machine's Claude Code token activity and publish it as one per-host aggregate.

Claude Pro/Max has no account-wide usage API, so every machine that runs Claude Code
publishes its own daily totals to generated/claude-activity/<host-id>.json. The host id
is random (no hostname, user or path is published). Days are merged with the copy already
in the repository by keeping the larger total, so local transcript cleanup never erases
published history. Only completed UTC days are published.

Standard library only. The GitHub token comes from GH_TOKEN/GITHUB_TOKEN or `gh auth token`
and is never written anywhere.
"""
from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import urllib.error
import urllib.request

REPO = 'Mackeabit/Mackeabit'
DIRECTORY = 'generated/claude-activity'
SOURCE = 'Claude Code local transcripts'
FIELDS = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')
HOST_ID = re.compile(r'^[0-9a-f]{8}$')


def default_claude_dirs():
    configured = os.environ.get('CLAUDE_CONFIG_DIR')
    return [Path(configured)] if configured else [Path.home() / '.claude']


def host_id(path: Path):
    if path.exists():
        value = path.read_text(encoding='utf-8').strip()
        if not HOST_ID.match(value): raise ValueError(f'Invalid host id in {path}')
        return value
    value = secrets.token_hex(4)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + '\n', encoding='utf-8')
    return value


def collect(claude_dirs, today):
    """Return {date: tokens} for completed UTC days from local Claude Code transcripts."""
    messages = {}
    for claude_dir in claude_dirs:
        projects = Path(claude_dir) / 'projects'
        if not projects.is_dir(): continue
        for transcript in projects.rglob('*.jsonl'):
            with transcript.open(encoding='utf-8', errors='replace') as handle:
                for line in handle:
                    if '"usage"' not in line: continue
                    try: record = json.loads(line)
                    except ValueError: continue
                    if record.get('type') != 'assistant': continue
                    message = record.get('message')
                    usage = message.get('usage') if isinstance(message, dict) else None
                    stamp = record.get('timestamp')
                    if not isinstance(usage, dict) or not isinstance(stamp, str): continue
                    # Streaming and resumed sessions repeat a response; count each response once.
                    key = (message.get('id'), record.get('requestId'))
                    if None in key: key = ('uuid', record.get('uuid') or line)
                    counts = [usage.get(field) or 0 for field in FIELDS]
                    if any(type(value) is not int or value < 0 for value in counts): continue
                    day = datetime.fromisoformat(stamp.replace('Z', '+00:00')).astimezone(timezone.utc).date()
                    previous = messages.get(key)
                    if previous:
                        counts = [max(a, b) for a, b in zip(previous[1], counts)]
                        day = min(day, previous[0])
                    messages[key] = (day, counts)
    days = {}
    for day, counts in messages.values():
        if day >= today: continue
        days[day.isoformat()] = days.get(day.isoformat(), 0) + sum(counts)
    return {d: n for d, n in days.items() if n > 0}


def validate(data, host, today):
    if not isinstance(data, dict) or data.get('schema') != 1 or data.get('source') != SOURCE or data.get('host') != host:
        raise ValueError('Unexpected Claude activity file')
    days = {}
    for item in data.get('days', []):
        stamp, tokens = item.get('date'), item.get('tokens')
        if not isinstance(stamp, str) or date.fromisoformat(stamp).isoformat() != stamp or date.fromisoformat(stamp) >= today:
            raise ValueError('Invalid or incomplete day in Claude activity')
        if stamp in days or type(tokens) is not int or tokens < 0: raise ValueError('Invalid Claude token count')
        days[stamp] = tokens
    return days


def build(host, current, previous):
    """Merge with the published copy; a day's total can grow but never shrink."""
    merged = dict(previous)
    for day, tokens in current.items(): merged[day] = max(tokens, merged.get(day, 0))
    if not merged: raise ValueError('No Claude Code usage found; refusing an empty file')
    return {'schema': 1, 'source': SOURCE, 'host': host, 'dataThrough': max(merged),
            'days': [{'date': d, 'tokens': merged[d]} for d in sorted(merged)]}


def render(data):
    return json.dumps(data, indent=2) + '\n'


def github_token():
    """GH_TOKEN/GITHUB_TOKEN, then `gh auth token`, then git's credential helper (never interactive)."""
    for name in ('GH_TOKEN', 'GITHUB_TOKEN'):
        if os.environ.get(name): return os.environ[name]
    quiet = {'capture_output': True, 'text': True, 'timeout': 30,
             'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
    gh = shutil.which('gh')
    if gh:
        result = subprocess.run([gh, 'auth', 'token'], **quiet)
        if result.returncode == 0 and result.stdout.strip(): return result.stdout.strip()
    git = shutil.which('git')
    if git:
        env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
        result = subprocess.run([git, 'credential', 'fill'], input='protocol=https\nhost=github.com\n\n', env=env, **quiet)
        fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if result.returncode == 0 and fields.get('password'): return fields['password']
    raise RuntimeError('No GitHub token: set GH_TOKEN, `gh auth login`, or sign in to github.com with git')


def api(token, method, path, body=None):
    request = urllib.request.Request(f'https://api.github.com/repos/{REPO}/contents/{path}',
                                     data=None if body is None else json.dumps(body).encode(), method=method,
                                     headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                                              'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'profile-activity'})
    try:
        with urllib.request.urlopen(request, timeout=60) as response: return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404 and method == 'GET': return None
        raise RuntimeError(f'GitHub {method} {path}: HTTP {error.code}') from None


def publish(host, current, today):
    token = github_token()
    path = f'{DIRECTORY}/{host}.json'
    for attempt in range(2):
        remote = api(token, 'GET', path + '?ref=main')
        previous = validate(json.loads(base64.b64decode(remote['content'])), host, today) if remote else {}
        data = build(host, current, previous)
        content = render(data)
        if remote and base64.b64decode(remote['content']).decode('utf-8') == content:
            return data, 'unchanged'
        body = {'message': f'Refresh Claude token activity ({host}) through {data["dataThrough"]}',
                'content': base64.b64encode(content.encode()).decode(), 'branch': 'main'}
        if remote: body['sha'] = remote['sha']
        try:
            api(token, 'PUT', path, body)
            return data, 'published'
        except RuntimeError:
            if attempt: raise  # One retry after a concurrent update; never force.


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--claude-dir', type=Path, action='append', help='Claude config dir (default: CLAUDE_CONFIG_DIR or ~/.claude); repeatable')
    parser.add_argument('--host-id-file', type=Path, default=Path.home() / '.mackeabit-profile' / 'claude-host-id')
    parser.add_argument('--publish', action='store_true', help='Merge into the repository copy and commit it to main')
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    host = host_id(args.host_id_file)
    current = collect(args.claude_dir or default_claude_dirs(), today)
    if args.publish: data, status = publish(host, current, today)
    else: data, status = build(host, current, {}), 'dry-run'
    print(json.dumps({'status': status, 'host': host, 'dataThrough': data['dataThrough'],
                      'activeDays': len(data['days']), 'tokens': sum(d['tokens'] for d in data['days'])}))


if __name__ == '__main__':
    main()
