import urllib.request, urllib.parse, http.cookiejar, json

BASE = 'https://contract-mgmt-lnzy.onrender.com'
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(urllib.request.Request(BASE + '/login', data=urllib.parse.urlencode({'username':'admin','password':'admin'}).encode(), headers={'User-Agent':'Mozilla/5.0'}), timeout=90)

# We need PO detail which includes mode_of_shipment. Use /export/pos or po pages.
# Try export/pos to get mode + status
r = opener.open(urllib.request.Request(BASE + '/export/pos', headers={'User-Agent':'Mozilla/5.0'}), timeout=120)
data = r.read().decode('utf-8')
import csv, io
reader = csv.reader(io.StringIO(data))
rows = list(reader)
print('export rows:', len(rows))
if rows:
    print('header:', rows[0][:30])
# find trucks
for row in rows[1:]:
    joined = ' | '.join(row)
    if 'Truck' in joined and len(row) > 3:
        print(row[:12])
