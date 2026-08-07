import urllib.request, urllib.parse, http.cookiejar, json

BASE = 'https://contract-mgmt-lnzy.onrender.com'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(urllib.request.Request(BASE + '/login', data=urllib.parse.urlencode({'username':'admin','password':'admin'}).encode(), headers={'User-Agent':'Mozilla/5.0'}), timeout=90)

# Use /api/pos to list, then fetch a few po_detail pages to find a Sea PO with PG received + LC not opened.
pos = json.loads(opener.open(urllib.request.Request(BASE + '/api/pos', headers={'User-Agent':'Mozilla/5.0'}), timeout=120).read().decode())
print('total:', len(pos))

import re
candidates = []
for p in pos:
    if p['po_number'] and len(p['pgs']) > 0 and len(p['lcs']) == 0:
        candidates.append(p)
print('POs with PG but no LC:', len(candidates))

# fetch detail pages to find mode=Sea
for p in candidates[:40]:
    try:
        r = opener.open(urllib.request.Request(f"{BASE}/pos/{p['id']}", headers={'User-Agent':'Mozilla/5.0'}), timeout=60)
        det = r.read().decode('utf-8')
        m = re.search(r'mode_of_shipment or .-.</i>\s*([^<]+)<', det) or re.search(r'<div class="col-md-8">([^<]+)</div>', det)
        mode = ''
        mm = re.search(r'Mode of Shipment</strong></div>\s*<div class="col-md-8">([^<]*)</div>', det, re.S)
        if mm:
            mode = mm.group(1).strip()
        status = ''
        sm = re.search(r'badge bg-info">([^<]+)</span>', det)
        if sm:
            status = sm.group(1).strip()
        print(f"id={p['id']} po={p['po_number']} mode={mode!r} status={status!r}")
    except Exception as e:
        print(f"id={p['id']} ERR {e}")
