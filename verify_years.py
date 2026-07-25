import requests
s = requests.Session()
s.post('http://127.0.0.1:5000/login', data={'username': 'admin', 'password': 'admin'}, timeout=10)

s2 = requests.Session()
s2.post('https://contract-mgmt-lnzy.onrender.com/login', data={'username': 'admin', 'password': 'admin'}, timeout=10)

for label, base, session in [
    ('Local MySQL', 'http://127.0.0.1:5000', s),
    ('Render PG', 'https://contract-mgmt-lnzy.onrender.com', s2),
]:
    print(f'\n=== {label} ===')
    # Check PO list with year filter
    r = session.get(base + '/pos?year=2025', timeout=10)
    print('  PO list (year=2025):', r.status_code, '| Has year badge:', '"2025"' in r.text)
    
    # Check year summary in response
    if 'Contracts by Year' in r.text:
        print('  Year summary section present')
    
    # Check year filter dropdown
    if 'All Years' in r.text:
        print('  Year filter dropdown present')
    
    # Check year column
    if 'badge bg-secondary' in r.text:
        print('  Year badges in table rows')
    
    # Check years query via API - get distinct years by checking first PO
    r2 = session.get(base + '/api/pos', timeout=10)
    data = r2.json()
    years = set()
    for po in data[:20]:
        # check received date - not in API response directly
        po_detail = session.get(base + '/pos/' + str(po['id']), timeout=10)
        if '<td>2025' in po_detail.text or '<td>2026' in po_detail.text:
            pass
    print('  API total POs:', len(data))
    
    # Check reports page
    r3 = session.get(base + '/reports', timeout=10)
    print('  Reports page:', r3.status_code)
    if 'Contracts by Year' in r3.text:
        print('  Year report section present')
    if 'Budget Source by Year' in r3.text:
        print('  Budget x Year crosstab present')

print('\nDone')
