"""Collect Claude Code token activity from this machine and SSH hosts, then publish per-host totals.

Claude Pro/Max has no account-wide usage API, so usage is read from each machine's Claude Code
transcripts. One hub machine runs this daily with --remote for every other machine: the script
is sent over SSH stdin and run there, so remotes need only Python (no GitHub credentials).

- Each machine is published as generated/claude-activity/<host-id>.json. The host id is random
  and kept in ~/.mackeabit-profile/claude-host-id on that machine; no hostname, user, path,
  project, model or text is published, only dates and daily totals.
- A response recorded on several machines (e.g. an SSH session also logged by the client) is
  counted once, for the first machine in run order (this machine, then --remote in the order
  given). Put always-on servers before laptops.
- Days merge with the published copy by keeping the larger total, so transcript cleanup never
  erases history. Published days older than FREEZE_DAYS are final.
- Only completed UTC days are published.

Standard library only. The GitHub token comes from GH_TOKEN/GITHUB_TOKEN, `gh auth token`, or
git's credential helper, and is never written anywhere.
"""
from __future__ import annotations

import argparse
import base64
from datetime import date, datetime, timedelta, timezone
import hashlib
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
RESPONSE_ID = re.compile(r'^[0-9a-f]{16}$')
FREEZE_DAYS = 7
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


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


def responses(claude_dirs, today):
    """Return {response-hash: (date, tokens)} for completed UTC days.

    Streaming and resumed sessions repeat a response (same message id and request id); it is
    counted once. Only a 16-hex hash of the ids leaves this function.
    """
    found = {}
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
                    ids = (message.get('id'), record.get('requestId'))
                    raw = f'{ids[0]}|{ids[1]}' if None not in ids else 'uuid|' + str(record.get('uuid') or line)
                    key = hashlib.sha1(raw.encode()).hexdigest()[:16]
                    counts = [usage.get(field) or 0 for field in FIELDS]
                    if any(type(value) is not int or value < 0 for value in counts): continue
                    day = datetime.fromisoformat(stamp.replace('Z', '+00:00')).astimezone(timezone.utc).date()
                    previous = found.get(key)
                    if previous:
                        counts = [max(a, b) for a, b in zip(previous[1], counts)]
                        day = min(day, previous[0])
                    found[key] = (day, counts)
    return {key: (day.isoformat(), sum(counts)) for key, (day, counts) in found.items() if day < today and sum(counts)}


def totals(found):
    days = {}
    for day, tokens in found.values(): days[day] = days.get(day, 0) + tokens
    return days


def collect(claude_dirs, today):
    """Return {date: tokens} for completed UTC days on this machine."""
    return totals(responses(claude_dirs, today))


def assign(sources):
    """[(host, responses)] in priority order -> [(host, {date: tokens})], each response counted once."""
    seen, result = set(), []
    for host, found in sources:
        result.append((host, totals({k: v for k, v in found.items() if k not in seen})))
        seen.update(found)
    return result


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


def build(host, current, previous, today):
    """Merge with the published copy: totals only grow, and days older than FREEZE_DAYS are final."""
    cutoff = (today - timedelta(days=FREEZE_DAYS)).isoformat()
    merged = dict(previous)
    for day, tokens in current.items():
        if day in previous and day < cutoff: continue
        merged[day] = max(tokens, merged.get(day, 0))
    if not merged: raise ValueError('No Claude Code usage found; refusing an empty file')
    return {'schema': 1, 'source': SOURCE, 'host': host, 'dataThrough': max(merged),
            'days': [{'date': d, 'tokens': merged[d]} for d in sorted(merged)]}


def render(data):
    return json.dumps(data, indent=2) + '\n'


def github_token():
    """GH_TOKEN/GITHUB_TOKEN, then `gh auth token`, then git's credential helper (never interactive)."""
    for name in ('GH_TOKEN', 'GITHUB_TOKEN'):
        if os.environ.get(name): return os.environ[name]
    quiet = {'capture_output': True, 'text': True, 'timeout': 30, 'creationflags': NO_WINDOW}
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


def publish(token, host, current, today):
    path = f'{DIRECTORY}/{host}.json'
    for attempt in range(2):
        remote_copy = api(token, 'GET', path + '?ref=main')
        previous = validate(json.loads(base64.b64decode(remote_copy['content'])), host, today) if remote_copy else {}
        data = build(host, current, previous, today)
        content = render(data)
        if remote_copy and base64.b64decode(remote_copy['content']).decode('utf-8') == content:
            return data, 'unchanged'
        body = {'message': f'Refresh Claude token activity ({host}) through {data["dataThrough"]}',
                'content': base64.b64encode(content.encode()).decode(), 'branch': 'main'}
        if remote_copy: body['sha'] = remote_copy['sha']
        try:
            api(token, 'PUT', path, body)
            return data, 'published'
        except RuntimeError:
            if attempt: raise  # One retry after a concurrent update; never force.


def emit(host, found):
    """What a remote sends back over SSH: its host id and hashed responses with date and total."""
    return {'schema': 1, 'source': SOURCE, 'host': host,
            'responses': [[key, day, tokens] for key, (day, tokens) in sorted(found.items())]}


def parse_emit(data, today):
    host = data.get('host') if isinstance(data, dict) else None
    if data.get('schema') != 1 or data.get('source') != SOURCE or not isinstance(host, str) or not HOST_ID.match(host):
        raise ValueError('Remote returned unexpected data')
    found = {}
    for key, day, tokens in data.get('responses', []):
        if not RESPONSE_ID.match(key) or date.fromisoformat(day).isoformat() != day or type(tokens) is not int or tokens < 0:
            raise ValueError('Remote returned an invalid response record')
        if day < today.isoformat(): found[key] = (day, tokens)  # Ignore a day the hub still considers open.
    return host, found


def remote(spec, today):
    """Run this script on an SSH host (`alias` or `alias=python-command`) and return (host, responses)."""
    alias, _, python = spec.partition('=')
    # On Windows use the system OpenSSH (it reads Windows-style IdentityFile paths; Git's ssh may not).
    system_ssh = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'OpenSSH' / 'ssh.exe'
    ssh = str(system_ssh) if os.name == 'nt' and system_ssh.exists() else 'ssh'
    command = [ssh, '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', alias, f'{python or "python3"} -I -B - --emit']
    result = subprocess.run(command, input=Path(__file__).read_bytes(), capture_output=True, timeout=900,
                            creationflags=NO_WINDOW)
    if result.returncode != 0:
        raise RuntimeError(f'exit {result.returncode}: {result.stderr.decode(errors="replace").strip()[-300:]}')
    return parse_emit(json.loads(result.stdout), today)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--claude-dir', type=Path, action='append', help='Claude config dir (default: CLAUDE_CONFIG_DIR or ~/.claude); repeatable')
    parser.add_argument('--host-id-file', type=Path, default=Path.home() / '.mackeabit-profile' / 'claude-host-id')
    parser.add_argument('--publish', action='store_true', help='Merge into the repository copies and commit them to main')
    parser.add_argument('--remote', action='append', default=[], metavar='ALIAS[=PYTHON]',
                        help='Also collect from an SSH host (key auth); repeatable, in priority order')
    parser.add_argument('--emit', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    today = datetime.now(timezone.utc).date()
    host = host_id(args.host_id_file)
    local = responses(args.claude_dir or default_claude_dirs(), today)
    if args.emit:
        print(json.dumps(emit(host, local)))
        return
    labels, sources, failures = {host: 'local'}, [(host, local)], 0
    for spec in args.remote:
        label = spec.partition('=')[0]
        try:
            remote_host, found = remote(spec, today)
            if remote_host in labels: raise ValueError(f'host id {remote_host} already reported by {labels[remote_host]}')
            labels[remote_host] = label
            sources.append((remote_host, found))
        except Exception as error:  # One unreachable machine must not block the others.
            failures += 1
            print(json.dumps({'source': label, 'status': 'failed', 'error': str(error)[:300]}))
    token = github_token() if args.publish else None
    for source_host, days in assign(sources):
        label = labels[source_host]
        try:
            if not days:
                print(json.dumps({'source': label, 'status': 'no-usage', 'host': source_host}))
                continue
            data, status = publish(token, source_host, days, today) if args.publish else (build(source_host, days, {}, today), 'dry-run')
            print(json.dumps({'source': label, 'status': status, 'host': source_host, 'dataThrough': data['dataThrough'],
                              'activeDays': len(data['days']), 'tokens': sum(d['tokens'] for d in data['days'])}))
        except Exception as error:
            failures += 1
            print(json.dumps({'source': label, 'status': 'failed', 'host': source_host, 'error': str(error)[:300]}))
    if failures: raise SystemExit(1)


if __name__ == '__main__':
    main()
