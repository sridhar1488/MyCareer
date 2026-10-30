"""Validate discovery deliverables without modifying the source workbook."""
from pathlib import Path
from zipfile import ZipFile
import hashlib
import json
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs' / 'evidence'
inventory = json.loads((EVIDENCE / 'workbook-inventory.json').read_text(encoding='utf-8'))
workbook = ROOT / inventory['file']
checks = []

def check(name, condition):
    checks.append({'check': name, 'passed': bool(condition)})

check('Original workbook SHA256 matches discovery', hashlib.sha256(workbook.read_bytes()).hexdigest() == inventory['sha256'])
check('Exactly the two required visible sheets', [(s['name'], s['state']) for s in inventory['sheets']] == [('Sample Evaluation Form', 'visible'), ('RatingScale', 'visible')])
expected = {
    'F24': 'SUM(F19:F23)', 'F26': 'F24/F25',
    'F33': 'SUM(F30:F32)', 'F35': 'F33/F34',
    'F50': 'SUM(F39:F49)', 'F51': 'AVERAGE(F39:F49)',
    'F53': '(F26*(7/10))', 'F54': '(F35*(1/10))',
    'F55': '(F51*(2/10))', 'F57': 'SUM(F53:F55)',
}
actual = {c['cell']: c['formula'] for c in inventory['sheets'][0]['cells'] if c['formula']}
check('All ten source formulas exactly match documented references', actual == expected)
ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with ZipFile(workbook) as z:
    source_formula_count = sum(len(ET.fromstring(z.read(n)).findall('.//m:f', ns)) for n in z.namelist() if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', n))
check('No additional source formulas omitted', source_formula_count == len(actual))
cell_doc = (EVIDENCE / 'workbook-cells.md').read_text(encoding='utf-8')
populated = sum(c['value'] is not None or c['formula'] is not None for s in inventory['sheets'] for c in s['cells'])
cell_rows = [line for line in cell_doc.splitlines() if re.match(r'\| [A-Z]+\d+ \|', line)]
check('All 136 populated/formula cells listed', populated == 136 == len(cell_rows))
spec = (ROOT / 'docs' / '02-workbook-specification.md').read_text(encoding='utf-8')
check('Every formula appears in form specification', all('`='+formula+'`' in spec for formula in expected.values()))
broken = []
for path in [ROOT / 'README.md', *(ROOT / 'docs').glob('*.md')]:
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
        if target.startswith(('http:', 'https:', '#')):
            continue
        if not (path.parent / target.split('#')[0]).exists():
            broken.append(f'{path.name}: {target}')
check('Documentation local links resolve', not broken)
branding = json.loads((EVIDENCE / 'branding-inventory.json').read_text(encoding='utf-8'))
kit = branding.get('global_kit_declarations') or ''
check('Brand colors and font sourced to global theme', all(v in kit for v in ['--e-global-color-primary:#702C91', '--e-global-color-secondary:#FE2072', 'Franklin Gothic ATC']))
check('Official logo references captured', any('MedImpact-International-Clear-Background.webp' in t for t in branding['image_candidates']))
versions = json.loads((EVIDENCE / 'version-candidates.json').read_text(encoding='utf-8'))
check('All candidate registry requests succeeded', len(versions) == 17 and all('version' in v and 'error' not in v for v in versions))
result = {'checks': checks, 'passed': sum(c['passed'] for c in checks), 'total': len(checks),
          'source_sha256': inventory['sha256'], 'broken_links': broken,
          'scope': 'Discovery evidence only; no application tests or runtime compatibility validation.'}
(EVIDENCE / 'discovery-verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
