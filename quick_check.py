import requests, urllib3, re, json
urllib3.disable_warnings()
s = requests.Session()
s.verify = False

# Login
r = s.post('https://contract-mgmt-lnzy.onrender.com/login',
           data={'username': 'admin', 'password': 'admin'}, timeout=15)
print('Login:', r.status_code, ('OK' if '/login' not in r.url else 'redirected'))

# Dashboard
r = s.get('https://contract-mgmt-lnzy.onrender.com/', timeout=15)
print('Dash:', r.status_code)
for m in re.findall(r'<h[1-6][^>]*>\s*([\d,./]+)\s*</h[1-6]>', r.text):
    print('  >', m)

# Try API with draw parameter (faster)
r = s.get('https://contract-mgmt-lnzy.onrender.com/api/pos?draw=1&start=0&length=1', timeout=15)
if r.status_code == 200:
    d = r.json()
    print('API total:', d.get('recordsTotal', d.get('total', '?')))
else:
    print('API:', r.status_code)
