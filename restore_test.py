import urllib.request, urllib.parse, http.cookiejar, re, sys
BASE = 'https://contract-mgmt-lnzy.onrender.com'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(urllib.request.Request(BASE + '/login', data=urllib.parse.urlencode({'username':'admin','password':'admin'}).encode(), headers={'User-Agent':'Mozilla/5.0'}), timeout=120)

def set_stat(po_id, new_status):
    r = opener.open(urllib.request.Request(f'{BASE}/pos/{po_id}/edit', headers={'User-Agent':'Mozilla/5.0'}), timeout=120)
    html = r.read().decode('utf-8')
    fields, textareas, selects = {}, {}, {}
    for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', html):
        n = m.group(1); v = ''
        vm = re.search(r'value="([^"]*)"', m.group(0))
        if vm: v = vm.group(1)
        t = re.search(r'type="([^"]*)"', m.group(0))
        tt = t.group(1).lower() if t else 'text'
        fields[n] = '' if tt == 'checkbox' else v
    for m in re.finditer(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', html, re.S):
        textareas[m.group(1)] = re.sub(r'<[^>]+>', '', m.group(2)).replace('&amp;','&')
    for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
        n = m.group(1)
        sel = re.search(r'<option value="([^"]*)"\s+selected', m.group(2)) or re.search(r'<option selected[^>]*>\s*([^<]+?)\s*</option>', m.group(2))
        if sel: selects[n] = sel.group(1).strip()
    form = dict(fields); form.update(textareas); form.update(selects)
    for k in list(form):
        if k.startswith('delete_'): del form[k]
    form['po_status'] = new_status
    data = urllib.parse.urlencode(form).encode()
    try:
        opener.open(urllib.request.Request(f'{BASE}/pos/{po_id}/edit', data=data, headers={'User-Agent':'Mozilla/5.0'}), timeout=120)
        print(f'set {po_id} -> {new_status} OK')
    except urllib.error.HTTPError as e:
        print(f'set {po_id} -> {new_status} HTTPError {e.code}')
        print(e.read().decode()[:300])

set_stat(14457, 'Awaiting LC opening')

# verify detail
r = opener.open(urllib.request.Request(f'{BASE}/pos/14457', headers={'User-Agent':'Mozilla/5.0'}), timeout=120)
det = r.read().decode('utf-8')
for line in det.splitlines():
    if 'badge bg-info' in line:
        print('DETAIL:', line.strip()[:100])