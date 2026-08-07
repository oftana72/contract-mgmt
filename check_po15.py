import urllib.request, urllib.parse, http.cookiejar, re
BASE = 'https://contract-mgmt-lnzy.onrender.com'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(urllib.request.Request(BASE + '/login', data=urllib.parse.urlencode({'username':'admin','password':'admin'}).encode(), headers={'User-Agent':'Mozilla/5.0'}), timeout=120)
r = opener.open(urllib.request.Request(f'{BASE}/pos/15', headers={'User-Agent':'Mozilla/5.0'}), timeout=120)
html = r.read().decode('utf-8')
for line in html.splitlines():
    if 'badge bg-info' in line:
        print('DETAIL:', line.strip()[:120])