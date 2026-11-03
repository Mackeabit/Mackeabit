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
    assert any('s' in n.get('class','').split() for n in svg), 'Snake is missing'
    assert not any('u' in n.get('class','').split() for n in svg), 'Consumption bar should be hidden'
    assert not any(n.tag.rsplit('}',1)[-1] in ['text','script','foreignObject'] for n in svg.iter()), 'Visible labels or active content found'
    css=''.join(n.text or '' for n in svg if n.tag.endswith('}style'))
    assert '@keyframes' in css and 'infinite' in css, 'Snake is not animated'
    assert 'prefers-reduced-motion' in css, 'Reduced-motion fallback missing'
    assert svg.get('height')=='160'
    print(f'{theme}: {len(cells)} days, {expected_active} active cells, animated snake, no visible text')
