import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.post('https://contract-mgmt-lnzy.onrender.com/login', data={'username': 'admin', 'password': 'admin'}, timeout=30)
r = s.get('https://contract-mgmt-lnzy.onrender.com/api/pos', timeout=30)
data = r.json()
print('Total:', len(data))

sns = [p.get('serial_number') for p in data]
none_sn = sum(1 for s in sns if s is None)
with_sn = sum(1 for s in sns if s is not None)
print('With SN:', with_sn, 'None SN:', none_sn)

valid = [s for s in sns if s is not None]
if valid:
    print('SN range:', min(valid), '-', max(valid))
    print('Unique SNs:', len(set(valid)))
    print('SN 1509 exists:', 1509 in valid)
    print('SN 3054 exists:', 3054 in valid)

# Sample records
for p in data[:3]:
    print('ID:', p['id'], 'SN:', p.get('serial_number'), 'PO:', str(p.get('po_number',''))[:40])
