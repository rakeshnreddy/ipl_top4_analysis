"""Capture the fixed, public page matrix through gstack's browser driver."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BROWSER = '/Users/Rakesh/.codex/skills/gstack/browse/dist/browse'
PAGES = {'landing': '', 'hub': '?view=hub', 'football': '?league=epl-2026-27',
         'cricket': '?league=ipl-2026', 'f1': '?league=f1-2026', 'share': 'share.html'}

def capture(base, label, css=None):
    output = ROOT / 'docs' / 'screenshots' / label
    output.mkdir(parents=True, exist_ok=True)
    metrics = []
    for name, query in PAGES.items():
        if css and name == 'share':
            continue
        commands = [['goto', base + query], ['wait', 'h1']]
        if css:
            commands.append(['js', f"(() => {{const s=document.createElement('style');s.textContent={json.dumps(css)};document.head.append(s)}})()"])
        for theme in ('light', 'dark'):
            commands.append(['js', f"document.documentElement.dataset.theme='{theme}';localStorage.setItem('pp-theme','{theme}')"])
            for width, height in (((375, 812), (1280, 900)) if css else ((375, 812), (768, 1024), (1280, 900))):
                commands.extend([
                    ['viewport', f'{width}x{height}'],
                    ['js', 'window.scrollTo(0,0)'],
                    ['screenshot', '--viewport', str(output / f'{name}-{theme}-{width}.png')],
                    ['js', "JSON.stringify({url:location.href,title:document.title,width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,smallText:[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().height&&parseFloat(getComputedStyle(e).fontSize)<12).length})"],
                ])
        commands.append(['console', '--errors'])
        result = subprocess.run([BROWSER, 'chain'], input=json.dumps(commands), text=True, capture_output=True)
        (output / f'{name}.jsonl').write_text(result.stdout + result.stderr)
        metrics.append({'page': name, 'exit': result.returncode})
        print(json.dumps(metrics[-1]), flush=True)
        if result.returncode or 'ERROR:' in result.stdout:
            print((result.stdout + result.stderr)[-1800:], flush=True)
            raise SystemExit(result.returncode or 1)
    (output / 'manifest.json').write_text(json.dumps({'base': base, 'pages': metrics}, indent=2))

if __name__ == '__main__':
    if sys.argv[2] == 'directions':
        for direction in ('night-signal', 'season-ledger', 'race-control'):
            capture(sys.argv[1], 'directions/' + direction,
                    (ROOT / 'docs' / 'design-directions' / f'{direction}.css').read_text())
    else:
        capture(sys.argv[1], sys.argv[2])
