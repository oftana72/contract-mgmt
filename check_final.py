import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.post('https://contract-mgmt-lnzy.onrender.com/login', data={'username': 'admin', 'password': 'admin'}, timeout=60)
r = s.get('https://contract-mgmt-lnzy.onrender.com/api/pos', timeout=60)
data = r.json()
print('Total POs:', len(data))

sns = [p.get('serial') for p in data if p.get('serial') is not None]
print('Serials:', len(sns))
print('Range:', min(sns), '-', max(sns))
print('Unique:', len(set(sns)))

from collections import Counter
cnt = Counter(sns)
dupes = {k:v for k,v in cnt.items() if v > 1}
print('Duplicate serials:', len(dupes))

# Check orphans still present
orphan_po = [p for p in data if not p.get('po_number') and not p.get('supplier') and not p.get('total_amount') and not p.get('currency')]
print('Orphan POs (no PO#, supplier, amount, currency):', len(orphan_po))

# Stats from dashboard
r2 = s.get('https://contract-mgmt-lnzy.onrender.com/', timeout=60)
import re
for line in r2.text.split('\n'):
    if any(x in line for x in ['Purchase Order', 'Line Item', 'Supplier', 'Total Amoun']):
        clean = re.sub(r'<[^>]+>', '', line).strip()
        if clean:
            print('Label:', clean)
for m in re.findall(r'<h[1-6][^>]*>\s*([\d,./]+)\s*</h[1-6]>', r2.text):
    print('Value:', m)
