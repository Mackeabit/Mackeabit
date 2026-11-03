"""Check generated grass against the actual daily data and reject text/static output."""
from datetime import date, timedelta
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
data = json.loads((root/'generated/codex-activity.json').read_text(encoding='utf-8'))
end = date.fromisoformat(data['dataThrough'])
start = end-timedelta(days=(end.weekday()+1)%7+364)
expected_days = (end-start).days+1
expected_active = sum(d['tokens']>0 for d in data['days'] if start.isoformat()<=d['date']<=end.isoformat())
for theme in ['dark','light']:
    svg = ET.parse(root/f'generated/codex-activity-{theme}.svg').getroot()
    cells = [n for n in svg if 'c' in n.get('class','').split()]
    assert len(cells)==expected_days, 'Calendar day count differs from source'
    assert sum(len(n.get('class','').split())>1 for n in cells)==expected_active, 'Active day count differs from source'
    assert sum('s' in n.get('class','').split() for n in svg)==4, 'Four-part snake is missing'
    assert not any('comet' in n.get('class','').split() for n in svg), 'Old comet remains'
    css=''.join(n.text or '' for n in svg if n.tag.endswith('}style'))
    assert ('--cs:#c4b5fd' if theme=='dark' else '--cs:#8b5cf6') in css, 'Lavender color missing'
    palette = ['#262c36', '#053963', '#075b9c', '#1683d8', '#69b7ff'] if theme=='dark' else ['#ebedf0', '#cce7ff', '#8dcbff', '#399cf4', '#0969da']
    counts = {d['date']: d['tokens'] for d in data['days']}
    active = sorted(v for k,v in counts.items() if start.isoformat()<=k<=end.isoformat() and v>0)
    cuts = [active[int((len(active)-1)*q)] for q in [.25,.5,.75]]
    for i, cell in enumerate(cells):
        count = counts.get((start+timedelta(days=i)).isoformat(), 0)
        level = 0 if count==0 else 1+sum(count>cut for cut in cuts)
        if level:
            cell_id=cell.get('class').split()[1]
            assert f'.c.{cell_id}'+'{fill:var(--c'+str(level)+')' in css, 'Cell initial color differs from source'
        assert (f'--c{level}:'+palette[level]) in css if level else ('--ce:'+palette[0]) in css, 'Palette differs from source'
        assert cell.get('x')==str(i//7*16+2) and cell.get('y')==str(i%7*16+2), 'Cell position differs from date'
    assert not any('u' in n.get('class','').split() for n in svg), 'Consumption bar should be hidden'
    assert not any(n.tag.rsplit('}',1)[-1] in ['text','script','foreignObject'] for n in svg.iter()), 'Visible labels or active content found'
    css=''.join(n.text or '' for n in svg if n.tag.endswith('}style'))
    assert '@keyframes s0' in css and 'infinite' in css, 'Snake is not animated'
    assert 'filter:url(#snake-glow)' in css and '.s.s3{opacity:.55}' in css, 'Glow or fading tail missing'
    assert any(n.get('id')=='snake-glow' for n in svg.iter()), 'Glow filter missing'
    assert 'prefers-reduced-motion' in css, 'Reduced-motion fallback missing'
    assert svg.get('height')=='160'
    print(f'{theme}: {len(cells)} days, {expected_active} active cells, lavender snake with head glow and fading tail, no visible text')
