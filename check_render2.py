import requests, urllib3, re, time
urllib3.disable_warnings()

BASE = 'https://contract-mgmt-lnzy.onrender.com'
s = requests.Session()
s.verify = False

# Login
r1 = s.post(BASE + '/login', data={'username': 'admin', 'password': 'admin'}, timeout=30)
print('Login:', r1.status_code, r1.url)

if r1.status_code == 200 and '/login' not in r1.url:
    r = s.get(BASE + '/', timeout=30)
    print('Dashboard:', r.status_code, len(r.text), 'bytes')
    
    # Find stat values
    for line in r.text.split('\n'):
        if any(x in line for x in ['Purchase Order', 'Line Item', 'Supplier', 'Total Amoun']):
            clean = re.sub(r'<[^>]+>', '', line).strip()
            if clean:
                print('  Label:', clean)
    
    # Extract heading values (the numbers)
    h_tags = re.findall(r'<h[1-6][^>]*>\s*([\d,.]+)\s*</h[1-6]>', r.text)
    print('Stat values:', h_tags)
    
    # Also check the POs page
    r2 = s.get(BASE + '/pos', timeout=30)
    match = re.search(r'Showing \d+ to \d+ of ([\d,]+)', r2.text)
    if match:
        print('POs table count:', match.group(1))
    print('POs page length:', len(r2.text))
else:
    print('Login failed or redirected to login')
    if r1.status_code == 500:
        print('Server error')
