import requests, urllib3, re
urllib3.disable_warnings()

BASE = 'https://contract-mgmt-lnzy.onrender.com'
s = requests.Session()
s.verify = False

# Login
r = s.post(BASE + '/login', data={'username': 'admin', 'password': 'admin'})
print('POST /login:', r.status_code, r.url)

# Get dashboard
r = s.get(BASE + '/')
print('GET /:', r.status_code)

# Find all numbers in the page with context
for line in r.text.split('\n'):
    if any(x in line for x in ['total_pos', 'total_items', 'total_suppliers', 'total_amount', 'po_count', 'stat-value', 'stat', 'count', 'badge']):
        print(line.strip()[:200])

# Find stat card values - these are typically in a div with class stat-number or similar
matches = re.findall(r'<div[^>]*class="?[^"]*stat[^"]*"?[^>]*>.*?(\d[\d,.]*)', r.text)
print('\nStat values found:', matches)

# Or look for the dashboard structure
sections = re.findall(r'<h[1-6][^>]*>.*?</h[1-6]>', r.text, re.DOTALL)
for s_ in sections:
    clean = re.sub(r'<[^>]+>', '', s_).strip()
    if clean and len(clean) < 30:
        print('Heading:', clean)

# Count POs via the POs page
r2 = s.get(BASE + '/pos')
if r2.status_code == 200:
    print('\nPOs page loaded:', len(r2.text), 'bytes')
    # Find DataTable info
    match = re.search(r'Showing \d+ to \d+ of ([\d,]+)', r2.text)
    if match:
        print('DataTable PO count:', match.group(1))
