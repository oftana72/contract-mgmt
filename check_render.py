import requests, re, urllib3
urllib3.disable_warnings()

BASE = 'https://contract-mgmt-lnzy.onrender.com'
s = requests.Session()
s.verify = False

# Login
r = s.post(BASE + '/login', data={'username': 'admin', 'password': 'admin'})
print('Login:', r.status_code, r.url)

# Get main page
r = s.get(BASE + '/')
content = r.text

# Find PO count in various places
for line in content.split('\n'):
    if 'po_count' in line or 'total' in line.lower() and 'po' in line.lower():
        print(line.strip()[:200])

# Look for DataTable info
match = re.search(r'Showing \d+ to \d+ of ([\d,]+)', content)
if match:
    print('PO count (DataTable):', match.group(1))

# Count rows in the table body
rows = re.findall(r'<tr[^>]*>', content)
print('Table rows found:', len(rows))

# Look for JSON data
match = re.search(r'po_count["\']?\s*[:=]\s*(\d+)', content)
if match:
    print('PO count (JSON):', match.group(1))
