import urllib.request, urllib.parse, http.cookiejar, json, re

BASE = 'https://contract-mgmt-lnzy.onrender.com'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(urllib.request.Request(BASE + '/login', data=urllib.parse.urlencode({'username':'admin','password':'admin'}).encode(), headers={'User-Agent':'Mozilla/5.0'}), timeout=120)

pos = json.loads(opener.open(urllib.request.Request(BASE + '/api/pos', headers={'User-Agent':'Mozilla/5.0'}), timeout=120).read().decode())
cand = [p for p in pos if p['po_number'] and len(p['pgs']) > 0 and len(p['lcs']) == 0]
print('candidates (PG, no LC):', len(cand))
for p in cand[:60]:
    print(p['id'], p['po_number'])
