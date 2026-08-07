import urllib.request, urllib.parse, http.cookiejar, json, re, time

BASE = 'https://contract-mgmt-lnzy.onrender.com'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(urllib.request.Request(BASE + '/login', data=urllib.parse.urlencode({'username':'admin','password':'admin'}).encode(), headers={'User-Agent':'Mozilla/5.0'}), timeout=120)

pos = json.loads(opener.open(urllib.request.Request(BASE + '/api/pos', headers={'User-Agent':'Mozilla/5.0'}), timeout=120).read().decode())
cand = [p for p in pos if p['po_number'] and len(p['pgs']) > 0 and len(p['lcs']) == 0]
found = 0
for p in cand[:80]:
    try:
        r = opener.open(urllib.request.Request(f"{BASE}/pos/{p['id']}/edit", headers={'User-Agent':'Mozilla/5.0'}), timeout=60)
        html = r.read().decode('utf-8')
        mm = re.search(r'name="mode_of_shipment"[^>]*value="([^"]*)"', html)
        mode = mm.group(1).strip() if mm else '?'
        if mode.lower() == 'sea':
            sm = re.search(r'name="po_status"[^>]*value="([^"]*)"', html)
            cur = ''
            cm = re.search(r'<option value="([^"]*)" selected', html)
            if cm: cur = cm.group(1)
            print('SEA candidate: id=%s po=%s status=%r' % (p['id'], p['po_number'], cur))
            found += 1
            if found >= 3: break
    except Exception as e:
        print('ERR', p['id'], str(e)[:80])
    time.sleep(0.3)
print('done, found', found)
