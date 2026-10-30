"""Read-only discovery: preserve XLSX XML evidence and public branding sources."""
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET
import json, hashlib, re
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs' / 'evidence'
OUT.mkdir(parents=True, exist_ok=True)
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
book = ROOT / 'MI Performance Appraisal Development Form YE2025.xlsx'
with ZipFile(book) as z:
    strings = ET.fromstring(z.read('xl/sharedStrings.xml'))
    strings = [''.join(si.itertext()) for si in strings]
    styles = ET.fromstring(z.read('xl/styles.xml'))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    targets = {r.attrib['Id']: r.attrib['Target'] for r in rels}
    result = {'file': book.name, 'inspected_at_utc': datetime.now(timezone.utc).isoformat(), 'sha256': hashlib.sha256(book.read_bytes()).hexdigest(),
              'defined_names': [dict(n.attrib, text=n.text) for n in wb.findall('m:definedNames/m:definedName', NS)],
              'calculation': [n.attrib for n in wb.findall('m:calcPr', NS)], 'sheets': []}
    for s in wb.find('m:sheets', NS):
        rid = s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        target = targets[rid].lstrip('/')
        target = target if target.startswith('xl/') else 'xl/' + target
        tree = ET.fromstring(z.read(target))
        cells = []
        for c in tree.findall('.//m:sheetData/m:row/m:c', NS):
            v, f = c.find('m:v', NS), c.find('m:f', NS)
            value = v.text if v is not None else None
            if c.get('t') == 's' and value is not None:
                value = strings[int(value)]
            if c.get('t') == 'inlineStr':
                value = ''.join(c.find('m:is', NS).itertext())
            cells.append({'cell': c.get('r'), 'type': c.get('t'), 'style': c.get('s', '0'),
                          'value': value, 'formula': f.text if f is not None else None})
        meta = {}
        for tag in ['dimension','sheetViews','sheetFormatPr','cols','mergeCells','dataValidations',
                    'conditionalFormatting','sheetProtection','printOptions','pageMargins','pageSetup','headerFooter']:
            meta[tag] = [ET.tostring(n, encoding='unicode') for n in tree.findall('m:'+tag, NS)]
        meta['row_dimensions'] = [n.attrib for n in tree.findall('m:sheetData/m:row', NS)]
        result['sheets'].append({'name': s.get('name'), 'state': s.get('state','visible'), 'cells': cells, 'metadata': meta})
    result['styles_xml'] = ET.tostring(styles, encoding='unicode')
    result['embedded_assets'] = [n for n in z.namelist() if n.startswith(('xl/media/', 'xl/comments', 'xl/drawings/'))]
    result['drawing_xml'] = {n: z.read(n).decode('utf-8') for n in result['embedded_assets'] if n.endswith('.xml')}
    result['theme_xml'] = z.read('xl/theme/theme1.xml').decode('utf-8')
(OUT/'workbook-inventory.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
lines = ['# Workbook cell inventory', '', 'Exact non-empty cell contents and formulas. Cached values are not recalculated results.', '']
for s in result['sheets']:
    lines += ['## '+s['name'], '', '| Cell | Style | Value / formula |', '|---|---|---|']
    for c in s['cells']:
        if c['value'] is None and c['formula'] is None: continue
        text = ('='+c['formula']+' [cached: '+str(c['value'])+']') if c['formula'] else str(c['value'])
        lines.append('| '+c['cell']+' | '+c['style']+' | '+text.replace('|','\\|').replace('\n','<br>')+' |')
    lines += ['']
(OUT/'workbook-cells.md').write_text('\n'.join(lines), encoding='utf-8')

def fetch(url):
    with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=40) as r:
        return r.read().decode('utf-8', errors='replace')

url = 'https://medimpactinternational.com/'
html = fetch(url)
(OUT/'corporate-home.html').write_text(html, encoding='utf-8')
links = re.findall(r'<link\b[^>]*>', html, re.I)
css_urls = []
for link in links:
    if 'stylesheet' in link:
        m = re.search(r'href=[\"\']([^\"\']+)', link)
        if m: css_urls.append(urljoin(url, m.group(1)))
kit = re.search(r'\.elementor-kit-1431\{([^}]+)\}',html)
branding = {'url':url, 'inspected_at_utc': datetime.now(timezone.utc).isoformat(),
            'global_kit_selector': '.elementor-kit-1431',
            'global_kit_declarations': kit.group(1) if kit else None,
            'font_faces': re.findall(r'@font-face\s*\{[^{}]*\}',html),
            'stylesheets':[], 'image_candidates':[], 'inline_colors': sorted(set(re.findall(r'#[0-9a-fA-F]{3,8}\b', html)))}
for i, css_url in enumerate(css_urls):
    try:
        css = fetch(css_url)
        name = f'corporate-style-{i:02}.css'
        (OUT/name).write_text(css, encoding='utf-8')
        branding['stylesheets'].append({'url':css_url, 'file':name, 'colors':sorted(set(re.findall(r'#[0-9a-fA-F]{3,8}\b',css))), 'font_families':sorted(set(re.findall(r'font-family\s*:\s*([^;}]+)',css)))})
    except Exception as e:
        branding['stylesheets'].append({'url':css_url,'error':str(e)})
for tag in re.findall(r'<(?:img|svg)\b[^>]*>', html, re.I):
    if re.search('logo',tag,re.I): branding['image_candidates'].append(tag)
(OUT/'branding-inventory.json').write_text(json.dumps(branding, indent=2), encoding='utf-8')
print(json.dumps({'sheets':[{'name':s['name'],'populated':sum(c['value'] is not None or c['formula'] is not None for c in s['cells'])} for s in result['sheets']], 'stylesheets':len(css_urls), 'logo_tags':len(branding['image_candidates'])}, indent=2))
