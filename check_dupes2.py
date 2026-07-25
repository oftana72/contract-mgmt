import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.post('https://contract-mgmt-lnzy.onrender.com/login', data={'username': 'admin', 'password': 'admin'}, timeout=30)
r = s.get('https://contract-mgmt-lnzy.onrender.com/api/pos', timeout=30)
data = r.json()

# Check one record's full keys
if data:
    print('Keys:', list(data[0].keys()))
    print('First record:', json.dumps(data[0], indent=2, default=str)[:500])

# Count different po_numbers
po_nums = {}
for p in data:
    pn = p.get('po_number', '')
    if pn:
        key = str(pn)[:30]
        po_nums[key] = po_nums.get(key, 0) + 1
print('\nPO number distribution (top 10):')
for k, v in sorted(po_nums.items(), key=lambda x: -x[1])[:10]:
    print(f'  {k}: {v}')
