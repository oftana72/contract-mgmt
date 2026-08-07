import urllib.request, urllib.parse, http.cookiejar, re, sys

BASE = 'https://contract-mgmt-lnzy.onrender.com'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(urllib.request.Request(BASE + '/login', data=urllib.parse.urlencode({'username':'admin','password':'admin'}).encode(), headers={'User-Agent':'Mozilla/5.0'}), timeout=90)

po_id = 14457  # 4500010303 Humanwell Truck ETB
r = opener.open(urllib.request.Request(f'{BASE}/pos/{po_id}/edit', headers={'User-Agent':'Mozilla/5.0'}), timeout=90)
html = r.read().decode('utf-8')

# extract form fields (name -> default value)
fields = {}
textareas = {}
selects = {}
for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*>', html):
    name = m.group(1)
    val = ''
    vm = re.search(r'value="([^"]*)"', m.group(0))
    if vm:
        val = vm.group(1)
    typ = re.search(r'type="([^"]*)"', m.group(0))
    t = typ.group(1).lower() if typ else 'text'
    if t == 'checkbox':
        fields[name] = m.group(0)  # need checked handling
    else:
        fields[name] = val
for m in re.finditer(r'<textarea[^>]*name="([^"]+)"[^>]*>(.*?)</textarea>', html, re.S):
    textareas[m.group(1)] = re.sub(r'<[^>]+>', '', m.group(2)).replace('&amp;','&')
for m in re.finditer(r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.S):
    name = m.group(1)
    sel = re.search(r'<option value="([^"]*)"\s+selected', m.group(2)) or re.search(r'<option selected[^>]*value="([^"]*)"', m.group(2)) or re.search(r'<option\s+selected[^>]*>\s*([^<]+?)\s*</option>', m.group(2))
    if sel:
        selects[name] = sel.group(1).strip()

form = {}
for k, v in fields.items():
    if 'check' in k.lower() or k in ('csrf_token',):  # skip checkboxes unless needed
        form[k] = ''
    else:
        form[k] = v
form.update(textareas)
form.update(selects)

# print key fields
for k in ['po_status','mode_of_shipment','lc_status','lc_opened_date','po_number']:
    print(f'{k} = {form.get(k)!r}')

form['po_status'] = 'Cancelled'
# ensure mode truck
print('mode before:', form.get('mode_of_shipment'))
if form.get('mode_of_shipment','').strip().lower() != 'truck':
    form['mode_of_shipment'] = 'Truck'
print('mode after:', form.get('mode_of_shipment'))

# handle checkbox arrays (delete_pg, delete_item) - leave empty
for k in list(form.keys()):
    if k.startswith('delete_'):
        del form[k]

data = urllib.parse.urlencode(form).encode()
req = urllib.request.Request(f'{BASE}/pos/{po_id}/edit', data=data, headers={'User-Agent':'Mozilla/5.0'})
try:
    r = opener.open(req, timeout=90)
    print('POST edit status:', r.status, 'url:', r.geturl())
except urllib.error.HTTPError as e:
    print('POST edit HTTPError:', e.code)
    print(e.read().decode()[:500])
    sys.exit(1)

# check detail page status
r = opener.open(urllib.request.Request(f'{BASE}/pos/{po_id}', headers={'User-Agent':'Mozilla/5.0'}), timeout=90)
det = r.read().decode('utf-8')
# find status badge
for line in det.splitlines():
    if 'badge bg-info' in line or 'po_status' in line:
        print('DETAIL:', line.strip()[:150])
