import urllib.request, urllib.parse, http.cookiejar, json, re

BASE = 'https://contract-mgmt-lnzy.onrender.com'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(urllib.request.Request(BASE + '/login', data=urllib.parse.urlencode({'username':'admin','password':'admin'}).encode(), headers={'User-Agent':'Mozilla/5.0'}), timeout=120)

pos = json.loads(opener.open(urllib.request.Request(BASE + '/api/pos', headers={'User-Agent':'Mozilla/5.0'}), timeout=120).read().decode())
target = None
for p in pos:
    if p['po_number'] == '4500002915':
        target = p
        break
print('target:', target and (target['id'], target['po_number'], len(target['pgs']), len(target['lcs'])))
if not target:
    print('not found')
    raise SystemExit
po_id = target['id']

r = opener.open(urllib.request.Request(f'{BASE}/pos/{po_id}/edit', headers={'User-Agent':'Mozilla/5.0'}), timeout=120)
html = r.read().decode('utf-8')
mm = re.search(r'name="mode_of_shipment"[^>]*value="([^"]*)"', html)
print('mode field:', mm.group(1) if mm else '?')
sm = re.search(r'name="po_status"[^>]*>\s*<option value="([^"]*)" selected', html)
print('current status option:', sm.group(1) if sm else '?')

# Build full form (reuse approach)
fields = {}
textareas = {}
selects = {}
for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', html):
    name = m.group(1)
    val = ''
    vm = re.search(r'value="([^"]*)"', m.group(0))
    if vm: val = vm.group(1)
    typ = re.search(r'type="([^"]*)"', m.group(0))
    t = typ.group(1).lower() if typ else 'text'
    if t == 'checkbox': fields[name] = ''
    else: fields[name] = val
for m in re.finditer(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', html, re.S):
    textareas[m.group(1)] = re.sub(r'<[^>]+>', '', m.group(2)).replace('&amp;','&')
for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
    name = m.group(1)
    sel = re.search(r'<option value="([^"]*)"\s+selected', m.group(2)) or re.search(r'<option selected[^>]*>\s*([^<]+?)\s*</option>', m.group(2))
    if sel: selects[name] = sel.group(1).strip()
form = {k: v for k, v in fields.items()}
form.update(textareas); form.update(selects)
for k in list(form.keys()):
    if k.startswith('delete_'): del form[k]
form['po_status'] = 'Cancelled'
print('mode for POST:', form.get('mode_of_shipment'))

data = urllib.parse.urlencode(form).encode()
try:
    r = opener.open(urllib.request.Request(f'{BASE}/pos/{po_id}/edit', data=data, headers={'User-Agent':'Mozilla/5.0'}), timeout=120)
    print('POST status:', r.status, r.geturl())
except urllib.error.HTTPError as e:
    print('POST HTTPError:', e.code)
    print(e.read().decode()[:300])
    raise SystemExit

r = opener.open(urllib.request.Request(f'{BASE}/pos/{po_id}', headers={'User-Agent':'Mozilla/5.0'}), timeout=120)
det = r.read().decode('utf-8')
for line in det.splitlines():
    if 'badge bg-info' in line:
        print('DETAIL STATUS:', line.strip()[:120])
