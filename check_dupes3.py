import requests, urllib3, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False
s.post('https://contract-mgmt-lnzy.onrender.com/login', data={'username': 'admin', 'password': 'admin'}, timeout=30)
r = s.get('https://contract-mgmt-lnzy.onrender.com/api/pos', timeout=30)
data = r.json()
print('Total:', len(data))

# Use correct key 'serial'
sns = [p.get('serial') for p in data]
valid = [s for s in sns if s is not None]
print('With serial:', len(valid))
if valid:
    print('Serial range:', min(valid), '-', max(valid))
    print('Unique serials:', len(set(valid)))
    print('Serial 1509 exists:', 1509 in valid)
    print('Serial 3054 exists:', 3054 in valid)
    
    # Count duplicate serials
    from collections import Counter
    cnt = Counter(valid)
    dupes = {k:v for k,v in cnt.items() if v > 1}
    print('Unique serials with duplicates:', len(dupes))
    if dupes:
        print('Sample duplicate serials:')
        for k, v in sorted(dupes.items())[:5]:
            print(f'  Serial {k}: {v} records')
else:
    # Show sample
    for p in data[:3]:
        print('ID:', p['id'], 'Keys:', list(p.keys()))
