"""Render account token activity and publish via the existing Codex GitHub connection.

Standard library only. No model turns, credentials copied, or external SVG resources.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import xml.etree.ElementTree as ET

REPO = 'Mackeabit/Mackeabit'
PREFIX = 'generated/codex-activity'
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)


class Rpc:
    def __init__(self, binary):
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        self.proc = subprocess.Popen([binary, 'app-server'], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     text=True, encoding='utf-8', **options)
        self.q = queue.Queue()
        self.seq = 0
        self.thread_id = None
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.call('initialize', {'clientInfo': {'name': 'github_profile_activity', 'version': '1.0.0'},
                                     'capabilities': {'experimentalApi': True}})
            self.send({'method': 'initialized'})
        except Exception:
            self.close()
            raise

    def _read(self):
        for line in self.proc.stdout:
            try: self.q.put(json.loads(line))
            except ValueError: pass
        self.q.put(None)

    def send(self, message):
        self.proc.stdin.write(json.dumps(message) + '\n')
        self.proc.stdin.flush()

    def call(self, method, params=None, timeout=90):
        self.seq += 1
        request = {'id': self.seq, 'method': method}
        if params is not None: request['params'] = params
        self.send(request)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise RuntimeError(f'{method}: timed out')
            try: msg = self.q.get(timeout=remaining)
            except queue.Empty: raise RuntimeError(f'{method}: timed out') from None
            if msg is None: raise RuntimeError('Codex process closed')
            if msg.get('id') == self.seq and 'method' not in msg:
                if 'error' in msg:
                    raise RuntimeError(f'{method}: RPC error {msg["error"].get("code")}')
                return msg['result']
            if 'id' in msg and 'method' in msg:
                # Do not silently grant authentication, policy, or permission requests.
                self.send({'id': msg['id'], 'error': {'code': -32601, 'message': 'Interactive request unsupported'}})
                raise RuntimeError('Interactive approval/authentication required; no automatic approval')

    def github(self, tool, args):
        allowed = {'fetch', 'fetch_file', 'create_tree', 'create_commit', 'update_ref'}
        if tool not in allowed: raise ValueError('Tool outside publisher scope')
        if self.thread_id is None:
            # A temporary protocol context for MCP; never starts a model turn or saves a chat.
            self.thread_id = self.call('thread/start', {'ephemeral': True, 'cwd': str(Path.cwd())})['thread']['id']
            result = self.call('mcpServerStatus/list', {'threadId': self.thread_id, 'serverName': 'codex_apps',
                                                       'detail': 'toolsAndAuthOnly'})
            available = {k for s in result.get('data', []) for k in s.get('tools', {})}
            if not all('github.' + k in available for k in allowed):
                raise RuntimeError('Existing GitHub connection lacks required tools')
        result = self.call('mcpServer/tool/call', {'threadId': self.thread_id, 'server': 'codex_apps',
                                                 'tool': 'github.' + tool, 'arguments': args})
        if result.get('isError'): raise RuntimeError(f'GitHub {tool} failed; last published image preserved')
        body = result.get('structuredContent')
        if not isinstance(body, dict): raise RuntimeError(f'GitHub {tool}: missing structured result')
        return body

    def close(self):
        self.proc.terminate()
        try: self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)


def normalize(raw, today=None):
    today = today or datetime.now(timezone.utc).date()
    summary = raw.get('summary')
    buckets = raw.get('dailyUsageBuckets')
    keys = ['lifetimeTokens', 'peakDailyTokens', 'longestRunningTurnSec', 'currentStreakDays', 'longestStreakDays']
    if not isinstance(summary, dict) or not isinstance(buckets, list) or not buckets:
        raise ValueError('Usage is unavailable; refusing an empty replacement')
    stats = {}
    for key in keys:
        value = summary.get(key)
        if value is not None and (type(value) is not int or value < 0): raise ValueError('Invalid summary')
        stats[key] = value
    days = {}
    for bucket in buckets:
        stamp = bucket['startDate']
        parsed = date.fromisoformat(stamp)
        count = bucket['tokens']
        if parsed.isoformat() != stamp or parsed > today or stamp in days:
            raise ValueError('Invalid, future, or duplicate date')
        if type(count) is not int or count < 0: raise ValueError('Invalid token count')
        days[stamp] = count
    if not any(days.values()) or stats['lifetimeTokens'] is None:
        raise ValueError('Usage is empty or incomplete')
    if sum(days.values()) > stats['lifetimeTokens']: raise ValueError('Daily total exceeds lifetime total')
    if stats['peakDailyTokens'] is not None and max(days.values()) > stats['peakDailyTokens']:
        raise ValueError('Daily count exceeds reported peak')
    end = max(days)
    if (today - date.fromisoformat(end)).days > 7: raise ValueError('Usage data is over seven days old')
    return {'schema': 1, 'source': 'Codex account/usage/read', 'dataThrough': end,
            'summary': stats, 'days': [{'date': d, 'tokens': days[d]} for d in sorted(days)]}


def check_regression(data, previous):
    if previous and (data['dataThrough'] < previous['dataThrough'] or
                     data['summary']['lifetimeTokens'] < previous['summary']['lifetimeTokens']):
        raise ValueError('Account data regressed; preserving last published activity')


def compact(value):
    if value is None: return '—'
    for scale, suffix in [(10**9, 'B'), (10**6, 'M'), (10**3, 'K')]:
        if value >= scale: return f'{value / scale:.2f}'.rstrip('0').rstrip('.') + suffix
    return str(value)


def render(data, theme):
    dark = theme == 'dark'
    fg, muted = ('#f0f6fc', '#8b949e') if dark else ('#1f2328', '#656d76')
    colors = ['#262c36', '#053963', '#075b9c', '#1683d8', '#69b7ff'] if dark else ['#ebedf0', '#cce7ff', '#8dcbff', '#399cf4', '#0969da']
    root = ET.Element(f'{{{NS}}}svg', {'width': '828', 'height': '260', 'viewBox': '0 0 828 260',
                        'role': 'img', 'aria-labelledby': 'title desc'})
    def el(tag, text=None, **attrs):
        node = ET.SubElement(root, f'{{{NS}}}{tag}', {k.replace('_','-'): str(v) for k,v in attrs.items()})
        node.text = text
        return node
    el('title', "Mackeabit's Codex token activity", id='title')
    el('desc', 'Account-wide daily token usage. Blue intensity uses quartiles of active days in the displayed period. Data through ' + data['dataThrough'], id='desc')
    el('style', f'text{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;fill:{fg}}}.muted{{fill:{muted}}}')
    stats = data['summary']
    seconds = stats['longestRunningTurnSec']
    duration = '—' if seconds is None else f'{seconds // 3600}h {(seconds % 3600) // 60}m'
    items = [('Lifetime tokens', compact(stats['lifetimeTokens'])), ('Peak day', compact(stats['peakDailyTokens'])),
             ('Longest task', duration), ('Longest streak', f"{stats['longestStreakDays']} days" if stats['longestStreakDays'] is not None else '—'),
             ('Current streak', f"{stats['currentStreakDays']} days" if stats['currentStreakDays'] is not None else '—')]
    for i, (label, value) in enumerate(items):
        x = 24 + i * 158
        el('text', value, x=x, y=26, font_size=19, font_weight=600)
        el('text', label, x=x, y=47, font_size=12, **{'class':'muted'})
    el('text', 'Codex token activity', x=24, y=85, font_size=14, font_weight=600)
    end = date.fromisoformat(data['dataThrough'])
    start = end - timedelta(days=(end.weekday()+1)%7 + 52*7)
    daily = {d['date']:d['tokens'] for d in data['days']}
    active = sorted(n for d,n in daily.items() if start.isoformat() <= d <= end.isoformat() and n > 0)
    cuts = [active[min(len(active)-1, int((len(active)-1)*q))] for q in [.25,.5,.75]]
    seen_months = set()
    for col in range(53):
        for row in range(7):
            day = start + timedelta(days=col*7+row)
            if day > end: continue
            value = daily.get(day.isoformat(),0)
            level = 0 if value == 0 else 1 + sum(value > q for q in cuts)
            cell = el('rect', x=24+col*14.7, y=101+row*14.7, width=11.7, height=11.7, rx=2.4,
                      fill=colors[level], data_date=day.isoformat(), data_tokens=value)
            ET.SubElement(cell, f'{{{NS}}}title').text = f'{day.isoformat()}: {value:,} tokens'
            month = (day.year, day.month)
            if (day.day == 1 or col == 0 and row == 0) and month not in seen_months:
                el('text', day.strftime('%b'), x=24+col*14.7, y=219, font_size=11, **{'class':'muted'})
                seen_months.add(month)
    el('text', 'Data through ' + data['dataThrough'], x=24, y=246, font_size=11, **{'class':'muted'})
    el('text', 'Less', x=657, y=246, font_size=11, **{'class':'muted'})
    for i, color in enumerate(colors): el('rect', x=688+i*15, y=236, width=11, height=11, rx=2, fill=color)
    el('text', 'More', x=770, y=246, font_size=11, **{'class':'muted'})
    return ET.tostring(root, encoding='unicode')+'\n'


def outputs(data):
    return {PREFIX+'.json': json.dumps(data, indent=2)+'\n',
            **{PREFIX+f'-{theme}.svg': render(data,theme) for theme in ['dark','light']}}


def fetch_json(rpc, url):
    result = rpc.github('fetch', {'url':url})
    return json.loads(result['content'])


def publish(rpc, files, data, bootstrap=False):
    ref = fetch_json(rpc, f'https://api.github.com/repos/{REPO}/git/ref/heads/main')
    head = ref['object']['sha']
    tree = fetch_json(rpc, f'https://api.github.com/repos/{REPO}/git/trees/{head}?recursive=1')
    if tree.get('truncated'): raise RuntimeError('Incomplete repository tree')
    present = {item['path'] for item in tree['tree']}
    existing = set(files) & present
    if existing != set(files) and (not bootstrap or existing):
        raise RuntimeError('Expected output files missing; bootstrap is only allowed when all are absent')
    if PREFIX+'.json' in present:
        previous = rpc.github('fetch_file', {'repository_full_name':REPO, 'path':PREFIX+'.json', 'ref':head})
        check_regression(data, json.loads(previous['content']))
    # Compare all outputs; allows a repaired renderer to publish with unchanged input.
    changed = []
    for path, content in files.items():
        old = rpc.github('fetch_file', {'repository_full_name':REPO,'path':path,'ref':head}) if path in present else None
        if old is None or old['content'] != content:
            changed.append({'path':path,'mode':'100644','type':'blob','content':content})
    if not changed: return {'status':'unchanged','commit':head}
    new_tree = rpc.github('create_tree', {'repository_full_name':REPO, 'base_tree_sha':tree['sha'], 'tree_elements':changed})
    commit = rpc.github('create_commit', {'repository_full_name':REPO, 'parent_sha':head,
                      'tree_sha':new_tree['sha'], 'message':'Refresh Codex token activity through '+data['dataThrough']})
    rpc.github('update_ref', {'repository_full_name':REPO,'branch_name':'main',
                             'sha':commit['sha'],'expected_sha':head,'force':False})
    for path, content in files.items():
        readback = rpc.github('fetch_file', {'repository_full_name':REPO,'path':path,'ref':commit['sha']})
        if readback['content'] != content: raise RuntimeError('Published readback mismatch')
    return {'status':'published','commit':commit['sha']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex', default=str(Path.home()/'.local/bin/codex'))
    parser.add_argument('--input', type=Path, help='Offline usage response; cannot be combined with --publish')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--bootstrap', action='store_true', help='Initialize all three missing output files once')
    args = parser.parse_args()
    if args.input and args.publish: parser.error('Offline data cannot be published')
    rpc = None
    try:
        if args.input: raw = json.loads(args.input.read_text(encoding='utf-8'))
        else:
            rpc = Rpc(args.codex)
            raw = rpc.call('account/usage/read')
        data = normalize(raw)
        old_path = args.output_dir/(PREFIX+'.json')
        previous = json.loads(old_path.read_text(encoding='utf-8')) if old_path.exists() else None
        check_regression(data, previous)
        files = outputs(data)
        result = publish(rpc, files, data, args.bootstrap) if args.publish else {'status':'rendered'}
        for name, content in files.items():
            path = args.output_dir/name
            path.parent.mkdir(parents=True,exist_ok=True)
            tmp = path.with_suffix(path.suffix+'.tmp')
            tmp.write_text(content,encoding='utf-8')
            tmp.replace(path)
        print(json.dumps({**result,'dataThrough':data['dataThrough'],'activeDays':sum(d['tokens']>0 for d in data['days'])}))
    finally:
        if rpc: rpc.close()


if __name__ == '__main__':
    main()
